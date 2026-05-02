"""
API Dashboard — supervision temps réel
=======================================

Deux fonctionnalités principales :
    1. REST : endpoints de stats + liste des alertes
    2. WebSocket : push des nouvelles alertes au fur et à mesure qu'elles
       arrivent sur le topic Kafka security.alerts

L'API consomme Kafka dans une task asyncio en arrière-plan, et broadcast à
tous les clients WS connectés.
"""
import os
import sys
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import List, Set, Optional
from datetime import datetime

sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from auth import get_current_user, require_roles, verify_token
from kafka_client import make_consumer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("api-dashboard")

DATABASE_URL = os.environ["DATABASE_URL"]
KAFKA_TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "security.alerts")
CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]

engine = create_async_engine(DATABASE_URL, pool_size=5)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# -----------------------------------------------------------------------------
# Gestionnaire de connexions WebSocket
# -----------------------------------------------------------------------------
class ConnectionManager:
    """Maintient l'ensemble des WebSocket connectés et broadcast à tous."""
    def __init__(self):
        self.active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        log.info("WS client connected (total=%d)", len(self.active))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self.active.discard(ws)
        log.info("WS client disconnected (total=%d)", len(self.active))

    async def broadcast(self, message: dict):
        """Envoie le message à tous les clients connectés."""
        if not self.active:
            return
        dead = []
        async with self._lock:
            for ws in self.active:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    log.warning("WS send failed: %s", e)
                    dead.append(ws)
            for ws in dead:
                self.active.discard(ws)


manager = ConnectionManager()


# -----------------------------------------------------------------------------
# Task background : Kafka consumer → broadcast WebSocket
# -----------------------------------------------------------------------------
async def kafka_to_websocket_pump():
    """
    Tourne en boucle infinie. Consume Kafka et push aux clients WS.
    """
    consumer = make_consumer(KAFKA_TOPIC_ALERTS, group_id="dashboard-ws-v3")
    await consumer.start()
    log.info("Kafka WS pump started on topic %s", KAFKA_TOPIC_ALERTS)
    try:
        async for msg in consumer:
            log.info("Pushing alert to %d clients", len(manager.active))
            await manager.broadcast(msg.value)
    except Exception as e:
        log.exception("Pump crashed: %s", e)
    finally:
        await consumer.stop()


# -----------------------------------------------------------------------------
# Lifecycle
# -----------------------------------------------------------------------------
pump_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pump_task
    pump_task = asyncio.create_task(kafka_to_websocket_pump())
    yield
    pump_task.cancel()
    try:
        await pump_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(title="PFE Dashboard API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


async def get_db():
    async with SessionLocal() as s:
        yield s


# -----------------------------------------------------------------------------
# Endpoints REST
# -----------------------------------------------------------------------------
class Alert(BaseModel):
    id: int
    timestamp: datetime
    username: Optional[str]
    ip_address: Optional[str]
    alert_type: str
    severity: str
    score: Optional[float]
    details: dict = {}


@app.get("/health")
async def health():
    return {"status": "ok", "ws_clients": len(manager.active)}


@app.get("/api/alerts", response_model=List[Alert])
async def list_alerts(
    limit: int = 50,
    _: dict = Depends(require_roles("admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text(
        "SELECT id, timestamp, username, ip_address, alert_type, severity, score, "
        "COALESCE(details, '{}'::jsonb) AS details "
        "FROM security.alerts ORDER BY timestamp DESC LIMIT :lim"
    ), {"lim": limit})
    return [dict(r._mapping) for r in result]


@app.get("/api/stats")
async def stats(
    _: dict = Depends(require_roles("admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("""
        SELECT alert_type, severity, COUNT(*) AS count
        FROM security.alerts
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        GROUP BY alert_type, severity
        ORDER BY count DESC
    """))
    return [dict(r._mapping) for r in result]


# -----------------------------------------------------------------------------
# WebSocket : token passé en query string (les WS browser ne supportent pas
# les headers Authorization sans gymnastique)
# -----------------------------------------------------------------------------
@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket, token: str = Query(...)):
    """
    Le client se connecte avec ws://host/ws/alerts?token=JWT
    On vérifie le JWT, on ajoute le client au pool, on attend la déconnexion.
    """
    try:
        verify_token(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await manager.connect(websocket)
    try:
        while True:
            # On attend juste la déconnexion. Le serveur push, le client ne dit rien.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
