from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel

from web_dashboard.config import WEB_SECRET_KEY
from web_dashboard.services.storage_service import web_db_get as db_get


router = APIRouter()
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


class UserLoginRequest(BaseModel):
    username: str
    password: str


def create_user_access_token(username: str):
    payload = {
        "sub": username,
        "role": "user",
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    }

    return jwt.encode(payload, WEB_SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, WEB_SECRET_KEY, algorithms=[ALGORITHM])

        username = payload.get("sub")
        role = payload.get("role")

        if not username or role != "user":
            raise HTTPException(status_code=401, detail="Invalid user token")

        users = db_get("users", {})

        if username not in users:
            raise HTTPException(status_code=401, detail="User no longer exists")

        return username

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid user token")


@router.post("/login")
def user_login(request: UserLoginRequest):
    username = request.username.strip()
    password = request.password.strip()

    users = db_get("users", {})

    if username not in users:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if users.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_user_access_token(username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }