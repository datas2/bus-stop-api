import os
from dotenv import load_dotenv
from fastapi import HTTPException, Header

# Load environment variables from .env file
load_dotenv()

API_KEY = os.environ.get("API_KEY")
def require_api_key(x_api_key: str = Header(..., alias="x-api-key")):
    """
    Dependency to require API_KEY in the X-API-KEY header.
    """
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API Key."
        )