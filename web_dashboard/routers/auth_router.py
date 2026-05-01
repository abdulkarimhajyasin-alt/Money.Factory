from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from web_dashboard.auth import create_access_token, verify_login

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(data: LoginRequest):
    if not verify_login(data.username, data.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token({"sub": data.username})

    return {
        "access_token": token,
        "token_type": "bearer"
    }