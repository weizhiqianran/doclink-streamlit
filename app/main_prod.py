from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

import requests as http_requests
import os
import jwt
import uuid
import logging
from logging.handlers import RotatingFileHandler
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            "/var/log/doclink/doclink.log",
            maxBytes=10000000,  # 10MB
            backupCount=5,
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


# App initialization
app = FastAPI(title="Doclink")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="templates")


# Middleware headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["Content-Security-Policy"] = (
        "default-src 'self';"
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://cdnjs.cloudflare.com "
        "https://www.googletagmanager.com "
        "https://www.google-analytics.com "
        "https://cdn.jsdelivr.net;"
        "style-src 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com "
        "https://cdn.jsdelivr.net "
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/ "
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.2/;"
        "style-src-elem 'self' 'unsafe-inline' "
        "https://fonts.googleapis.com "
        "https://cdn.jsdelivr.net "
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/ "
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.2/;"
        "font-src 'self' https://fonts.gstatic.com "
        "https://cdn.jsdelivr.net data:;"
        "img-src 'self' data: https://www.google-analytics.com https://*.googleusercontent.com;"
        "connect-src 'self' https://www.google-analytics.com;"
    )

    return response


# CORS
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
        logger.info(f"Token verification error: {str(e)}")
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
            # If we have both token and session, prioritize session
            if session_cookie:
                try:
                    user_data = verify_session_token(session_cookie)
                    request.state.user_data = user_data
                    return await call_next(request)
                except Exception as e:
                    logger.info(f"Error validation of session cookie {e}")
                    if not token:
                        return RedirectResponse(url=FRONTEND_URL)

            # Token-based auth as fallback
            if token:
                logger.info("Using token authentication")
                request.state.token = token
                request.state.user_id = request.query_params.get("userId")
                request.state.is_new_user = (
                    request.query_params.get("isNewUser", "false").lower() == "true"
                )
                return await call_next(request)

            # No valid auth method
            logger.info("No valid authentication method found")
            return RedirectResponse(url=FRONTEND_URL)

        except Exception as e:
            logger.info(f"Auth middleware error: {str(e)}", exc_info=True)
            return RedirectResponse(url=FRONTEND_URL)

    return await call_next(request)


@app.get("/chat/{session_id}")
async def chat_page(request: Request, session_id: str):
    """Handle both initial and subsequent visits to chat page"""
    logger.info(f"******** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ********")
    try:
        logger.info(f"Processing chat page request for session {session_id}")
        logger.info(f"Request state: {vars(request.state)}")

        # If we have a token in query params, this is an initial visit
        if hasattr(request.state, "token"):
            logger.info("Processing initial visit with token")
            # Verify Google token and get user info
            try:
                # Verify Google token and get user info
                google_user = await verify_google_token(request.state.token)
                logger.info(f"Google user verified: {google_user.get('email')}")

                # Create user data
                user_data = {
                    "user_id": request.state.user_id,
                    "email": google_user.get("email"),
                    "name": google_user.get("name"),
                    "picture": google_user.get("picture"),
                }

            except Exception as e:
                logger.error(f"Error processing token: {str(e)}", exc_info=True)
                raise

            # Create session token
            session_token = create_session_token(user_data)

            # Create domain if first time
            if request.state.is_new_user:
                with Database() as db:
                    domain_id = str(uuid.uuid4())
                    db.insert_domain_info(
                        user_id=request.state.user_id,
                        domain_id=domain_id,
                        domain_name="My First Folder",
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
            logger.info("Processing subsequent visit with session cookie")

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
        logger.info(f"Error processing subsequent visit with session cookie {e}")
        raise HTTPException(status_code=500, detail=f"Error rendering application {e}")


# Include other routes
app.include_router(endpoints.router, prefix="/api/v1")
