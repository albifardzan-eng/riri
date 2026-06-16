from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from api.routes import router
from config.settings import settings
from utils.logger import logger
from websocket.websocket_server import manager


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
    lifespan=lifespan
)

app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except Exception:
        manager.disconnect(websocket)