"""
QuranAI Database Layer
SQLite + SQLAlchemy for users, chats, messages, and bookmarks.
"""

import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Boolean,
    Integer, ForeignKey, JSON, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quranai.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# =====================================================
# MODELS
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    picture = Column(Text, nullable=True)  # Google profile picture URL
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    preferred_language = Column(String(10), default="en")  # en, ar, ur
    theme = Column(String(10), default="light")  # light, dark
    created_at = Column(DateTime, default=utcnow)
    last_login = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan",
                         order_by="Chat.updated_at.desc()")
    bookmarks = relationship("Bookmark", back_populates="user", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), default="New Chat")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_archived = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan",
                            order_by="Message.created_at.asc()")

    __table_args__ = (
        Index("ix_chats_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)  # LLM reasoning (for assistant messages)
    sources = Column(JSON, nullable=True)  # List of source references
    is_bookmarked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    chat = relationship("Chat", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_chat_created", "chat_id", "created_at"),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="bookmarks")
    message = relationship("Message")

    __table_args__ = (
        Index("ix_bookmarks_user", "user_id"),
    )


# =====================================================
# DATABASE INITIALIZATION
# =====================================================

def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created.")


@contextmanager
def get_db():
    """Yield a database session, auto-close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# USER OPERATIONS
# =====================================================

def get_or_create_user(db, google_id: str, email: str, name: str, picture: str = None) -> User:
    """Find existing user by Google ID or create new one."""
    user = db.query(User).filter(User.google_id == google_id).first()

    if user:
        # Update last login and any changed profile info
        user.last_login = utcnow()
        user.name = name
        user.picture = picture
        user.email = email
        db.commit()
        db.refresh(user)
        return user

    # Create new user
    user = User(
        google_id=google_id,
        email=email,
        name=name,
        picture=picture,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# =====================================================
# CHAT OPERATIONS
# =====================================================

def create_chat(db, user_id: str, title: str = "New Chat") -> Chat:
    chat = Chat(user_id=user_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_user_chats(db, user_id: str, limit: int = 50, offset: int = 0, archived: bool = False):
    return (
        db.query(Chat)
        .filter(Chat.user_id == user_id, Chat.is_archived == archived)
        .order_by(Chat.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_chat_with_messages(db, chat_id: str, user_id: str) -> Chat | None:
    return (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == user_id)
        .first()
    )


def add_message(db, chat_id: str, role: str, content: str,
                thinking: str = None, sources: list = None) -> Message:
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        thinking=thinking,
        sources=sources,
    )
    db.add(msg)

    # Update chat's updated_at timestamp
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat:
        chat.updated_at = utcnow()

    db.commit()
    db.refresh(msg)
    return msg


def update_chat_title(db, chat_id: str, user_id: str, title: str):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if chat:
        chat.title = title
        db.commit()
    return chat


def delete_chat(db, chat_id: str, user_id: str) -> bool:
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if chat:
        db.delete(chat)
        db.commit()
        return True
    return False


def auto_title_from_message(content: str) -> str:
    """Generate a short title from the first user message."""
    clean = content.strip()
    if len(clean) <= 60:
        return clean
    return clean[:57] + "..."


# =====================================================
# BOOKMARK OPERATIONS
# =====================================================

def create_bookmark(db, user_id: str, message_id: str, note: str = None) -> Bookmark:
    bookmark = Bookmark(user_id=user_id, message_id=message_id, note=note)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


def get_user_bookmarks(db, user_id: str):
    return (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .all()
    )


def delete_bookmark(db, bookmark_id: str, user_id: str) -> bool:
    bm = db.query(Bookmark).filter(Bookmark.id == bookmark_id, Bookmark.user_id == user_id).first()
    if bm:
        db.delete(bm)
        db.commit()
        return True
    return False
