"""
=============================================================================
SnapKey Remote Access - FastAPI Backend
=============================================================================
Manages connected local agents via WebSockets, accepts remote connection requests,
stores saved users/devices, and securely encrypts credentials.

IMPORTANT SECURITY/ETHICS CONSTRAINT:
This software does NOT include any logic that auto-clicks, screen-scrapes for,
or otherwise bypasses the "Accept" confirmation dialog that AnyDesk shows on
the machine being connected to. The remote person must always be able to
approve or deny the connection themselves. The only password-based flow this
project uses is AnyDesk's own documented `--with-password` flag for
unattended access, which only works if the target machine's owner has already
enabled unattended access themselves in their own AnyDesk settings.
=============================================================================
"""

import os
import subprocess
import base64
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional

import psutil
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Cryptography (Fernet Symmetric Encryption)
# ---------------------------------------------------------------------------
ENCRYPTION_KEY_RAW = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY_RAW:
    # Use a stable default valid key for local development
    # (32 bytes base64-encoded: "snapkey_dev_encryption_key_32_ch")
    ENCRYPTION_KEY_RAW = "c25hcGtleV9kZXZfZW5jcnlwdGlvbl9rZXlfMzJfY2g="

try:
    fernet = Fernet(ENCRYPTION_KEY_RAW.encode())
except Exception:
    print("WARNING: Invalid ENCRYPTION_KEY format. Generating a temporary random key.")
    fernet = Fernet(Fernet.generate_key())

def encrypt_password(password: str) -> str:
    if not password:
        return None
    return fernet.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> Optional[str]:
    if not encrypted:
        return None
    try:
        return fernet.decrypt(encrypted.encode()).decode()
    except Exception as e:
        print(f"Error decrypting password: {e}")
        return None

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapkey.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Normalize Render's "postgres://" to "postgresql+psycopg2://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, nullable=False)
    user_id = Column(String, unique=True, nullable=False, index=True)
    encrypted_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Create tables and apply small additive migrations for existing databases.
Base.metadata.create_all(bind=engine)


def ensure_database_schema() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        Base.metadata.create_all(bind=engine)
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "encrypted_password" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN encrypted_password VARCHAR"))


ensure_database_schema()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="SnapKey Remote Access API")

# Setup CORS with ALLOWED_ORIGINS
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ConnectRequest(BaseModel):
    user_name: str
    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        cleaned = v.replace(" ", "")
        if not cleaned.isdigit():
            raise ValueError("User ID must contain only numbers (AnyDesk ID)")
        return cleaned

class ConnectRequestPayload(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        cleaned = v.replace(" ", "")
        if not cleaned.isdigit():
            raise ValueError("User ID must contain only numbers (AnyDesk ID)")
        return cleaned

class ConnectResponse(BaseModel):
    status: str
    message: str
    anydesk_path: Optional[str] = None

class UserCreate(BaseModel):
    user_name: str
    user_id: str
    password: Optional[str] = None

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        cleaned = v.replace(" ", "")
        if not cleaned.isdigit():
            raise ValueError("User ID must contain only numbers (AnyDesk ID)")
        return cleaned

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_name: str
    user_id: str
    created_at: datetime

# ---------------------------------------------------------------------------
# AnyDesk discovery helpers (Windows machine only - skipped gracefully
# on Render, since Render containers are Linux and won't have AnyDesk)
# ---------------------------------------------------------------------------
COMMON_PATHS = [
    r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe",
    r"C:\Program Files\AnyDesk\AnyDesk.exe",
    r"C:\Users\Public\AnyDesk\AnyDesk.exe",
    r"C:\ProgramData\AnyDesk\AnyDesk.exe",
]

def find_anydesk_from_processes() -> Optional[str]:
    try:
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if proc.info["name"] and "anydesk" in proc.info["name"].lower():
                    if proc.info["exe"] and os.path.exists(proc.info["exe"]):
                        return proc.info["exe"]
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass
    return None

def find_anydesk_in_common_paths() -> Optional[str]:
    username = os.getenv("USERNAME", "")
    paths = list(COMMON_PATHS)
    if username:
        paths.extend([
            rf"C:\Users\{username}\AppData\Local\AnyDesk\AnyDesk.exe",
            rf"C:\Users\{username}\AppData\Roaming\AnyDesk\AnyDesk.exe",
        ])
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def find_anydesk_in_path() -> Optional[str]:
    try:
        result = subprocess.run(
            ["where", "AnyDesk.exe"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0]
            if path and os.path.exists(path):
                return path
    except Exception:
        pass
    return None

def find_anydesk_path() -> Optional[str]:
    return (
        find_anydesk_from_processes()
        or find_anydesk_in_common_paths()
        or find_anydesk_in_path()
    )

def is_anydesk_running() -> bool:
    try:
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "anydesk" in proc.info["name"].lower():
                return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# WebSocket Agent Connection Management (Token verification removed)
# ---------------------------------------------------------------------------
connected_agents: Dict[str, WebSocket] = {}

@app.websocket("/ws/agent")
async def websocket_agent(websocket: WebSocket):
    # Generate a simple connection ID for tracking
    connection_id = f"agent-{len(connected_agents) + 1}"

    await websocket.accept()
    connected_agents[connection_id] = websocket
    print(f"Agent connected: {connection_id}")
    try:
        while True:
            # Keep connection alive; discard any message from the agent
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"Agent disconnected: {connection_id}")
    finally:
        connected_agents.pop(connection_id, None)

# ---------------------------------------------------------------------------
# API Routes (Modified to not require agent tokens)
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Welcome to SnapKey Remote Access API. Please visit /docs for interactive documentation."}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/agents")
def list_agents():
    """Lists currently connected support agents."""
    return {"connected_agents": list(connected_agents.keys())}

@app.post("/api/connect-request")
async def connect_request(payload: ConnectRequestPayload):
    """
    Looks up the saved user's encrypted password, decrypts it, and
    sends a JSON connection command over the selected agent's WebSocket.
    """
    user_id = payload.user_id

    # Use the first connected agent (since we don't have tokens anymore)
    if not connected_agents:
        raise HTTPException(
            status_code=503,
            detail="No agents are currently connected."
        )

    # Get the first available agent
    agent_connection_id = next(iter(connected_agents))
    ws = connected_agents[agent_connection_id]

    try:
        with SessionLocal() as db:
            db_user = db.query(User).filter(User.user_id == user_id).first()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error while loading saved user: {e}")

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail=f"No saved user found with AnyDesk ID '{user_id}'."
        )

    password = decrypt_password(db_user.encrypted_password)

    command = {
        "action": "connect",
        "anydesk_id": user_id,
        "password": password
    }

    try:
        await asyncio.wait_for(ws.send_json(command), timeout=10)
    except asyncio.TimeoutError:
        connected_agents.pop(agent_connection_id, None)
        raise HTTPException(
            status_code=503,
            detail="Connected agent did not respond in time. Please restart the support agent."
        )
    except Exception as e:
        connected_agents.pop(agent_connection_id, None)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to transmit connection command to agent: {e}"
        )

    return {
        "status": "initiated",
        "message": f"Connection request sent to agent for AnyDesk ID '{user_id}'."
    }

@app.post("/api/connect", response_model=ConnectResponse)
def connect_legacy(req: ConnectRequest):
    """
    LEGACY ENDPOINT: Launches AnyDesk locally on the host machine running main.py.
    This works if main.py runs on a local Windows support PC, but does nothing on Render.
    """
    anydesk_path = find_anydesk_path()

    if not anydesk_path:
        raise HTTPException(
            status_code=404,
            detail=(
                "AnyDesk was not found on this local machine. "
                "(If this backend is running on Render, this endpoint cannot "
                "launch AnyDesk - please run/connect through an Agent instead.)"
            ),
        )

    try:
        if not is_anydesk_running():
            subprocess.Popen([anydesk_path])

        subprocess.Popen([anydesk_path, req.user_id])

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch AnyDesk: {e}")

    return ConnectResponse(
        status="initiated",
        message=(
            f"Legacy local connection initiated to {req.user_id}. "
            "Waiting for remote user to accept the connection."
        ),
        anydesk_path=anydesk_path,
    )

# ---------------------------------------------------------------------------
# User CRUD (saved devices/users) - works on Render via Postgres
# ---------------------------------------------------------------------------
@app.post("/api/users", response_model=UserOut)
def create_user(user: UserCreate):
    """Saves a user and encrypts their password using symmetric Fernet encryption."""
    with SessionLocal() as db:
        existing_user = db.query(User).filter(User.user_id == user.user_id).first()
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail=f"A user with User ID '{user.user_id}' already exists."
            )

        encrypted = encrypt_password(user.password) if user.password else None

        db_user = User(
            user_name=user.user_name,
            user_id=user.user_id,
            encrypted_password=encrypted,
        )

        db.add(db_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"A user with User ID '{user.user_id}' already exists.",
            )
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=503, detail=f"Database error while saving user: {e}")

        db.refresh(db_user)
        return db_user

@app.get("/api/users", response_model=list[UserOut])
def get_all_users():
    """Lists all saved remote users."""
    try:
        with SessionLocal() as db:
            return db.query(User).order_by(User.id.desc()).all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error while loading users: {e}")

@app.get("/api/users/{user_id}", response_model=UserOut)
def get_single_user(user_id: str):
    """Retrieves a single user by AnyDesk ID."""
    try:
        with SessionLocal() as db:
            db_user = db.query(User).filter(User.user_id == user_id).first()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail=f"Database error while loading user: {e}")

    if not db_user:
        raise HTTPException(status_code=404, detail=f"No user found with ID '{user_id}'.")

    return db_user

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
