"""
KisanMitra — backend/local_server.py
Local server mirroring Lambda Function URL and serving frontend/ per ARCHITECTURE.md §5.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path when executed directly
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.handler import get_hello_card, lambda_handler

app = FastAPI(title="KisanMitra Local Mirror", version="1.0.0")

# Enable CORS for all local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = WORKSPACE_ROOT / "frontend"

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "kisanmitra-local", "mode": "mirror"}

@app.get("/api/cloud-status")
def cloud_status():
    from backend.s3_client import check_s3_connection
    s3_info = check_s3_connection()
    lambda_url = os.environ.get("LAMBDA_ENDPOINT", "https://k76r7b2zmycfizyb2bsevadqhm0ofgup.lambda-url.eu-north-1.on.aws/")
    return {
        "status": "online",
        "s3": s3_info,
        "lambda": {
            "function_name": os.environ.get("LAMBDA_FUNCTION_NAME", "kisaanmitrav1"),
            "endpoint": lambda_url,
            "region": os.environ.get("AWS_REGION", "eu-north-1"),
            "connected": True
        }
    }

@app.options("/chat")
def chat_options():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

@app.get("/api/regions")
def api_regions():
    from backend.tools.regions import get_all_districts, get_state_languages
    return {
        "districts": get_all_districts(),
        "state_languages": get_state_languages()
    }

@app.post("/api/farm-intelligence")
async def api_farm_intelligence(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    event = {
        "rawPath": "/api/farm-intelligence",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(body)
    }
    res = lambda_handler(event)
    return JSONResponse(content=json.loads(res["body"]), status_code=res.get("statusCode", 200))

@app.post("/api/crop-image-analysis")
async def api_crop_image_analysis(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    event = {
        "rawPath": "/api/crop-image-analysis",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(body)
    }
    res = lambda_handler(event)
    return JSONResponse(content=json.loads(res["body"]), status_code=res.get("statusCode", 200))

@app.post("/api/chat")
@app.post("/chat")
async def chat_endpoint(request: Request):
    """
    Mirror the Lambda Function URL handler locally.
    In Phase 0, returns the hardcoded hello card.
    In Phase 2, integrates router, agents, recommender, and supervisor.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Mirror Lambda event structure
    event = {
        "rawPath": "/chat",
        "requestContext": {
            "http": {
                "method": "POST"
            }
        },
        "body": json.dumps(body)
    }

    # Execute lambda_handler to guarantee 100% parity between local and Lambda
    res = lambda_handler(event)
    card_data = json.loads(res["body"])
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    return JSONResponse(content=card_data, status_code=res.get("statusCode", 200), headers=headers)

# Mount static frontend directory at root /
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.local_server:app", host="127.0.0.1", port=8000, reload=False, app_dir=str(WORKSPACE_ROOT))
