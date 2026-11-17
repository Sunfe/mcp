from fastapi import Header, HTTPException, status
from app.config import settings


def verify_token(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return True
