"""
API Tickets — FastAPI async
============================

Rôle : exposer une API REST pour le frontend Tickets, et publier sur Kafka
chaque événement d'authentification ou de métier.

Patterns :
    - JWT bearer auth (Keycloak signe, on vérifie via JWKS)
    - Tous les événements vont sur Kafka, jamais directement en DB
    - SQLAlchemy 2.0 async pour les opérations métier (tickets/comments)
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List

sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from auth import get_current_user
from kafka_client import KafkaPublisher

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("api-tickets")


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]


# -----------------------------------------------------------------------------
# Lifecycle (async): connecte Kafka et la DB au démarrage
# -----------------------------------------------------------------------------
publisher = KafkaPublisher()
engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting api-tickets...")
    await publisher.start()
    yield
    log.info("Shutting down api-tickets...")
    await publisher.stop()
    await engine.dispose()


app = FastAPI(
    title="PFE Tickets API",
    description="Application métier — produit les événements vers Kafka",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Schémas Pydantic
# -----------------------------------------------------------------------------
class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")


class Ticket(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    status: str
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


class AuthEventNotification(BaseModel):
    """Le frontend notifie l'API qu'un login s'est passé (côté client OIDC)."""
    event_type: str = Field(..., pattern="^(login_success|login_failed|logout)$")
    success: bool = True
    details: dict = {}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# -----------------------------------------------------------------------------
# Endpoints publics : santé
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-tickets"}


# -----------------------------------------------------------------------------
# Endpoint clé : notification d'événement d'auth → Kafka
# -----------------------------------------------------------------------------
@app.post("/api/auth/notify", status_code=202)
async def notify_auth_event(
    body: AuthEventNotification,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Le frontend appelle ce endpoint après un login réussi pour notifier le
    backend. L'API ne fait QUE publier sur Kafka — la persistance se fait
    dans event-persister.
    """
    await publisher.publish_auth_event(
        topic=KAFKA_TOPIC,
        event_type=body.event_type,
        username=user["username"],
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        success=body.success,
        details={**body.details, "app": "tickets"},
    )
    return {"status": "published"}


@app.post("/api/auth/failed", status_code=202)
async def notify_failed_login(
    request: Request,
    body: dict,
):
    """
    Endpoint NON authentifié pour notifier un login échoué (pas de JWT valide).
    Utilisé par le simulateur et par les tentatives ratées du frontend.
    """
    username = body.get("username", "unknown")
    await publisher.publish_auth_event(
        topic=KAFKA_TOPIC,
        event_type="login_failed",
        username=username,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        success=False,
        details=body.get("details", {}),
    )
    return {"status": "published"}


@app.post("/api/event-test", status_code=202)
async def event_test(request: Request, body: dict):
    """
    DEV ONLY : endpoint utilisé par le simulateur pour publier n'importe quel
    événement (succès, échec) sans authentification. À DÉSACTIVER en prod.
    """
    await publisher.publish_auth_event(
        topic=KAFKA_TOPIC,
        event_type=body.get("event_type", "login_success"),
        username=body.get("username", "unknown"),
        ip_address=body.get("ip_address") or client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        success=body.get("success", True),
        details=body.get("details", {}),
    )
    return {"status": "published"}


# -----------------------------------------------------------------------------
# Tickets : CRUD basique
# -----------------------------------------------------------------------------
@app.get("/api/tickets", response_model=List[Ticket])
async def list_tickets(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("""
        SELECT id, title, description, priority, status, created_by, created_at
        FROM tickets.tickets
        WHERE created_by = :uid
        ORDER BY created_at DESC LIMIT 50
    """), {"uid": user["sub"]})
    return [dict(r._mapping) for r in result]


@app.post("/api/tickets", response_model=Ticket, status_code=201)
async def create_ticket(
    body: TicketCreate,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("""
        INSERT INTO tickets.tickets (title, description, priority, created_by)
        VALUES (:title, :desc, :priority, :uid)
        RETURNING id, title, description, priority, status, created_by, created_at
    """), {
        "title": body.title, "desc": body.description,
        "priority": body.priority, "uid": user["sub"],
    })
    await db.commit()
    ticket = dict(result.one()._mapping)

    # Publie aussi cet événement métier sur Kafka pour traçabilité
    await publisher.publish_auth_event(
        topic=KAFKA_TOPIC,
        event_type="ticket_created",
        username=user["username"],
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        success=True,
        details={"ticket_id": ticket["id"], "priority": body.priority},
    )
    return ticket


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user
