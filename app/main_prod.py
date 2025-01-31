from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

import requests as http_requests
import os
import jwt
import uuid

from datetime import datetime, timedelta
from dotenv import load_dotenv
from .api import endpoints
from .db.database import Database

# Load configurations
load_dotenv()

# Constants
FRONTEND_URL = os.getenv("FRONTEND_URL_PROD", "http://localhost:3000")
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


def create_session_token(user_data: dict) -> str:
    """Create an encrypted session token"""
    payload = {
        "user_id": user_data["user_id"],
        "email": user_data["email"],
        "exp": datetime.utcnow() + timedelta(days=1),  # 1 day expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_session_token(session_token: str) -> dict:
    """Verify and decode session token"""
    try:
        payload = jwt.decode(session_token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware to check authentication for protected routes"""
    # Public routes that don't need authentication
    public_paths = {"/api/version", "/docs", "/redoc", "/openapi.json"}

    if request.url.path in public_paths:
        return await call_next(request)

    # Check if it's a chat route
    if request.url.path.startswith("/chat/"):
        # Get either query parameters (from Next.js redirect) or session cookie
        token = request.query_params.get("token")
        session_cookie = request.cookies.get("session_token")

        if not token and not session_cookie:
            return RedirectResponse(url=FRONTEND_URL)

        try:
            if token:
                # Store token info in request state for the endpoint to use
                request.state.token = token
                request.state.user_id = request.query_params.get("userId")
                request.state.is_new_user = (
                    request.query_params.get("isNewUser", "false").lower() == "true"
                )
            else:
                # Verify session cookie
                user_data = verify_session_token(session_cookie)
                request.state.user_data = user_data
        except Exception as e:
            print(f"Auth error: {str(e)}")
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

            # Create session token
            session_token = create_session_token(user_data)

            # Create domain if first time
            if request.state.is_new_user:
                with Database() as db:
                    domain_id = str(uuid.uuid4())
                    db.insert_domain_info(
                        user_id=request.state.user_id,
                        domain_id=domain_id,
                        domain_name="My First Domain",
                        domain_type=0,
                    )
                    db.insert_user_guide(
                        user_id=request.state.user_id, domain_id=domain_id
                    )

            # Create response with template
            response = templates.TemplateResponse(
                "app.html",
                {
                    "request": request,
                    "session_id": session_id,
                    "user_id": user_data["user_id"],
                    "is_first_time": request.state.is_new_user,
                    "environment": "prod",
                },
            )

            # Set session cookie
            response.set_cookie(
                key="session_token",
                value=session_token,
                httponly=True,
                secure=False,
                max_age=86400,  # 1 day
                samesite="lax",
            )

            return response

        # If we have user_data from cookie, this is a subsequent visit
        else:
            user_data = request.state.user_data
            return templates.TemplateResponse(
                "app.html",
                {
                    "request": request,
                    "session_id": session_id,
                    "user_id": user_data["user_id"],
                    "is_first_time": False,
                    "environment": "prod",
                },
            )

    except Exception as e:
        print(f"Error in chat page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error rendering application")


@app.get("/api/version")
async def get_version():
    return {"version": "1.0.0"}


# Include other routes
app.include_router(endpoints.router, prefix="/api/v1")
