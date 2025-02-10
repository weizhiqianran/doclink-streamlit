from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

import requests as http_requests
import os
import uuid

from dotenv import load_dotenv
from .api import endpoints
from .db.database import Database

# Load configurations
load_dotenv()

# Constants
FRONTEND_URL = os.getenv("FRONTEND_URL_DEV", "http://localhost:3000")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
SECRET_KEY = os.getenv("MIDDLEWARE_SECRET_KEY")

# App initialization
app = FastAPI(title="Doclink")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


async def verify_google_token(token: str) -> dict:
    """Verify Google OAuth token and get user info"""
    try:
        # Use the access token to get user info from Google
        userinfo_response = http_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )

        if not userinfo_response.ok:
            raise ValueError("Failed to get user info")

        userinfo = userinfo_response.json()

        # Verify basic user info exists
        if not userinfo.get("sub"):  # 'sub' is the Google user ID
            raise ValueError("Invalid user info")

        return userinfo
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware to check authentication for protected routes"""
    # Public routes that don't need authentication
    public_paths = {"/api/version", "/docs", "/redoc", "/openapi.json"}

    if request.url.path in public_paths:
        return await call_next(request)

    if request.url.path.startswith("/chat/"):
        token = request.query_params.get("token")
        session_token = request.cookies.get("session_token")

        if not token and not session_token:
            return RedirectResponse(url=FRONTEND_URL)

        try:
            # If we have a session token, verify it with Google
            if session_token:
                try:
                    user_info = await verify_google_token(session_token)
                    request.state.user_data = {
                        "user_id": request.query_params.get("userId"),
                        "email": user_info.get("email"),
                    }
                    return await call_next(request)
                except Exception as e:
                    print(f"Error {e}")
                    if not token:
                        return RedirectResponse(url=FRONTEND_URL)

            # Token-based auth as fallback
            if token:
                print("Using token authentication")
                request.state.token = token
                request.state.user_id = request.query_params.get("userId")
                request.state.is_new_user = (
                    request.query_params.get("isNewUser", "false").lower() == "true"
                )
                return await call_next(request)

            return RedirectResponse(url=FRONTEND_URL)

        except Exception as e:
            print(f"Auth middleware error: {str(e)}", exc_info=True)
            return RedirectResponse(url=FRONTEND_URL)

    return await call_next(request)


@app.get("/chat/{session_id}")
async def chat_page(request: Request, session_id: str):
    """Handle both initial and subsequent visits to chat page"""
    try:
        # If we have a token in query params, this is an initial visit
        if hasattr(request.state, "token"):
            # Verify Google token and get user info
            google_user = await verify_google_token(request.state.token)

            # Create user data
            user_data = {
                "user_id": request.state.user_id,
                "email": google_user.get("email"),
                "name": google_user.get("name"),
                "picture": google_user.get("picture"),
            }

            # Database updates for session and initial user
            with Database() as db:
                # Create domain if first time
                if request.state.is_new_user:
                    domain_id = str(uuid.uuid4())
                    db.insert_domain_info(
                        user_id=request.state.user_id,
                        domain_id=domain_id,
                        domain_name="Default",
                        domain_type=0,
                    )
                    db.insert_user_guide(
                        user_id=request.state.user_id, domain_id=domain_id
                    )
                # Update session information
                db.upsert_session_info(
                    user_id=request.state.user_id, session_id=session_id
                )

                db.conn.commit()

            # Create response with template
            response = templates.TemplateResponse(
                "app.html",
                {
                    "request": request,
                    "session_id": session_id,
                    "user_id": user_data["user_id"],
                    "is_first_time": request.state.is_new_user,
                    "environment": "dev",
                },
            )

            # Set the Google token as both session and drive token
            response.set_cookie(
                key="session_token",
                value=request.state.token,
                httponly=True,
                secure=False,
                max_age=3600,
                samesite="strict",
            )

            return response

        # If we have user_data from cookie, this is a subsequent visit
        else:
            user_data = request.state.user_data

            with Database() as db:
                db.upsert_session_info(
                    user_id=user_data["user_id"], session_id=session_id
                )

            return templates.TemplateResponse(
                "app.html",
                {
                    "request": request,
                    "session_id": session_id,
                    "user_id": user_data["user_id"],
                    "is_first_time": False,
                    "environment": "dev",
                },
            )

    except Exception as e:
        print(f"Error in chat page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error rendering application")


@app.get("/api/get_drive_token")
async def get_drive_token(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="No access token found")
    try:
        await verify_google_token(session_token)
        return {"accessToken": session_token}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token {e}")


# Include other routes
app.include_router(endpoints.router, prefix="/api/v1")
