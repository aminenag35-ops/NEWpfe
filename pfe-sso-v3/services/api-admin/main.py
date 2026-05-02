"""
API Admin — gestion users, audit, alertes
==========================================

Lecture pure depuis PostgreSQL (la base est alimentée par event-persister).
Permet aussi le blocage manuel d'un user ou d'une IP.
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
import redis.asyncio as redis

from auth import get_current_user, require_roles

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("api-admin")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]
CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]


engine = create_async_engine(DATABASE_URL, pool_size=5)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
redis_client: Optional[redis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await redis_client.close()
    await engine.dispose()


app = FastAPI(title="PFE Admin API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


async def get_db():
    async with SessionLocal() as s:
        yield s


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class User(BaseModel):
    id: int
    keycloak_id: str
    username: str
    email: Optional[str]
    is_blocked: bool
    blocked_at: Optional[datetime]
    blocked_reason: Optional[str]
    created_at: datetime


class BlockRequest(BaseModel):
    reason: str = "manual block by admin"


class AuthEvent(BaseModel):
    id: int
    event_type: str
    username: Optional[str]
    ip_address: Optional[str]
    success: Optional[bool]
    timestamp: datetime
    details: dict = {}


class Alert(BaseModel):
    id: int
    timestamp: datetime
    username: Optional[str]
    ip_address: Optional[str]
    alert_type: str
    severity: str
    score: Optional[float]
    details: dict = {}
    is_resolved: bool


class BlockedIP(BaseModel):
    ip: str
    ttl_seconds: int
    reason: str


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@app.get("/api/users", response_model=List[User])
async def list_users(
    _: dict = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text(
        "SELECT id, keycloak_id, username, email, is_blocked, "
        "blocked_at, blocked_reason, created_at FROM auth.users ORDER BY created_at DESC"
    ))
    return [dict(r._mapping) for r in result]


@app.post("/api/users/{user_id}/block")
async def block_user(
    user_id: int, body: BlockRequest,
    _: dict = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text(
        "UPDATE auth.users SET is_blocked = TRUE, blocked_at = NOW(), "
        "blocked_reason = :r WHERE id = :id"
    ), {"r": body.reason, "id": user_id})
    await db.commit()
    return {"status": "blocked"}


@app.post("/api/users/{user_id}/unblock")
async def unblock_user(
    user_id: int,
    _: dict = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text(
        "UPDATE auth.users SET is_blocked = FALSE, blocked_at = NULL, "
        "blocked_reason = NULL WHERE id = :id"
    ), {"id": user_id})
    await db.commit()
    return {"status": "unblocked"}


@app.get("/api/events", response_model=List[AuthEvent])
async def list_events(
    limit: int = 100,
    _: dict = Depends(require_roles("admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text(
        "SELECT id, event_type, username, ip_address, success, timestamp, "
        "COALESCE(details, '{}'::jsonb) AS details "
        "FROM auth.events ORDER BY timestamp DESC LIMIT :lim"
    ), {"lim": limit})
    return [dict(r._mapping) for r in result]


@app.get("/api/alerts", response_model=List[Alert])
async def list_alerts(
    limit: int = 50,
    _: dict = Depends(require_roles("admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text(
        "SELECT id, timestamp, username, ip_address, alert_type, severity, score, "
        "COALESCE(details, '{}'::jsonb) AS details, is_resolved "
        "FROM security.alerts ORDER BY timestamp DESC LIMIT :lim"
    ), {"lim": limit})
    return [dict(r._mapping) for r in result]


@app.get("/api/blocked-ips", response_model=List[BlockedIP])
async def list_blocked_ips(_: dict = Depends(require_roles("admin"))):
    blocked = []
    async for key in redis_client.scan_iter("blocked_ip:*"):
        ip = key.split(":", 1)[1]
        ttl = await redis_client.ttl(key)
        reason = await redis_client.get(key) or ""
        blocked.append({"ip": ip, "ttl_seconds": ttl, "reason": reason})
    return blocked


@app.delete("/api/blocked-ips/{ip}")
async def unblock_ip(ip: str, _: dict = Depends(require_roles("admin"))):
    deleted = await redis_client.delete(f"blocked_ip:{ip}")
    return {"deleted": bool(deleted)}


@app.get("/api/stats")
async def stats(
    _: dict = Depends(require_roles("admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """Statistiques agrégées pour le dashboard."""
    result = await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM auth.events WHERE timestamp >= NOW() - INTERVAL '24 hours') AS events_24h,
            (SELECT COUNT(*) FROM security.alerts WHERE timestamp >= NOW() - INTERVAL '24 hours') AS alerts_24h,
            (SELECT COUNT(DISTINCT ip_address) FROM auth.events WHERE timestamp >= NOW() - INTERVAL '24 hours') AS unique_ips_24h,
            (SELECT COUNT(*) FROM auth.users WHERE is_blocked) AS blocked_users
    """))
    row = result.one()._mapping
    return dict(row)
