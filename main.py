import time
import logging

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from utils.logging_conf import setup_logging
from utils.rate_limit import rate_limiter
from utils.auth import require_api_key
from routes import bus_stops

setup_logging()
logger = logging.getLogger("bus-stop-api")

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="bus-stop-api",
    version="1.0.0",
    description="API for retrieving bus stop information."
)

# Allow CORS for all origins (optional, for testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host

    if not rate_limiter(client_ip):
        logger.warning("rate_limit_exceeded", extra={"ip": client_ip})
        raise HTTPException(status_code=429, detail="Too many requests")
    
    return await call_next(request)


# Basic health check endpoint
start_time = time.time()
@app.get("/")
def health():
    """
    Returns the API status, name, version, and uptime in seconds.
    """
    uptime = int(time.time() - start_time)
    return {
        "msg": "API status 🚀",
        "name": app.title,
        "version": app.version,
        "uptime": uptime,
    }

# Include routers
app.include_router(
    bus_stops.router,
    dependencies=[Depends(require_api_key)]
)