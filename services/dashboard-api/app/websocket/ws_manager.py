from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections for real-time dashboard updates.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        try:
            await websocket.accept()
            self.active_connections.append(websocket)

            logger.info(
                f"Client connected. Active clients = {len(self.active_connections)}"
            )
        except Exception as e:
            logger.error(f"WebSocket accept failed: {e}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

            logger.info(
                f"Client disconnected. Active clients = {len(self.active_connections)}"
            )

    async def send_personal_message(
        self,
        message: Dict[str, Any],
        websocket: WebSocket
    ):
        try:
            await websocket.send_json(message)

        except WebSocketDisconnect:
            logger.warning("Client disconnected during personal message send")
            self.disconnect(websocket)

        except Exception as e:
            logger.error(f"Personal message send failed: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast message to all active clients
        """

        if not self.active_connections:
            return

        dead_connections = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)

            except WebSocketDisconnect:
                dead_connections.append(connection)

            except Exception as e:
                logger.warning(f"Broadcast failed: {e}")
                dead_connections.append(connection)

        # cleanup
        for conn in dead_connections:
            self.disconnect(conn)


# ⭐ Singleton instance (IMPORTANT — THIS FIXES YOUR IMPORT ERROR POSSIBILITY)
ws_manager: ConnectionManager = ConnectionManager()