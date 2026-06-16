from fastapi import WebSocket
from utils.logger import logger


class WebSocketManager:

    def __init__(self):
        self.connections = []

    async def connect(
        self,
        websocket: WebSocket
    ):
        await websocket.accept()
        self.connections.append(websocket)

        logger.info(
            f"WS Connected | Total={len(self.connections)}"
        )

    def disconnect(
        self,
        websocket: WebSocket
    ):
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(
        self,
        data: dict
    ):
        dead_connections = []

        for connection in self.connections:

            try:
                await connection.send_json(data)

            except Exception:
                dead_connections.append(connection)

        for conn in dead_connections:
            self.disconnect(conn)


manager = WebSocketManager()