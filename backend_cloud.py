"""
Quran-Talk Backend API v5.0 — "Authenticated Scholar"
FastAPI with Google Auth, user profiles, chat persistence, and conversational RAG.
"""

import json
import os
import re
from datetime import datetime, timezone
from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Internal modules
from database import (
    init_db, get_db_session,
    get_or_create_user, get_user_by_id,
    create_chat, get_user_chats, get_chat_with_messages,
    add_message, update_chat_title, delete_chat, auto_title_from_message,
    create_bookmark, get_user_bookmarks, delete_bookmark,
    User, Chat, Message,
)
from auth import (
    GOOGLE_CLIENT_ID,
    GoogleAuthRequest, GoogleCodeRequest, TokenResponse,
    create_access_token, verify_google_id_token, exchange_google_code,
    get_current_user, get_optional_user, get_google_auth_url,
)

# =====================================================
# LLM PROVIDER (Cloud-based)
# =====================================================
# Supports: groq, together, openai — configure via env vars

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # groq | together | openai
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")  # default for Groq
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

# Auto-set base URLs if not provided
if not LLM_BASE_URL:
    if LLM_PROVIDER == "groq":
        LLM_BASE_URL = "https://api.groq.com/openai/v1"
    elif LLM_PROVIDER == "together":
        LLM_BASE_URL = "https://api.together.xyz/v1"
    elif LLM_PROVIDER == "openai":
        LLM_BASE_URL = "https://api.openai.com/v1"

# Use OpenAI-compatible client for all providers
from openai import OpenAI

llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL) if LLM_API_KEY else None


# =====================================================
# CONFIGURATION
# =====================================================
DATA_DIR = os.getenv("DATA_DIR", "./quran_data")
INDEX_PATH = os.path.join(DATA_DIR, "quran_hadith.index")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Frontend URL for redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# =====================================================
# THE "FLUID MENTOR" SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """You are a warm, knowledgeable, and strictly orthodox Islamic scholar named Quran-Talk. Your goal is to guide the user with accuracy (Haqq) and compassion (Rahmah), speaking in a natural, fluid narrative.

**YOUR CONVERSATIONAL STYLE (The "Fluid Mentor"):**
1. **No Headers:** Do not use bold headers like "The Evidence" or "The Ruling." Write in clear, connected paragraphs.
2. **The "Weave" Technique:**
   - Embed citations naturally.
   - **Example:** "Bismillah. Regarding your question, the consensus of the scholars is that this is not permitted. This is based on the narration in **Sahih Bukhari [#5590]** where the Prophet (saw) said: **[ARABIC TEXT]** meaning *"[ENGLISH TRANSLATION]"*. This teaches us that..."
3. **Handling Sources:**
   - **Priority:** Always prioritize the "LOCAL QURAN/HADITH" context first.
   - **Web Fallback:** If local context is empty, use the "EXTERNAL SCHOLARLY RESOURCES" but explicitly cite the website.
   - **Missing Data:** If NO sources are found, state: *"My library doesn't have the specific text for this right now, but the general consensus is..."*
4. **Tone:** Use "We," "Our tradition," and be gentle but firm on Haram/Halal boundaries.

**LANGUAGE:**
- Reply in the same language/script as the user (English, Urdu, or Roman Urdu).
"""


# =====================================================
# REQUEST / RESPONSE MODELS
# =====================================================

class ChatMessageRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None  # None = create new chat


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    preferred_language: Optional[str] = None
    theme: Optional[str] = None


class UpdateChatTitleRequest(BaseModel):
    title: str


class BookmarkRequest(BaseModel):
    message_id: str
    note: Optional[str] = None


# Legacy (unauthenticated) request model for backward compat
class LegacyChatRequest(BaseModel):
    query: str
    history: Optional[list[dict]] = []
    think_mode: Optional[bool] = True


# =====================================================
# SMALL TALK DETECTION
# =====================================================
GREETING_PATTERNS = [
    r'^(hi|hello|hey|howdy|hiya|greetings|salaam|assalamu alaikum|salam)[\s!?.]*$',
    r'^(good\s*(morning|afternoon|evening|day))[\s!?.]*$',
    r'^(how\s*are\s*you|how\'?s\s*it\s*going|what\'?s\s*up|sup)[\s!?.]*$',
    r'^(thanks|thank\s*you|thx)[\s!?.]*$',
    r'^(bye|goodbye|see\s*you|take\s*care)[\s!?.]*$',
]


def is_small_talk(query: str) -> bool:
    normalized = query.lower().strip()
    return any(re.match(p, normalized, re.IGNORECASE) for p in GREETING_PATTERNS)


# =====================================================
# RESPONSE PARSING
# =====================================================
def parse_thinking_response(response: str) -> tuple[str, str]:
    think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
    if think_match:
        thinking = think_match.group(1).strip()
        answer = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
    else:
        thinking = ""
        answer = response.strip()
    return thinking, answer


# =====================================================
# LLM CALL (Cloud Provider via OpenAI-compatible API)
# =====================================================
def call_llm(prompt: str, system: str = None) -> tuple[str, str]:
    """Call the cloud LLM and return (thinking, answer)."""
    if not llm_client:
        raise Exception("LLM not configured. Set LLM_API_KEY environment variable.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.6,
            max_tokens=2048,
        )
        full_response = response.choices[0].message.content.strip()
        thinking, answer = parse_thinking_response(full_response)
        return thinking, answer
    except Exception as e:
        raise Exception(f"LLM error: {str(e)}")


# =====================================================
# FASTAPI APP
# =====================================================
app = FastAPI(
    title="Quran-Talk API",
    description="Authenticated Islamic Scholar — Quran & Hadith with Google Auth",
    version="5.0.0"
)

_extra_origin = os.getenv("FRONTEND_URL", "")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://quranai.vercel.app",
        *( [_extra_origin] if _extra_origin else [] ),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# STARTUP: Load models, data, init DB
# =====================================================
embedding_model = None
index = None
metadata = None
quran_count = 0
hadith_count = 0


@app.on_event("startup")
def startup():
    global embedding_model, index, metadata, quran_count, hadith_count

    # Initialize database
    init_db()

    # Load embedding model
    print("🧠 Loading sentence transformer model...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)

    # Load vector index
    if os.path.exists(INDEX_PATH):
        print("📂 Loading HNSW vector index...")
        index = hnswlib.Index(space='cosine', dim=EMBEDDING_DIM)
        index.load_index(INDEX_PATH)
        index.set_ef(50)

        print("📜 Loading metadata...")
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        quran_count = sum(1 for m in metadata if m.get("source_type") == "quran")
        hadith_count = sum(1 for m in metadata if m.get("source_type") == "hadith")
        print(f"✅ Backend ready! Quran: {quran_count}, Hadith: {hadith_count}")
    else:
        print("⚠️ Vector index not found. Run build_db.py first.")
        metadata = []

    # LLM status
    if llm_client:
        print(f"🤖 LLM Provider: {LLM_PROVIDER} | Model: {LLM_MODEL}")
    else:
        print("⚠️ No LLM API key configured. Set LLM_API_KEY.")


# =====================================================
# RETRIEVAL FUNCTIONS
# =====================================================
def retrieve_sources(query: str, k: int = 5) -> list[dict]:
    if not index or not metadata:
        return []
    query_embedding = embedding_model.encode([query]).astype('float32')
    labels, distances = index.knn_query(query_embedding, k=k)
    return [metadata[idx] for idx in labels[0]]


def format_source_for_context(item: dict) -> str:
    text_ar = item.get('text_ar') or "[Arabic unavailable]"
    text_en = item.get('text_en') or "[English unavailable]"

    if item.get("source_type") == "quran":
        return (f"📖 Quran {item['surah_name']} [{item.get('surah_number', '?')}:{item['verse_number']}]\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")
    else:
        return (f"📜 {item['collection']} Hadith #{item['hadith_number']}\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")


def format_source_reference(item: dict) -> dict:
    if item.get("source_type") == "quran":
        return {"type": "quran", "surah_name": item["surah_name"], "verse_number": item["verse_number"]}
    else:
        return {"type": "hadith", "collection": item["collection"], "hadith_number": item["hadith_number"]}


def format_history_for_prompt(messages: list) -> str:
    """Format message history for the LLM prompt."""
    if not messages:
        return ""
    formatted = "PREVIOUS CONVERSATION:\n"
    for msg in messages[-6:]:
        role = "User" if msg.get("role") == "user" else "Scholar"
        content = msg.get("content", "")[:500]
        formatted += f"{role}: {content}\n"
    return formatted + "\n"


# =====================================================
# RESPONSE GENERATION
# =====================================================
def generate_response(query: str, sources: list[dict], history: list[dict]) -> dict:
    if sources:
        local_context = "📚 LOCAL QURAN/HADITH SOURCES:\n" + "\n\n".join(
            [format_source_for_context(s) for s in sources]
        )
    else:
        local_context = "📚 LOCAL QURAN/HADITH SOURCES:\n[No directly matching sources found]"

    history_text = format_history_for_prompt(history)

    user_prompt = f"""{history_text}{local_context}

CURRENT QUESTION: {query}

Respond as the Fluid Mentor, weaving citations naturally into your answer."""

    try:
        thinking, answer = call_llm(user_prompt, system=SYSTEM_PROMPT)
        if answer:
            return {"response": answer, "thinking": thinking, "success": True}
        raise Exception("Empty response")
    except Exception as e:
        fallback = "Bismillah. Here are the most relevant sources:\n\n"
        for s in sources:
            if s.get("source_type") == "quran":
                fallback += f"📖 **{s['surah_name']}:{s['verse_number']}**\n"
            else:
                fallback += f"📜 **{s['collection']} #{s['hadith_number']}**\n"
            text_en = s.get('text_en', '')
            text = text_en[:400] + "..." if len(text_en) > 400 else text_en
            fallback += f"> {text}\n\n"
        return {"response": fallback, "thinking": "", "success": False}


def handle_small_talk(query: str, history: list[dict]) -> dict:
    history_text = format_history_for_prompt(history)
    prompt = f"{history_text}User: {query}"
    system = ("You are Quran-Talk, a warm and friendly Islamic scholar. "
              "Be conversational. Start with 'Assalamu Alaikum' if appropriate.")
    try:
        thinking, answer = call_llm(prompt, system=system)
        return {"response": answer or "Assalamu Alaikum! How can I help you today?",
                "thinking": thinking, "success": True}
    except Exception:
        return {"response": "Assalamu Alaikum! 🌙 How can I help?",
                "thinking": "", "success": False}


# =====================================================
# AUTH ENDPOINTS
# =====================================================

@app.get("/auth/google/url")
def auth_google_url():
    """Return the Google OAuth2 consent URL for the frontend to redirect to."""
    return {"url": get_google_auth_url()}


@app.post("/auth/google", response_model=TokenResponse)
async def auth_google_id_token(request: GoogleAuthRequest, db=Depends(get_db_session)):
    """
    Authenticate with a Google ID token (from 'Sign in with Google' button).
    Frontend sends the credential/id_token; we verify and issue a JWT.
    """
    google_info = await verify_google_id_token(request.credential)

    user = get_or_create_user(
        db,
        google_id=google_info["google_id"],
        email=google_info["email"],
        name=google_info["name"],
        picture=google_info.get("picture"),
    )

    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "preferred_language": user.preferred_language,
            "theme": user.theme,
        }
    )


@app.post("/auth/google/code", response_model=TokenResponse)
async def auth_google_code(request: GoogleCodeRequest, db=Depends(get_db_session)):
    """
    Authenticate with a Google authorization code (server-side flow).
    """
    google_info = await exchange_google_code(request.code)

    user = get_or_create_user(
        db,
        google_id=google_info["google_id"],
        email=google_info["email"],
        name=google_info["name"],
        picture=google_info.get("picture"),
    )

    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "preferred_language": user.preferred_language,
            "theme": user.theme,
        }
    )


@app.get("/auth/google/callback")
async def auth_google_callback(code: str, state: str = "", db=Depends(get_db_session)):
    """
    OAuth2 callback — browser redirects here after Google consent.
    Exchanges code, creates/fetches user, redirects to frontend with token.
    """
    google_info = await exchange_google_code(code)

    user = get_or_create_user(
        db,
        google_id=google_info["google_id"],
        email=google_info["email"],
        name=google_info["name"],
        picture=google_info.get("picture"),
    )

    token = create_access_token(user.id)
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={token}")


# =====================================================
# USER PROFILE ENDPOINTS
# =====================================================

@app.get("/api/me")
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
        "preferred_language": current_user.preferred_language,
        "theme": current_user.theme,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@app.patch("/api/me")
def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Update user profile settings."""
    if body.name is not None:
        current_user.name = body.name
    if body.preferred_language is not None:
        current_user.preferred_language = body.preferred_language
    if body.theme is not None:
        current_user.theme = body.theme
    db.commit()
    db.refresh(current_user)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
        "preferred_language": current_user.preferred_language,
        "theme": current_user.theme,
    }


# =====================================================
# CHAT ENDPOINTS (Authenticated)
# =====================================================

@app.get("/api/chats")
def list_chats(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """List user's chats (sidebar data)."""
    chats = get_user_chats(db, current_user.id, limit=limit, offset=offset)
    return {
        "chats": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "message_count": len(c.messages),
            }
            for c in chats
        ]
    }


@app.get("/api/chats/{chat_id}")
def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Get a specific chat with all messages."""
    chat = get_chat_with_messages(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at.isoformat() if chat.created_at else None,
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "thinking": m.thinking,
                "sources": m.sources,
                "is_bookmarked": m.is_bookmarked,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in chat.messages
        ]
    }


@app.post("/api/chats/{chat_id}/messages")
def send_message_to_chat(
    chat_id: str,
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Send a message in an existing chat."""
    chat = get_chat_with_messages(db, chat_id, current_user.id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return _process_message(db, chat, body.message)


@app.post("/api/chat")
def send_message(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    Main chat endpoint.
    If chat_id is provided, continues that chat.
    If not, creates a new chat.
    Returns the assistant response + chat_id.
    """
    if body.chat_id:
        chat = get_chat_with_messages(db, body.chat_id, current_user.id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
    else:
        # Create new chat, auto-title from first message
        title = auto_title_from_message(body.message)
        chat = create_chat(db, current_user.id, title=title)

    return _process_message(db, chat, body.message)


def _process_message(db, chat: Chat, user_message: str) -> dict:
    """Core message processing — save user msg, generate response, save assistant msg."""
    # Save user message
    user_msg_obj = add_message(db, chat.id, role="user", content=user_message)

    # Build history from saved messages
    history = [
        {"role": m.role, "content": m.content}
        for m in chat.messages[-6:]
    ]

    # Generate response
    if is_small_talk(user_message):
        result = handle_small_talk(user_message, history)
        sources = []
    else:
        sources_data = retrieve_sources(user_message, k=5)
        result = generate_response(user_message, sources_data, history)
        sources = [format_source_reference(s) for s in sources_data] if result["success"] else []

    # Save assistant message
    msg = add_message(db, chat.id, role="assistant", content=result["response"])

    return {
        "response": result["response"],
        "chat_id": str(chat.id),
        "message_id": str(msg.id),
        "user_message_id": str(user_msg_obj.id),
        "thinking": result.get("thinking", ""),
        "sources_used": sources,
        "is_bookmarked": False
    }


# =====================================================
# BOOKMARK ENDPOINTS
# =====================================================

@app.post("/api/messages/{message_id}/bookmark")
def toggle_bookmark(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Toggle the bookmark status of a message."""
    # Logic to find message and toggle is_bookmarked
    # We need a helper for this or do it inline
    # Since we didn't add a specific helper in database.py yet, let's do it via session here
    # or better, let's look up the message.
    
    # We need to verify ownership!
    # Message -> Conversation -> User
    
    message = db.query(Message).join(Chat).filter(
        Message.id == message_id,
        Chat.user_id == current_user.id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
        
    message.is_bookmarked = not message.is_bookmarked
    db.commit()
    
    return {"message_id": message_id, "is_bookmarked": message.is_bookmarked}


@app.get("/api/bookmarks")
def get_bookmarks(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Get all bookmarked messages for the user."""
    # Join Message -> Chat -> User
    bookmarks = db.query(Message).join(Chat).filter(
        Chat.user_id == current_user.id,
        Message.is_bookmarked == True
    ).order_by(Message.created_at.desc()).limit(limit).offset(offset).all()
    
    return {
        "bookmarks": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "chat_id": m.conversation_id,
                "chat_title": m.conversation.title
            }
            for m in bookmarks
        ]
    }

    assistant_msg = add_message(
        db, chat.id,
        role="assistant",
        content=result["response"],
        thinking=result.get("thinking"),
        sources=sources,
    )

    return {
        "chat_id": chat.id,
        "message_id": assistant_msg.id,
        "response": result["response"],
        "thinking": result.get("thinking", ""),
        "sources_used": sources,
    }


@app.patch("/api/chats/{chat_id}")
def rename_chat(
    chat_id: str,
    body: UpdateChatTitleRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Rename a chat."""
    chat = update_chat_title(db, chat_id, current_user.id, body.title)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"id": chat.id, "title": chat.title}


@app.delete("/api/chats/{chat_id}")
def remove_chat(
    chat_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """Delete a chat and all its messages."""
    if delete_chat(db, chat_id, current_user.id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Chat not found")





# =====================================================
# LEGACY ENDPOINTS (unauthenticated, backward compat)
# =====================================================

@app.post("/chat")
def legacy_chat(request: LegacyChatRequest):
    """Legacy chat endpoint (no auth) — backward compatible."""
    query = request.query
    history = request.history or []

    if is_small_talk(query):
        result = handle_small_talk(query, history)
        return {"response": result["response"], "thinking": result["thinking"], "sources_used": []}

    sources = retrieve_sources(query, k=5)
    result = generate_response(query, sources, history)

    return {
        "response": result["response"],
        "thinking": result["thinking"],
        "sources_used": [format_source_reference(s) for s in sources] if result["success"] else []
    }


# =====================================================
# HEALTH & STATUS
# =====================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Quran-Talk API v5.0 — Authenticated Scholar",
        "quran_verses": quran_count,
        "hadith_count": hadith_count,
        "total_indexed": len(metadata) if metadata else 0,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "auth_enabled": bool(GOOGLE_CLIENT_ID),
        "features": [
            "Google Auth",
            "User Profiles",
            "Chat Persistence",
            "Bookmarks",
            "Cloud LLM",
            "RAG (Quran + Hadith)",
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok"}
