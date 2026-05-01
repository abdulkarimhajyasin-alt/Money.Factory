from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError

from web_dashboard.config import (
    WEB_SECRET_KEY,
    WEB_ADMIN_USERNAME,
    WEB_ADMIN_PASSWORD
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

bearer_scheme = HTTPBearer()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, WEB_SECRET_KEY, algorithm=ALGORITHM)


def verify_login(username: str, password: str):
    return username == WEB_ADMIN_USERNAME and password == WEB_ADMIN_PASSWORD


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, WEB_SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")

        if username != WEB_ADMIN_USERNAME:
            raise HTTPException(status_code=401, detail="Invalid token")

        return username

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")