from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web_dashboard.database import init_web_db_pool
from web_dashboard.routers.auth_router import router as auth_router
from web_dashboard.routers.users_router import router as users_router
from web_dashboard.routers.dashboard_router import router as dashboard_router
from web_dashboard.routers.financial_router import router as financial_router
from web_dashboard.routers.user_auth_router import router as user_auth_router
from web_dashboard.routers.user_panel_router import router as user_panel_router

app = FastAPI(
    title="Money Factory Web Dashboard",
    version="1.0.0"
)

templates = Jinja2Templates(directory="web_dashboard/templates")


@app.on_event("startup")
def startup_event():
    init_web_db_pool()


@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )


@app.get("/user", response_class=HTMLResponse)
def user_dashboard_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="user_dashboard.html",
        context={}
    )


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(financial_router, prefix="/financial", tags=["Financial"])
app.include_router(user_auth_router, prefix="/user-auth", tags=["User Auth"])
app.include_router(user_panel_router, prefix="/user-panel", tags=["User Panel"])