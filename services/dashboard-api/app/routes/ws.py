from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.ws_manager import ws_manager

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await ws_manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)