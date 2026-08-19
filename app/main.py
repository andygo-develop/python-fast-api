from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.core.lifespan import lifespan
from app.users.router import router as users_router


def create_app() -> FastAPI:
    app = FastAPI(title="fast-api", lifespan=lifespan)
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    return app


app = create_app()
