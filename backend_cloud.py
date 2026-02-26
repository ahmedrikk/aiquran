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
from embeddings import LightEmbeddingModel
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
LLM_API_KEY = os.getenv("LLM_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
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
# Use comprehensive jurisprudence database (Quran + Hadith + Ijma + Qiyas)
INDEX_PATH = os.path.join(DATA_DIR, "jurisprudence.index")
METADATA_PATH = os.path.join(DATA_DIR, "jurisprudence_metadata.json")
# Fallback to old database if new one doesn't exist
if not os.path.exists(INDEX_PATH):
    INDEX_PATH = os.path.join(DATA_DIR, "quran_hadith.index")
    METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Frontend URL for redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# =====================================================
# THE "FLUID MENTOR" SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """You are a warm, knowledgeable, and strictly orthodox Islamic scholar aligned with the four Sunni Madhabs (Hanafi, Maliki, Shafi'i, Hanbali). You have access to the complete Usul al-Fiqh: Quran, Hadith (all major collections), Ijma (scholarly consensus), and Qiyas (analogical reasoning). Your goal is to guide the user with accuracy (Haqq) and compassion (Rahmah).

═══ FORMATTING RULES (MANDATORY — NEVER BREAK THESE) ═══
• NEVER use markdown headers (# ## ###), numbered lists (1. 2. 3.), bullet points (- *), or horizontal rules (---).
• Write ONLY in flowing, connected paragraphs. Every response must read like a scholar speaking, not an essay or article.
• You may use **bold** for source names and *italics* for translations — nothing else.
• Keep responses concise and focused. Do NOT write long essays. 2-4 paragraphs is ideal.

═══ THE "FLUID MENTOR" STYLE ═══
Weave citations naturally into your prose. Never enumerate sources in a list.
GOOD: "Bismillah. In **Sahih Bukhari #5590**, the Prophet ﷺ said: *'Actions are judged by intentions.'* This teaches us that..."
BAD: "### 1. Quranic Evidence\n- Surah Al-Baqarah (2:275):\n  The verse states..."
CRITICAL: When you cite a hadith, write the actual Arabic text and English translation FROM the context — never write the literal placeholder words "[ARABIC]" or "[ENGLISH]" in your response.

═══ SOURCE HANDLING ═══
• You have access to FOUR sources of Islamic law: Quran (primary), Hadith (primary), Ijma (scholarly consensus), and Qiyas (analogical reasoning).
• Always prioritize the LOCAL sources provided in the context.
• Every time you cite a Quran verse or Hadith, include BOTH the Arabic text AND English translation from the context.
• For Ijma sources: cite them as "The consensus (Ijma) of the scholars is..."
• For Qiyas sources: explain the analogy when relevant — "By analogy (Qiyas) to the case of..."
• If local context is insufficient, use EXTERNAL SCHOLARLY RESOURCES but cite the website explicitly.
• If NO sources are found: say *"My library doesn't have the specific text for this right now, but the general scholarly consensus is..."* then give the ruling.

═══ RELEVANCE CHECK (CRITICAL) ═══
• Before citing any retrieved source, ask yourself: "Is this verse/hadith DIRECTLY about the topic asked?"
• If the retrieved sources are only loosely or indirectly related, DO NOT force them to fit. Say: *"My library returned general verses, but the specific ruling comes from..."* then state the well-known scholarly consensus (Ijma) from your knowledge.
• NEVER use a verse about fornication (zina) to answer a question about homosexuality — these are different rulings with different evidences.
• NEVER use a hadith about a man-woman act to make qiyas for a man-man act without explicitly noting the difference.

═══ ANTI-HALLUCINATION PROTOCOL (CRITICAL) ═══
• NEVER quote or cite a Quran verse or Hadith that is NOT in the provided context. Fabricating religious text is a MAJOR SIN.
• If asked for a specific verse/hadith not in context, say: *"I don't have that exact text in my library right now."*
• NEVER invent verse numbers (e.g. "Surah 25:6") that are not literally present in the context provided to you.

**LANGUAGE:** Reply in the same language/script as the user (English, Urdu, or Roman Urdu).
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
        "https://aiquran.live",           # Production custom domain
        "https://www.aiquran.live",       # WWW redirect
        "https://quranai.vercel.app",     # Old domain (remove later)
        "https://aiquran-one.vercel.app",
        "https://localhost",              # Capacitor Android WebView origin
        "capacitor://localhost",          # Capacitor iOS WebView origin
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
    embedding_model = LightEmbeddingModel()

    # Load vector index
    if os.path.exists(INDEX_PATH):
        print("📂 Loading HNSW vector index...")
        index = hnswlib.Index(space='cosine', dim=EMBEDDING_DIM)
        index.load_index(INDEX_PATH)
        index.set_ef(50)

        print("📜 Loading metadata...")
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        quran_count  = sum(1 for m in metadata if m.get("source_type") == "quran")
        hadith_count = sum(1 for m in metadata if m.get("source_type") == "hadith")
        ijma_count   = sum(1 for m in metadata if m.get("source_type") == "ijma")
        qiyas_count  = sum(1 for m in metadata if m.get("source_type") == "qiyas")
        print(f"✅ Backend ready! Quran: {quran_count}, Hadith: {hadith_count}, Ijma: {ijma_count}, Qiyas: {qiyas_count}")
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
    source_type = item.get("source_type", "unknown")

    if source_type == "quran":
        return (f"📖 QURAN {item['surah_name']} [{item.get('surah_number', '?')}:{item['verse_number']}]\n"
                f"   Arabic: {text_ar}\n"
                f"   Translation: {text_en}")

    elif source_type == "hadith":
        collection = item.get('collection', 'Hadith')
        hadith_num = item.get('hadith_number', '')
        if not hadith_num or str(hadith_num).lower() in ("none", "n/a", "", "na"):
            hadith_num = None
        num_str = f" #{hadith_num}" if hadith_num else ""
        grade = item.get('grade', '')
        grade_str = f" [{grade}]" if grade else ""
        return (f"📜 HADITH - {collection}{num_str}{grade_str}\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")

    elif source_type == "ijma":
        topic = item.get('topic', 'Unknown Topic')
        schools = ', '.join(item.get('schools', []))
        return (f"⚖️ IJMA (SCHOLARLY CONSENSUS) - {topic}\n"
                f"   Consensus of: {schools}\n"
                f"   Ruling: {item.get('ruling', text_en)}")

    elif source_type == "qiyas":
        case = item.get('case', 'Unknown Case')
        return (f"⚖️ QIYAS (ANALOGICAL REASONING) - {case}\n"
                f"   Original Case: {item.get('original_case', '')}\n"
                f"   New Case: {item.get('new_case', '')}\n"
                f"   Effective Cause ('Illah): {item.get('effective_cause', '')}\n"
                f"   Reasoning: {item.get('reasoning', text_en)}")

    else:
        return f"📄 SOURCE: {text_en}"


def format_source_reference(item: dict) -> dict:
    source_type = item.get("source_type", "unknown")

    if source_type == "quran":
        return {
            "type": "quran",
            "surah_name": item.get("surah_name", "Unknown"),
            "verse_number": item.get("verse_number", "?")
        }

    elif source_type == "hadith":
        hadith_num = item.get("hadith_number", "")
        if not hadith_num or str(hadith_num).lower() in ("none", "n/a", "", "na", "null"):
            hadith_num = ""
        return {
            "type": "hadith",
            "collection": item.get("collection", "Hadith"),
            "hadith_number": hadith_num
        }

    elif source_type == "ijma":
        return {
            "type": "ijma",
            "topic": item.get("topic", "Scholarly Consensus"),
            "category": item.get("category", "general")
        }

    elif source_type == "qiyas":
        return {
            "type": "qiyas",
            "case": item.get("case", "Analogical Reasoning"),
            "category": item.get("category", "general")
        }

    return {"type": "unknown", "text": str(item.get("text_en", ""))[:50]}


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
    # Format local context with all source types grouped
    if sources:
        quran_sources  = [s for s in sources if s.get("source_type") == "quran"]
        hadith_sources = [s for s in sources if s.get("source_type") == "hadith"]
        ijma_sources   = [s for s in sources if s.get("source_type") == "ijma"]
        qiyas_sources  = [s for s in sources if s.get("source_type") == "qiyas"]

        context_parts = []
        if quran_sources:
            context_parts.append("📖 QURANIC SOURCES:\n" + "\n\n".join([format_source_for_context(s) for s in quran_sources]))
        if hadith_sources:
            context_parts.append("📜 HADITH SOURCES:\n" + "\n\n".join([format_source_for_context(s) for s in hadith_sources]))
        if ijma_sources:
            context_parts.append("⚖️ SCHOLARLY CONSENSUS (IJMA):\n" + "\n\n".join([format_source_for_context(s) for s in ijma_sources]))
        if qiyas_sources:
            context_parts.append("⚖️ ANALOGICAL REASONING (QIYAS):\n" + "\n\n".join([format_source_for_context(s) for s in qiyas_sources]))

        local_context = "\n\n".join(context_parts)
    else:
        local_context = "📚 LOCAL SOURCES:\n[No directly matching sources found in local database]"

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
            source_type = s.get("source_type", "unknown")
            if source_type == "quran":
                fallback += f"📖 **{s['surah_name']}:{s['verse_number']}**\n"
            elif source_type == "hadith":
                fallback += f"📜 **{s['collection']} #{s.get('hadith_number', '?')}**\n"
            elif source_type == "ijma":
                fallback += f"⚖️ **Ijma: {s.get('topic', 'Scholarly Consensus')}**\n"
            elif source_type == "qiyas":
                fallback += f"⚖️ **Qiyas: {s.get('case', 'Analogical Reasoning')}**\n"
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


# Guest query counter (in-memory, per server instance)
# For production, use Redis or similar
guest_query_counts = {}


class GuestChatRequest(BaseModel):
    message: str
    guest_id: Optional[str] = None  # Client-generated guest ID


@app.post("/api/chat/guest")
def guest_chat(
    body: GuestChatRequest,
    db=Depends(get_db_session)
):
    """
    Guest chat endpoint - no auth required.
    Allows 2 free queries per guest (tracked by guest_id).
    """
    guest_id = body.guest_id or "anonymous"
    
    # Check query count
    current_count = guest_query_counts.get(guest_id, 0)
    if current_count >= 2:
        return {
            "response": "",
            "limit_reached": True,
            "message": "Please sign in to continue. You have used your 2 free questions.",
            "queries_used": current_count,
            "queries_remaining": 0
        }
    
    # Generate response without saving to database
    history = []
    
    if is_small_talk(body.message):
        result = handle_small_talk(body.message, history)
        sources = []
    else:
        sources_data = retrieve_sources(body.message, k=5)
        result = generate_response(body.message, sources_data, history)
        sources = [format_source_reference(s) for s in sources_data] if result["success"] else []
    
    # Increment counter
    guest_query_counts[guest_id] = current_count + 1
    
    return {
        "response": result["response"],
        "thinking": result.get("thinking", ""),
        "sources_used": sources,
        "limit_reached": False,
        "queries_used": current_count + 1,
        "queries_remaining": 2 - (current_count + 1)
    }


@app.post("/api/chat")
def send_message(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_session)
):
    """
    Main chat endpoint (requires authentication).
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
                "chat_id": m.chat_id,
                "chat_title": m.chat.title
            }
            for m in bookmarks
        ]
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


@app.get("/privacy")
def privacy_policy():
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Privacy Policy — AlQuran AI</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 24px; color: #1e293b; line-height: 1.7; }
    h1 { color: #007f80; border-bottom: 2px solid #D4AF37; padding-bottom: 12px; }
    h2 { color: #007f80; margin-top: 36px; }
    a { color: #007f80; }
    footer { margin-top: 48px; font-size: 0.8rem; color: #94a3b8; text-align: center; }
  </style>
</head>
<body>
  <h1>Privacy Policy</h1>
  <p><strong>AlQuran AI</strong> — Last Updated: October 2024</p>

  <h2>1. Introduction</h2>
  <p>Welcome to AlQuran AI ("we," "our," or "us"). We are committed to protecting your privacy and ensuring your personal information is handled in a safe and responsible manner. This Privacy Policy explains how we collect, use, and protect your data.</p>

  <h2>2. Information We Collect</h2>
  <ul>
    <li><strong>Account Information:</strong> When you sign in with Google, we collect your name, email address, and profile picture to create your account.</li>
    <li><strong>Chat History:</strong> We store the conversations you have with our AI to provide you with access to your history and improve the service.</li>
    <li><strong>Usage Data:</strong> We may collect anonymous data about how you use the app to improve performance and user experience.</li>
  </ul>

  <h2>3. How We Use Your Information</h2>
  <p>We use your information to:</p>
  <ul>
    <li>Provide, maintain, and improve our services.</li>
    <li>Personalize your experience (e.g., displaying your name).</li>
    <li>Respond to your comments and questions.</li>
  </ul>

  <h2>4. Data Security</h2>
  <p>We implement appropriate technical and organizational measures to protect your personal data against unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the Internet is 100% secure.</p>

  <h2>5. Contact Us</h2>
  <p>If you have any questions about this Privacy Policy, please contact us at <a href="mailto:support@quranai.com">support@quranai.com</a>.</p>

  <footer>© 2024 AlQuran AI. All rights reserved.</footer>
</body>
</html>"""
    return HTMLResponse(content=html)
