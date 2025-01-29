from fastapi import APIRouter, UploadFile, HTTPException, Request, Query, File, Form
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime
import os
import logging
import uuid
import base64
import psycopg2

from .core import Processor
from .core import Authenticator
from ..db.database import Database
from ..redis_manager import RedisManager, RedisConnectionError

# services
router = APIRouter()
processor = Processor()
authenticator = Authenticator()
redis_manager = RedisManager()

# logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


# request functions
@router.post("/db/get_user_info")
async def get_user_info(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        with Database() as db:
            user_info, domain_info = db.get_user_info_w_id(user_id)

        return JSONResponse(
            content={
                "user_info": user_info,
                "domain_info": domain_info,
            },
            status_code=200,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/rename_domain")
async def rename_domain(request: Request):
    try:
        data = await request.json()
        selected_domain_id = data.get("domain_id")
        new_name = data.get("new_name")
        with Database() as db:
            success = db.rename_domain(domain_id=selected_domain_id, new_name=new_name)

            if not success:
                return JSONResponse(
                    content={"message": "error while renaming domain"},
                    status_code=400,
                )

        return JSONResponse(
            content={"message": "success"},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error renaming domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/create_domain")
async def create_domain(
    request: Request,
    userID: str = Query(...),
):
    try:
        data = await request.json()
        domain_name = data.get("domain_name")
        domain_id = str(uuid.uuid4())
        with Database() as db:
            success = db.create_domain(
                user_id=userID,
                domain_id=domain_id,
                domain_name=domain_name,
                domain_type=1,
            )

            if not success:
                return JSONResponse(
                    content={"message": "error while creating domain"},
                    status_code=400,
                )

        return JSONResponse(
            content={"message": "success", "domain_id": domain_id},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error renaming domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/delete_domain")
async def delete_domain(request: Request):
    try:
        data = await request.json()
        domain_id = data.get("domain_id")
        with Database() as db:
            success = db.delete_domain(domain_id=domain_id)

            if success < 0:
                return JSONResponse(
                    content={
                        "message": "This is your default domain. You cannot delete it completely, instead you can delete the unnucessary files inside!"
                    },
                    status_code=400,
                )
            elif success == 0:
                return JSONResponse(
                    content={
                        "message": "Error while deleting domain. Please report this to us, using feedback on the bottom left."
                    },
                    status_code=400,
                )

            db.conn.commit()

        return JSONResponse(
            content={"message": "success"},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error while deleting domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/insert_feedback")
async def insert_feedback(
    userID: str = Query(...),
    feedback_type: str = Form(...),
    feedback_description: str = Form(...),
    feedback_screenshot: UploadFile = File(None),
):
    try:
        feedback_id = str(uuid.uuid4())
        screenshot_data = None

        if feedback_screenshot:
            contents = await feedback_screenshot.read()
            if len(contents) > 2 * 1024 * 1024:  # 2MB limit
                raise HTTPException(
                    status_code=400, detail="Screenshot size should be less than 2MB"
                )
            screenshot_data = base64.b64encode(contents).decode("utf-8")

        with Database() as db:
            db.insert_user_feedback(
                feedback_id=feedback_id,
                user_id=userID,
                feedback_type=feedback_type,
                description=feedback_description[:5000],
                screenshot=screenshot_data,
            )
            db.conn.commit()

        return JSONResponse(
            content={"message": "Thanks for the feedback!"}, status_code=200
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/db/insert_rating")
async def insert_rating(
    userID: str = Query(...),
    rating: int = Form(...),
    user_note: str = Form(""),
):
    try:
        rating_id = str(uuid.uuid4())
        with Database() as db:
            db.insert_user_rating(
                rating_id=rating_id,
                user_id=userID,
                rating=rating,
                user_note=user_note if user_note else None,
            )
            db.conn.commit()

        return JSONResponse(
            content={"message": "Thank you for the rating!"}, status_code=200
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/select_domain")
async def select_domain(
    request: Request,
    userID: str = Query(...),
):
    try:
        data = await request.json()
        selected_domain_id = data.get("domain_id")
        _, _, success = update_selected_domain(
            user_id=userID, domain_id=selected_domain_id
        )

        if not success:
            return JSONResponse(
                content={"message": "error while updating selected domain"},
                status_code=400,
            )

        redis_manager.refresh_user_ttl(userID)
        return JSONResponse(
            content={"message": "success"},
            status_code=200,
        )
    except RedisConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in select_domain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/generate_answer")
async def generate_answer(
    request: Request,
    userID: str = Query(...),
    sessionID: str = Query(...),
):
    try:
        data = await request.json()
        user_message = data.get("user_message")
        file_ids = data.get("file_ids")

        # Check if domain is selected
        selected_domain_id = redis_manager.get_data(f"user:{userID}:selected_domain")
        if not selected_domain_id:
            return JSONResponse(
                content={"message": "Please select a domain first..."},
                status_code=400,
            )

        if not file_ids:
            return JSONResponse(
                content={"message": "You didn't select any files..."},
                status_code=400,
            )

        # Get required data from Redis
        index, filtered_content, boost_info, index_header = processor.filter_search(
            domain_content=redis_manager.get_data(f"user:{userID}:domain_content"),
            domain_embeddings=redis_manager.get_data(
                f"user:{userID}:domain_embeddings"
            ),
            file_ids=file_ids,
        )

        if not index or not filtered_content:
            return JSONResponse(
                content={"message": "Nothing in here..."},
                status_code=400,
            )

        with Database() as db:
            question_count = db.update_session_info(
                user_id=userID, session_id=sessionID
            )

        # Process search
        answer, resources, resource_sentences = processor.search_index(
            user_query=user_message,
            domain_content=filtered_content,
            boost_info=boost_info,
            index=index,
            index_header=index_header,
        )

        if not resources or not resource_sentences:
            return JSONResponse(
                content={"message": answer},
                status_code=200,
            )

        redis_manager.refresh_user_ttl(userID)

        return JSONResponse(
            content={
                "answer": answer,
                "resources": resources,
                "resource_sentences": resource_sentences,
                "question_count": question_count,
            },
            status_code=200,
        )

    except RedisConnectionError as e:
        logger.error(f"Redis connection error: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in generate_answer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/io/store_file")
async def store_file(
    userID: str = Query(...),
    file: UploadFile = File(...),
    lastModified: str = Form(...),
):
    try:
        file_bytes = await file.read()
        if not file_bytes:
            return JSONResponse(
                content={
                    "message": f"Empty file {file.filename}. If you think not, please report this to us!"
                },
                status_code=400,
            )

        file_data = processor.rf.read_file(
            file_bytes=file_bytes, file_name=file.filename
        )

        if not file_data["sentences"]:
            return JSONResponse(
                content={
                    "message": f"No content to extract in {file.filename}. If there is please report this to us!"
                },
                status_code=400,
            )

        # Create embeddings
        file_embeddings = processor.ef.create_embeddings_from_sentences(
            sentences=file_data["sentences"]
        )

        # Store in Redis
        redis_key = f"user:{userID}:upload:{file.filename}"
        upload_data = {
            "file_name": file.filename,
            "last_modified": datetime.fromtimestamp(int(lastModified) / 1000).strftime(
                "%Y-%m-%d"
            )[:20],
            "sentences": file_data["sentences"],
            "page_numbers": file_data["page_number"],
            "is_headers": file_data["is_header"],
            "is_tables": file_data["is_table"],
            "embeddings": file_embeddings,
        }

        redis_manager.set_data(redis_key, upload_data, expiry=3600)

        return JSONResponse(
            content={"message": "success", "file_name": file.filename},
            status_code=200,
        )

    except Exception as e:
        logging.error(f"Error storing file {file.filename}: {str(e)}")
        return JSONResponse(
            content={"message": f"Error storing file: {str(e)}"}, status_code=500
        )


@router.post("/io/upload_files")
async def upload_files(userID: str = Query(...)):
    try:
        # Get domain info
        selected_domain_id = redis_manager.get_data(f"user:{userID}:selected_domain")

        with Database() as db:
            domain_info = db.get_domain_info(
                user_id=userID, domain_id=selected_domain_id
            )

            if not domain_info:
                return JSONResponse(
                    content={"message": "Invalid domain selected"}, status_code=400
                )

            # Get all stored files from Redis
            stored_files = redis_manager.get_keys_by_pattern(f"user:{userID}:upload:*")
            if not stored_files:
                return JSONResponse(
                    content={"message": "No files to process"}, status_code=400
                )

            file_info_batch = []
            file_content_batch = []

            # Process stored files
            for redis_key in stored_files:
                upload_data = redis_manager.get_data(redis_key)
                if not upload_data:
                    continue

                file_id = str(uuid.uuid4())

                # Prepare batches
                file_info_batch.append(
                    (
                        userID,
                        file_id,
                        selected_domain_id,
                        upload_data["file_name"],
                        upload_data["last_modified"],
                    )
                )

                for i in range(len(upload_data["sentences"])):
                    file_content_batch.append(
                        (
                            file_id,
                            upload_data["sentences"][i],
                            upload_data["page_numbers"][i],
                            upload_data["is_headers"][i],
                            upload_data["is_tables"][i],
                            psycopg2.Binary(upload_data["embeddings"][i]),
                        )
                    )

                # Clean up Redis
                redis_manager.delete_data(redis_key)

            # Bulk insert
            success = db.insert_file_batches(file_info_batch, file_content_batch)
            if not success:
                return JSONResponse(
                    content={"message": "Failed to process files"}, status_code=500
                )
            db.conn.commit()

        # Update domain info
        file_names, file_ids, success = update_selected_domain(
            user_id=userID, domain_id=selected_domain_id
        )
        if not success:
            return JSONResponse(
                content={
                    "message": "Files uploaded but, domain could not be updated",
                    "file_names": None,
                    "file_ids": None,
                },
                status_code=400,
            )

        return JSONResponse(
            content={
                "message": "success",
                "file_names": file_names,
                "file_ids": file_ids,
            },
            status_code=200,
        )

    except Exception as e:
        logging.error(f"Error processing uploads: {str(e)}")
        return JSONResponse(
            content={"message": f"Error processing uploads: {str(e)}"}, status_code=500
        )


@router.post("/db/remove_file_upload")
async def remove_file_upload(
    request: Request,
    userID: str = Query(...),
):
    try:
        data = await request.json()
        file_id = data.get("file_id")
        domain_id = data.get("domain_id")

        with Database() as db:
            success = db.clear_file_content(file_id=file_id)
            if not success:
                return JSONResponse(
                    content={
                        "message": "Error deleting files",
                    },
                    status_code=400,
                )
            db.conn.commit()

        _, _, success = update_selected_domain(user_id=userID, domain_id=domain_id)
        if not success:
            return JSONResponse(
                content={"message": "error"},
                status_code=200,
            )

        return JSONResponse(
            content={
                "message": "success",
            },
            status_code=200,
        )
    except KeyError:
        return JSONResponse(
            content={"message": "Please select the domain number first"},
            status_code=200,
        )
    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during file deletion: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


@router.post("/auth/login")
async def login(
    request: Request,
):
    try:
        data = await request.json()
        user_email = data.get("user_email")
        trial_password = data.get("trial_password")
        message = None
        status_code = 500
        session_id = None
        with Database() as db:
            user_info = db.get_user_info_w_email(user_email=user_email)
            if not user_info or not authenticator.verify_password(
                plain_password=trial_password,
                hashed_password=user_info["user_password"],
            ):
                message = "Invalid email or password"
                status_code = 401
            elif not user_info["is_active"]:
                message = "User is not activated yet. Please contact with --> rahmansahinler1@gmail.com"
                status_code = 401
            else:
                session_id = str(uuid.uuid4())
                db.insert_session_info(user_info["user_id"], session_id=session_id)
                db.conn.commit()
                message = "Login sucessfull"
                status_code = 200

        response = JSONResponse(
            content={"message": message, "session_id": session_id},
            status_code=status_code,
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return response

    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during login: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


@router.post("/auth/signup")
async def signup(
    request: Request,
):
    try:
        data = await request.json()
        user_name = data.get("user_name")
        user_surname = data.get("user_surname")
        user_email = data.get("user_email")
        user_password = data.get("user_password")
        with Database() as db:
            user_info = db.get_user_info_w_email(user_email=user_email)
            if user_info:
                return JSONResponse(
                    content={
                        "message": "User already Signed Up!",
                    },
                    status_code=400,
                )
            else:
                # User insertion
                user_id = str(uuid.uuid4())
                db.insert_user_info(
                    user_id=user_id,
                    google_id=str(uuid.uuid4()),
                    user_name=user_name,
                    user_surname=user_surname,
                    user_password=authenticator.hash_password(user_password),
                    user_email=user_email,
                    user_type="trial",
                    is_active=True,
                    refresh_token=str(uuid.uuid4()),
                    access_token=str(uuid.uuid4()),
                    picture_url=str(uuid.uuid4()),
                )

                # Deafult domain creation
                domain_id = str(uuid.uuid4())
                db.insert_domain_info(
                    user_id=user_id,
                    domain_id=domain_id,
                    domain_name="My First Domain",
                    domain_type=0,
                )
                db.insert_user_guide(user_id=user_id, domain_id=domain_id)

                # Session creation
                session_id = str(uuid.uuid4())
                db.insert_session_info(user_id, session_id=session_id)
                db.conn.commit()

        response = JSONResponse(
            content={
                "message": "Successfully Signed Up! Logging in...",
                "session_id": session_id,
            },
            status_code=201,
        )
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="strict",
        )

        return response
    except Exception as e:
        db.conn.rollback()
        logging.error(f"Error during login: {str(e)}")
        raise HTTPException(
            content={"message": f"Failed deleting, error: {e}"}, status_code=500
        )


@router.get("/auth/google/login")
async def google_login(request: Request):
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "openid",
            ],
        )

        flow.redirect_uri = GOOGLE_REDIRECT_URI
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )

        # Create response with authorization URL
        response = JSONResponse({"authorization_url": authorization_url})

        # Set state in secure cookie
        response.set_cookie(
            key="oauth_state",
            value=state,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=300,
        )

        return response

    except Exception as e:
        print(f"Login error: {e}")
        return RedirectResponse(
            url="/login?error=authentication_failed", status_code=303
        )


@router.get("/auth/callback")
async def google_callback(request: Request):
    try:
        state = request.query_params.get("state")
        code = request.query_params.get("code")

        if not state or not code:
            return RedirectResponse(
                url="/login?error=missing_parameters", status_code=303
            )

        # Get state from cookie
        stored_state = request.cookies.get("oauth_state")
        if not stored_state or stored_state != state:
            return RedirectResponse(url="/login?error=invalid_state", status_code=303)

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI],
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "openid",
            ],
        )

        flow.redirect_uri = GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code)

        id_info = id_token.verify_oauth2_token(
            flow.credentials.id_token, requests.Request(), GOOGLE_CLIENT_ID
        )

        with Database() as db:
            user_info = db.get_user_info_w_email(user_email=id_info["email"])
            if not user_info:
                user_id = str(uuid.uuid4())
                first_time = 1
                db.insert_user_info(
                    user_id=user_id,
                    google_id=id_info["sub"],
                    user_name=id_info.get("given_name", ""),
                    user_surname=id_info.get("family_name", ""),
                    user_password="123456seven",
                    user_email=id_info["email"],
                    picture_url=id_info["picture"],
                    refresh_token=str(uuid.uuid4()),
                    access_token=str(uuid.uuid4()),
                    user_type="user",
                    is_active=True,
                )

                # Deafult domain creation
                domain_id = str(uuid.uuid4())
                db.insert_domain_info(
                    user_id=user_id,
                    domain_id=domain_id,
                    domain_name="My First Domain",
                    domain_type=0,
                )
                db.insert_user_guide(user_id=user_id, domain_id=domain_id)

            else:
                user_id = user_info["user_id"]
                first_time = 0

            session_id = str(uuid.uuid4())
            db.insert_session_info(user_id, session_id=session_id)
            db.conn.commit()

        response = RedirectResponse(
            url=f"/chat/{session_id}",
            status_code=303,
        )

        # Set session cookies
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
        )
        response.set_cookie(
            key="first_time",
            value=str(first_time),
            httponly=False,
        )

        # Clear the oauth state cookie
        response.delete_cookie(key="oauth_state")

        return response

    except Exception as e:
        print(f"Authentication error: {e}")
        return RedirectResponse(
            url="/login?error=authentication_failed", status_code=303
        )


# local functions
def update_selected_domain(user_id: str, domain_id: str):
    try:
        redis_manager.set_data(f"user:{user_id}:selected_domain", domain_id)

        with Database() as db:
            file_info = db.get_file_info_with_domain(user_id, domain_id)

            if not file_info:
                # Clear any existing domain data
                redis_manager.delete_data(f"user:{user_id}:domain_content")
                redis_manager.delete_data(f"user:{user_id}:index")
                redis_manager.delete_data(f"user:{user_id}:index_header")
                redis_manager.delete_data(f"user:{user_id}:boost_info")
                return None, None, 1

            content, embeddings = db.get_file_content(
                file_ids=[info["file_id"] for info in file_info]
            )

            if not content or not len(embeddings):
                # Clear any existing domain data
                redis_manager.delete_data(f"user:{user_id}:domain_content")
                redis_manager.delete_data(f"user:{user_id}:index")
                redis_manager.delete_data(f"user:{user_id}:index_header")
                redis_manager.delete_data(f"user:{user_id}:boost_info")
                return None, None, 0

            # Store domain content in Redis
            redis_manager.set_data(f"user:{user_id}:domain_content", content)
            redis_manager.set_data(f"user:{user_id}:domain_embeddings", embeddings)

            file_names = [info["file_name"] for info in file_info]
            file_ids = [info["file_id"] for info in file_info]

            return file_names, file_ids, 1

    except Exception as e:
        logger.error(f"Error in update_selected_domain: {str(e)}")
        raise RedisConnectionError(f"Failed to update domain: {str(e)}")
