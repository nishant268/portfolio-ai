from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select

import os as _os
_DATA_DIR = Path(_os.environ.get("DATA_DIR", Path(__file__).parent.parent.parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB = _DATA_DIR / "chat.db"
engine = create_engine(f"sqlite:///{_DB}", connect_args={"check_same_thread": False})


class ChatSession(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = "New Chat"
    mode: str = "investor"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ChatMessage(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(index=True)
    role: str          # "user" | "assistant"
    content: str
    sources_json: str = "{}"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


# ── helpers ───────────────────────────────────────────────────────────────────

def list_sessions() -> list[ChatSession]:
    with Session(engine) as s:
        return s.exec(select(ChatSession).order_by(ChatSession.updated_at.desc())).all()  # type: ignore[arg-type]


def get_session_by_id(sid: str) -> ChatSession | None:
    with Session(engine) as s:
        return s.get(ChatSession, sid)


def create_session(title: str = "New Chat", mode: str = "investor") -> ChatSession:
    sess = ChatSession(title=title, mode=mode)
    with Session(engine) as s:
        s.add(sess)
        s.commit()
        s.refresh(sess)
    return sess


def delete_session(sid: str) -> bool:
    with Session(engine) as s:
        sess = s.get(ChatSession, sid)
        if not sess:
            return False
        msgs = s.exec(select(ChatMessage).where(ChatMessage.session_id == sid)).all()
        for m in msgs:
            s.delete(m)
        s.delete(sess)
        s.commit()
    return True


def get_messages(sid: str) -> list[ChatMessage]:
    with Session(engine) as s:
        return s.exec(select(ChatMessage).where(ChatMessage.session_id == sid).order_by(ChatMessage.created_at)).all()  # type: ignore[arg-type]


def add_message(sid: str, role: str, content: str, sources: dict | None = None) -> ChatMessage:
    import json
    msg = ChatMessage(session_id=sid, role=role, content=content, sources_json=json.dumps(sources or {}))
    with Session(engine) as s:
        s.add(msg)
        # update session timestamp + auto-title from first user message
        sess = s.get(ChatSession, sid)
        if sess:
            sess.updated_at = datetime.utcnow().isoformat()
            if role == "user" and sess.title == "New Chat":
                sess.title = content[:50] + ("…" if len(content) > 50 else "")
            s.add(sess)
        s.commit()
        s.refresh(msg)
    return msg


def delete_message(mid: str) -> bool:
    with Session(engine) as s:
        msg = s.get(ChatMessage, mid)
        if not msg:
            return False
        s.delete(msg)
        s.commit()
    return True
