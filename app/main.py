from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os
import jwt

from .api import endpoints
from .db.database import Database

app = FastAPI(title="Doclink")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/validate-user")
async def validate_user(request: Request):
    """
    Endpoint to validate and initialize user session
    """
    try:
        # Parse the incoming request body
        body = await request.json()

        # Extract user information
        user_id = body.get("user_id")
        email = body.get("email")

        # Validate the user in your database
        with Database() as db:
            # Check if user exists
            user = db.get_user_by_id(user_id)

            if not user:
                # Optional: Create user if not exists
                user = db.create_user({"user_id": user_id, "email": email})

            # Generate a session token
            session_token = generate_session_token(user)

            return JSONResponse(
                {
                    "status": "success",
                    "session_token": session_token,
                    "redirect_url": "/chat/new",  # Or your default chat page
                }
            )

    except Exception as e:
        return HTTPException(status_code=400, detail=str(e))


@app.get("/chat/{session_token}")
async def chat_page(request: Request, session_token: str):
    """
    Validate session token and render chat
    """
    try:
        # Validate session token
        user = validate_session_token(session_token)

        if not user:
            return RedirectResponse(url="/")  # Redirect to login/home

        # Render chat with user context
        return templates.TemplateResponse(
            "app.html",
            {"request": request, "user_id": user["id"], "session_token": session_token},
        )
    except Exception as e:
        return RedirectResponse(url="/")


def generate_session_token(user):
    """
    Generate a secure session token
    """
    payload = {
        "user_id": user["id"],
        "email": user["email"],
        "exp": datetime.utcnow() + timedelta(days=1),
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm="HS256")


def validate_session_token(token):
    """
    Validate and decode session token
    """
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        # Additional validation with database can be added here
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
