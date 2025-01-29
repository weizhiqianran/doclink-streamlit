from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse

from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

from jwt import encode, decode, ExpiredSignatureError, InvalidTokenError
import os
import logging
import uuid

from .api import endpoints
from .db.database import Database
from .db.config import GenerateConfig

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configurations
load_dotenv()
db_config = GenerateConfig.config()
JWT_SECRET = os.getenv("MIDDLEWARE_SECRET_KEY")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24

# App
app = FastAPI(title="Doclink")
security = HTTPBearer()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Template setup
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


# JWT helper functions
def create_access_token(user_id: str, email: str) -> str:
    """Create JWT access token"""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Dependency for protected routes"""
    return verify_token(credentials.credentials)


# Initialize user endpoint
@app.post("/initialize-user")
async def initialize_user(request: Request):
    try:
        body = await request.json()
        user_id = body.get("userId")
        session_token = body.get("sessionToken")
        is_new_user = body.get("isNewUser", False)

        print(f"Received initialization request: {body}")

        if not user_id or not session_token:
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Create a new session in database
        with Database() as db:
            session_id = str(uuid.uuid4())
            db.insert_session_info(user_id, session_id)

        # Generate access token
        access_token = create_access_token(user_id=user_id, email=body.get("email", ""))

        return JSONResponse(
            {
                "status": "success",
                "access_token": access_token,
                "token_type": "bearer",
                "session_id": session_id,
                "redirect_url": f"/chat/{session_id}",  # Include redirect URL
            }
        )

    except Exception as e:
        print(f"Error in initialize_user: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/chat/{session_id}")
async def chat_page(request: Request, session_id: str):
    """
    Validate session and render chat page
    """
    try:
        # Check if session exists and is valid
        with Database() as db:
            session_info = db.get_session_info(session_id)
            if not session_info:
                return RedirectResponse(url="/")

            user_id = session_info["user_id"]
            is_first_time = session_info.get("first_time", "1")

        # Render the app template with session data
        return templates.TemplateResponse(
            "app.html",
            {
                "request": request,
                "user_id": user_id,
                "session_id": session_id,
                "is_first_time": is_first_time,
            },
        )

    except Exception as e:
        logger.error(f"Error rendering chat page: {str(e)}")
        return RedirectResponse(url="/")


# Example protected route
@app.get("/check-session")
async def check_session(current_user: dict = Depends(get_current_user)):
    return {"status": "valid", "user_id": current_user["user_id"]}


# Include other routes
app.include_router(endpoints.router, prefix="/api/v1")
