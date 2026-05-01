from fastapi import APIRouter, Depends

from web_dashboard.auth import get_current_admin
from web_dashboard.services.dashboard_service import build_dashboard_summary

router = APIRouter()


@router.get("/summary")
def get_dashboard_summary(admin: str = Depends(get_current_admin)):
    return build_dashboard_summary()