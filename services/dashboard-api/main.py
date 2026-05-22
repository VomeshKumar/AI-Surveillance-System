from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / "config" / "dashboard-api.env")

from app.routes import auth, alerts, dashboard, faces, health, ws, cameras, reports, system, tracking
from app.database.postgres import AsyncSessionLocal
from app.database.postgres import init_db
from app.database.redis_cache import redis_manager
from app.services.tracking_service import update_tracking_for_detection
from app.storage.image_store import image_store
from app.streaming.redis_stream_hub import stream_hub
from app.websocket.ws_manager import ws_manager


# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------- ENGINE ALERT RELAY ----------------
async def engine_alert_relay():
    """
    Subscribes to the Engine's 'security_alerts' Redis Pub/Sub channel.
    On each alert from the Engine's recognition_worker:
      1. Broadcasts to all connected WebSocket dashboard clients.
      2. Pushes to 'face_events' stream for the consumer pipeline.
    This replaces the need for a separate bridge script.
    """
    while not redis_manager.redis_client:
        await asyncio.sleep(1)

    pubsub = redis_manager.redis_client.pubsub()
    await pubsub.subscribe("security_alerts")
    logger.info("[Engine Relay] Subscribed to 'security_alerts' Pub/Sub channel.")

    while True:
        try:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if message and message.get("data"):
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                alert_data = json.loads(raw)

                # Broadcast to frontend WebSocket clients
                ws_payload = {
                    "type": "NEW_DETECTION",
                    "data": {
                        "face_id": alert_data.get("person_id"),
                        "camera_id": alert_data.get("camera_id"),
                        "confidence": alert_data.get("score"),
                        "name": alert_data.get("name"),
                        "suspect_code": alert_data.get("suspect_code"),
                    },
                }
                await ws_manager.broadcast(ws_payload)

                # Push the original engine alert payload into the consumer stream.
                # The consumer expects the same schema the engine writes to
                # `alerts.global`, so keep that contract intact here.
                await redis_manager.redis_client.xadd(
                    "face_events", {"alert": raw}
                )

                logger.info(
                    "[Engine Relay] Alert forwarded: %s on %s",
                    alert_data.get("name"), alert_data.get("camera_id"),
                )
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error("[Engine Relay] Error: %s", e)
            await asyncio.sleep(2)


async def tracking_presence_relay():
    """
    Consumes lightweight live-location events from camera workers.
    This does not create alerts; it only updates active tracking sessions.
    """
    while not redis_manager.redis_client:
        await asyncio.sleep(1)

    pubsub = redis_manager.redis_client.pubsub()
    await pubsub.subscribe("tracking_presence")
    logger.info("[Tracking Relay] Subscribed to 'tracking_presence' Pub/Sub channel.")

    while True:
        try:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )
            if not message or not message.get("data"):
                await asyncio.sleep(0.05)
                continue

            raw = message["data"]
            if isinstance(raw, bytes):
                raw = raw.decode()
            presence = json.loads(raw)

            person_id = presence.get("person_id")
            camera_id = presence.get("camera_id")
            if person_id is None or not camera_id:
                continue

            confidence = presence.get("confidence", presence.get("score"))
            try:
                confidence = float(confidence) if confidence is not None else None
            except (TypeError, ValueError):
                confidence = None

            async with AsyncSessionLocal() as db:
                await update_tracking_for_detection(
                    db=db,
                    person_id=int(person_id),
                    camera_id=str(camera_id),
                    confidence=confidence,
                    detected_at=datetime.now(timezone.utc),
                    bbox=presence.get("bbox"),
                )
        except Exception as e:
            logger.error("[Tracking Relay] Error: %s", e)
            await asyncio.sleep(0.25)


# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting up API Service...")

    #  DB INIT
    await init_db()
    logger.info("Database initialized.")

    #  REDIS CONNECT (singleton manager used by cache + faces routes)
    await redis_manager.connect()

    await image_store.start()
    logger.info("Image storage workers started.")

    # Start Engine alert relay and live tracking relay as background tasks
    relay_task = asyncio.create_task(engine_alert_relay())
    tracking_relay_task = asyncio.create_task(tracking_presence_relay())
    logger.info("Engine alert relay started.")
    logger.info("Tracking presence relay started.")

    yield

    logger.info("Shutting down API Service...")

    relay_task.cancel()
    tracking_relay_task.cancel()
    await stream_hub.stop_all()
    await image_store.stop()
    await redis_manager.disconnect()


# ---------------- APP ----------------
app = FastAPI(
    title="AI Surveillance API",
    description="Backend microservice for facial recognition metadata and alert orchestration.",
    version="1.0.0",
    lifespan=lifespan
)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# ---------------- ROUTERS ----------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(faces.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(ws.router)
app.include_router(cameras.router)
app.include_router(reports.router)
app.include_router(system.router)
app.include_router(tracking.router)


# ---------------- ROOT ----------------
@app.get("/", tags=["Root"])
async def root():
    return {
        "status": "online",
        "message": "AI Surveillance System API is running. Visit /docs"
    }



# ---------------- LOCAL RUN ----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)
