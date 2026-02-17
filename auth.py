"""
QuranAI Authentication
Google OAuth2 + JWT token management.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import httpx
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database import get_db_session, get_or_create_user, get_user_by_id

# =====================================================
# CONFIGURATION
# =====================================================

# Google OAuth2 settings — set these as environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "quranai-change-this-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "72"))  # 3 days default

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"


# =====================================================
# SCHEMAS
# =====================================================

class GoogleAuthRequest(BaseModel):
    """For frontend sending the Google ID token directly."""
    credential: str  # Google ID token from Sign-In button


class GoogleCodeRequest(BaseModel):
    """For authorization code flow."""
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    preferred_language: str = "en"
    theme: str = "light"


# =====================================================
# JWT FUNCTIONS
# =====================================================

def create_access_token(user_id: str) -> str:
    """Create a JWT token for the user."""
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# =====================================================
# GOOGLE OAuth2 HELPERS
# =====================================================

async def verify_google_id_token(id_token: str) -> dict:
    """
    Verify a Google ID token (from the Sign-In with Google button).
    Returns the user info payload if valid.
    """
    async with httpx.AsyncClient() as client:
        # Use Google's tokeninfo endpoint for simple verification
        resp = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token"
            )

        payload = resp.json()

        # Verify the audience matches our client ID
        if payload.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token audience mismatch"
            )

        # Verify token is not expired
        if int(payload.get("exp", 0)) < int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )

        return {
            "google_id": payload["sub"],
            "email": payload["email"],
            "name": payload.get("name", payload.get("email", "User")),
            "picture": payload.get("picture"),
        }


async def exchange_google_code(code: str) -> dict:
    """
    Exchange an authorization code for tokens, then get user info.
    Used for the server-side OAuth2 flow.
    """
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })

        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Failed to exchange code: {token_resp.text}"
            )

        tokens = token_resp.json()
        access_token = tokens["access_token"]

        # Get user info
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if userinfo_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user info from Google"
            )

        info = userinfo_resp.json()
        return {
            "google_id": info["id"],
            "email": info["email"],
            "name": info.get("name", info.get("email", "User")),
            "picture": info.get("picture"),
        }


# =====================================================
# FASTAPI DEPENDENCIES
# =====================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db_session)
):
    """
    FastAPI dependency: extract and validate JWT, return User object.
    Use as: current_user = Depends(get_current_user)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_db_session)
):
    """
    Optional auth — returns User or None.
    Useful for endpoints that work with or without auth.
    """
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            return get_user_by_id(db, user_id)
    except Exception:
        pass
    return None


def get_google_auth_url(state: str = "") -> str:
    """Generate the Google OAuth2 consent URL."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"
