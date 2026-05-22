from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.security.api_key import APIKeyHeader
from contextlib import asynccontextmanager
import asyncio
import redis.asyncio as redis_async
from app.api.routes import health, admin, cameras
from app.core.config import settings
from app.detection.yunet_detector import YuNetDetector
from app.recognition.ghostfacenet import GhostFaceNet
from app.recognition.faiss_index import WatchlistIndex
import threading

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

async def redis_listener():
    r = redis_async.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )
    last_id = '$'
    while True:
        try:
            events = await r.xread({'alerts.global': last_id}, count=1, block=2000)
            if events:
                stream, messages = events[0]
                for msg_id, data in messages:
                    last_id = msg_id
                    if 'alert' in data:
                        await manager.broadcast(data['alert'])
        except Exception:
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.detector = YuNetDetector()
    app.state.recognizer = GhostFaceNet()
    app.state.faiss_idx = WatchlistIndex()
    app.state.faiss_lock = threading.Lock()
    
    task = asyncio.create_task(redis_listener())
    yield
    task.cancel()

app = FastAPI(title="AI Surveillance Engine API", version="0.1.0", lifespan=lifespan)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    if settings.API_KEY:
        if api_key != settings.API_KEY:
            raise HTTPException(status_code=403, detail="Could not validate API KEY")
    return api_key

app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_api_key)])
app.include_router(cameras.router, prefix="/api/cameras", tags=["cameras"], dependencies=[Depends(get_api_key)])

# v1 Aliases for external software integration
app.include_router(admin.router, prefix="/api/v1/faces", tags=["v1_faces"], dependencies=[Depends(get_api_key)])

@app.websocket("/api/v1/ws/alerts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"status": "AI Surveillance Engine API is running"}
