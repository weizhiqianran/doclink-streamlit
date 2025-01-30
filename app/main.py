from fastapi import FastAPI, Request, HTTPException
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv

from .api import endpoints

# Load configurations
load_dotenv()

# App
app = FastAPI(title="Doclink")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
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
templates = Jinja2Templates(directory="templates")


@app.post("/render-app")
async def render_app(request: Request):
    try:
        # Get data from request
        data = await request.json()

        # Extract all fields from the request
        user_id = data.get("user_id")
        session_id = data.get("session_id")
        is_first_time = data.get("is_first_time")
        session_token = data.get("session_token")

        # Create template data
        template_data = {
            "request": request,
            "user_id": user_id,
            "session_id": session_id,
            "is_first_time": is_first_time,
            "session_token": session_token,
        }

        # Return rendered template
        return templates.TemplateResponse("app.html", template_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/{session_id}")
async def get_chat_page(request: Request, session_id: str):
    try:
        # Create template data
        template_data = {
            "request": request,
            "session_id": session_id,
            "is_first_time": "false",
        }

        # Return rendered template
        return templates.TemplateResponse("app.html", template_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/version")
async def get_version():
    return {"version": "1.0.0"}


# Include other routes
app.include_router(endpoints.router, prefix="/api/v1")
