from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from config.settings import settings
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        f"{settings.APP_NAME} starting..."
    )

    yield

    logger.info(
        f"{settings.APP_NAME} shutting down..."
    )


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
)

app.include_router(router)
