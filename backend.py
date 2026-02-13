"""
Quran-Talk Backend API - "Connected Scholar" Edition
FastAPI with conversational RAG for Quran and Hadith.
Features: ChatOllama, DuckDuckGo web fallback, Fluid Mentor persona.
"""

import json
import os
import re
import time
import uuid
import random
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
from typing import Optional

# LangChain Ollama
from langchain_ollama import ChatOllama

# DuckDuckGo Search
from duckduckgo_search import DDGS


# =====================================================
# CONFIGURATION
# =====================================================
DATA_DIR = "./quran_data"
INDEX_PATH = os.path.join(DATA_DIR, "quran_hadith.index")
METADATA_PATH = os.path.join(DATA_DIR, "metadata.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Ollama LLM - Using /no_think by default for faster responses
llm = ChatOllama(
    model="qwen3:8b",
    base_url="http://localhost:11434",
    temperature=0.6
)

# =====================================================
# THE "FLUID MENTOR" SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """You are a warm, knowledgeable, and strictly orthodox Islamic scholar (aligned with the four Sunni Madhabs). Your goal is to guide the user with accuracy (Haqq) and compassion (Rahmah).

═══ FORMATTING RULES (MANDATORY — NEVER BREAK THESE) ═══
• NEVER use markdown headers (# ## ###), numbered lists (1. 2. 3.), bullet points (- *), or horizontal rules (---).
• Write ONLY in flowing, connected paragraphs. Every response must read like a scholar speaking, not an essay or article.
• You may use **bold** for source names and *italics* for translations — nothing else.
• Keep responses concise and focused. Do NOT write long essays. 2-4 paragraphs is ideal.

═══ THE "FLUID MENTOR" STYLE ═══
Weave citations naturally into your prose. Never enumerate sources in a list.
GOOD: "Bismillah. Regarding your question, the consensus of the scholars is clear on this matter. In **Sahih Bukhari [#5590]**, the Prophet ﷺ said: **[ARABIC]** meaning *'[ENGLISH]'*. This teaches us that..."
BAD: "### 1. Quranic Evidence\n- Surah Al-Baqarah (2:275):\n  The verse states..."

═══ SOURCE HANDLING ═══
• Always prioritize the LOCAL QURAN/HADITH context provided to you.
• If local context is insufficient, use EXTERNAL SCHOLARLY RESOURCES but cite the website explicitly (e.g., "According to a ruling referenced from IslamQA...").
• If NO sources are found: say *"My library doesn't have the specific text for this right now, but the general scholarly consensus is..."* then give the ruling from consensus.

═══ ANTI-HALLUCINATION PROTOCOL (CRITICAL) ═══
• NEVER quote or cite a Quran verse or Hadith that is NOT in the provided context. Fabricating religious text is a MAJOR SIN.
• NEVER invent Arabic text, Hadith numbers, or verse references.
• For established rulings with scholarly consensus (Ijma), state them clearly as Haram or Halal. Do NOT present false balance or "modern reinterpretations" that contradict the consensus of the four Madhabs.
• Accuracy ALWAYS takes priority over being diplomatic.

═══ TONE & LANGUAGE ═══
• Warm, conversational: use "We," "Our tradition," "Brother/Sister."
• Be gentle but FIRM on Haram/Halal boundaries.
• Reply in the same language/script as the user (English, Urdu, Roman Urdu, Arabic).
"""


# =====================================================
# REQUEST MODELS
# =====================================================
class ChatRequest(BaseModel):
    query: str
    history: Optional[list[dict]] = []


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
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, normalized, re.IGNORECASE):
            return True
    return False


# =====================================================
# WEB SEARCH FUNCTION (DuckDuckGo)
# =====================================================
def search_orthodox_web(query: str, max_results: int = 3) -> str:
    """Search the web for orthodox Islamic rulings."""
    try:
        search_query = f"{query} Islamic ruling orthodox sunni"
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=max_results))
        
        if not results:
            return ""
        
        formatted = "🌐 EXTERNAL SCHOLARLY RESOURCES:\n"
        for i, r in enumerate(results, 1):
            title = r.get('title', 'No Title')
            body = r.get('body', '')[:200]
            href = r.get('href', '')
            formatted += f"\n[{i}] {title}\n    {body}...\n    Source: {href}\n"
        
        return formatted
    except Exception as e:
        print(f"Web search error: {e}")
        return ""


# =====================================================
# LLM CALL (Using LangChain ChatOllama)
# =====================================================
def call_llm(prompt: str, system: str = None) -> str:
    """Call the LLM and return the response.
    
    Args:
        prompt: The user prompt
        system: System prompt (optional)
    """
    messages = []
    if system:
        messages.append(("system", system))
    
    # Always use /no_think for faster responses without reasoning
    final_prompt = prompt + " /no_think"
    messages.append(("human", final_prompt))
    
    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        raise Exception(f"LLM error: {str(e)}")


# =====================================================
# FASTAPI INITIALIZATION
# =====================================================
app = FastAPI(
    title="Quran-Talk API",
    description="Connected Scholar - Conversational Quran & Hadith with Web Fallback",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# LOAD MODELS AND DATA
# =====================================================
print("🧠 Loading sentence transformer model...")
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

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


# =====================================================
# RETRIEVAL FUNCTIONS
# =====================================================
def retrieve_sources(query: str, k: int = 5) -> list[dict]:
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


def format_history_for_prompt(history: list[dict]) -> str:
    if not history:
        return ""
    
    formatted = "PREVIOUS CONVERSATION:\n"
    for msg in history[-6:]:
        role = "User" if msg.get("role") == "user" else "Scholar"
        content = msg.get("content", "")[:500]
        formatted += f"{role}: {content}\n"
    formatted += "\n"
    return formatted


# =====================================================
# RESPONSE GENERATION (with Web Fallback)
# =====================================================
def generate_response(query: str, sources: list[dict], history: list[dict]) -> dict:
    # Format local context
    if sources:
        local_context = "📚 LOCAL QURAN/HADITH SOURCES:\n" + "\n\n".join([format_source_for_context(s) for s in sources])
    else:
        local_context = "📚 LOCAL QURAN/HADITH SOURCES:\n[No directly matching sources found in local database]"
    
    # Web fallback if local sources are weak
    web_context = ""
    if len(sources) < 2:
        web_context = search_orthodox_web(query)
    
    history_text = format_history_for_prompt(history)
    
    user_prompt = f"""{history_text}{local_context}

{web_context}

CURRENT QUESTION: {query}

Respond as the Fluid Mentor, weaving citations naturally into your answer."""

    try:
        answer = call_llm(user_prompt, system=SYSTEM_PROMPT)
        if answer:
            return {"response": answer, "success": True}
        raise Exception("Empty response")
    except Exception as e:
        # Fallback: just show sources
        fallback = "Bismillah. Here are the most relevant sources:\n\n"
        for s in sources:
            if s.get("source_type") == "quran":
                fallback += f"📖 **{s['surah_name']}:{s['verse_number']}**\n"
            else:
                fallback += f"📜 **{s['collection']} #{s['hadith_number']}**\n"
            
            text_en = s.get('text_en', '')
            text = text_en[:400] + "..." if len(text_en) > 400 else text_en
            fallback += f"> {text}\n\n"
        return {"response": fallback, "success": False}


def handle_small_talk(query: str, history: list[dict]) -> dict:
    history_text = format_history_for_prompt(history)
    prompt = f"{history_text}User: {query}"
    system = "You are Quran-Talk, a warm and friendly Islamic scholar. Be conversational and remember previous context. Start with 'Assalamu Alaikum' if appropriate."
    
    try:
        answer = call_llm(prompt, system=system)
        return {"response": answer or "Assalamu Alaikum! How can I help you today?", "success": True}
    except Exception:
        return {"response": "Assalamu Alaikum! 🌙 How can I help?", "success": False}


# =====================================================
# API ENDPOINTS
# =====================================================
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Quran-Talk API v5.0 - Connected Scholar",
        "quran_verses": quran_count,
        "hadith_count": hadith_count,
        "total_indexed": len(metadata),
        "features": ["ChatOllama", "DuckDuckGo Fallback", "Fluid Mentor Persona"]
    }


@app.post("/chat")
def chat(request: ChatRequest):
    """Conversational endpoint with history and web fallback."""
    query = request.query
    history = request.history or []
    
    if is_small_talk(query):
        result = handle_small_talk(query, history)
        return {"response": result["response"], "sources_used": []}
    
    sources = retrieve_sources(query, k=5)
    result = generate_response(query, sources, history)
    
    return {
        "response": result["response"],
        "sources_used": [format_source_reference(s) for s in sources] if result["success"] else []
    }


@app.get("/search")
def search(query: str = Query(...)):
    """Legacy endpoint without history."""
    if is_small_talk(query):
        result = handle_small_talk(query, [])
        return {"response": result["response"], "sources_used": []}
    
    sources = retrieve_sources(query, k=5)
    result = generate_response(query, sources, [])
    
    return {
        "response": result["response"],
        "sources_used": [format_source_reference(s) for s in sources] if result["success"] else []
    }


# =====================================================
# OPENAI-COMPATIBLE ENDPOINT (for sacred-scroll-ai frontend)
# =====================================================
class OpenAIChatRequest(BaseModel):
    model: Optional[str] = "quran-talk"
    messages: list[dict]
    stream: Optional[bool] = False


@app.post("/v1/chat/completions")
def openai_chat_completions(request: OpenAIChatRequest):
    """OpenAI Chat Completions-compatible endpoint.
    
    Translates between the OpenAI message format and the existing
    Quran-Talk RAG pipeline so the React frontend can talk directly
    to this backend.
    """
    # Extract the latest user message as the query
    user_messages = [m for m in request.messages if m.get("role") == "user"]
    if not user_messages:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model or "quran-talk",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Assalamu Alaikum! How can I help you today?"},
                "finish_reason": "stop"
            }]
        }

    query = user_messages[-1].get("content", "")

    # Build history from ALL prior messages (exclude the latest user message)
    history = []
    for m in request.messages[:-1]:
        role = m.get("role", "user")
        if role in ("user", "assistant"):
            history.append({"role": role, "content": m.get("content", "")})

    # Route through existing pipeline
    if is_small_talk(query):
        result = handle_small_talk(query, history)
        response_text = result["response"]
    else:
        sources = retrieve_sources(query, k=5)
        result = generate_response(query, sources, history)
        response_text = result["response"]

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model or "quran-talk",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


@app.get("/v1/random")
def get_random_verse():
    """Get a random verse from the Quran."""
    quran_verses = [m for m in metadata if m.get("source_type") == "quran"]
    if not quran_verses:
        return {"error": "No Quran verses found"}
    
    verse = random.choice(quran_verses)
    return {
        "arabic": verse.get("text_ar", ""),
        "translation": verse.get("text_en", ""),
        "reference": f"{verse.get('surah_name', 'Unknown')} {verse.get('surah_number', '?')}:{verse.get('verse_number', '?')}"
    }
