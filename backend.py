"""
Quran-Talk Backend API - "Connected Scholar" Edition
FastAPI with conversational RAG for Quran and Hadith.
Features: OpenRouter (Qwen3), DuckDuckGo web fallback, Fluid Mentor persona.
"""

import json
import os
import re
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel
from typing import Optional
from openai import OpenAI

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

# OpenRouter LLM
OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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"
)
OPENROUTER_MODEL = "qwen/qwen3-vl-30b-a3b-thinking"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# =====================================================
# THE "FLUID MENTOR" SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """You are a warm, knowledgeable, and strictly orthodox Islamic scholar named AlQuran Scholar. Your goal is to guide the user with accuracy (Haqq) and compassion (Rahmah), speaking in a natural, fluid narrative.

**YOUR CONVERSATIONAL STYLE (The "Fluid Mentor"):**
1. **No Headers or Bullet Points:** Do not use bold headers like "The Evidence" or "The Ruling." Do not use numbered lists or bullet points. Write in clear, connected paragraphs like a real scholar speaking.
2. **The "Weave" Technique — ALWAYS cite with Surah Name and Chapter:Verse:**
   - Embed citations naturally using the EXACT format: Surah Name (Chapter:Verse)
   - **CORRECT citations:** "In Surah Al-A'raf (7:181), Allah tells us..." or "As mentioned in Surah An-Nur (24:33)..."
   - **WRONG citations (never do this):** "In Surah 7, Allah says..." or "Surah Al-A'raf says..."
   - Always include BOTH the Surah name AND the chapter:verse number in parentheses.
   - For Hadith, cite as: "In Sahih Bukhari (#1234), the Prophet (ﷺ) said..."
   - When quoting Arabic text, place it on its own line, then follow with the English translation using the format: which translates to *"[English translation here]"*
3. **Handling Sources:**
   - **Priority:** Always prioritize the "LOCAL QURAN/HADITH" context provided to you. Use the exact surah numbers and verse numbers given in the sources.
   - **Web Fallback:** If local context is empty, use the "EXTERNAL SCHOLARLY RESOURCES" but explicitly cite the website.
   - **Missing Data:** If NO sources are found, state: "My library doesn't have the specific text for this right now, but the general scholarly consensus is..."
4. **Tone:** Use "We," "Our tradition," and be gentle but firm on Haram/Halal boundaries.

**CITATION FORMAT RULES (CRITICAL - MUST FOLLOW EXACTLY):**
- When citing a Quran verse in your response, you MUST write: "Surah [Name] ([Chapter]:[Verse])"
- Example: "Surah Al-Insan (76:8)" or "Surah Al-Isra (17:9)" - the verse number MUST be included
- WRONG formats that you must NEVER use:
  * "Surah 76" - missing verse number!
  * "Surah Al-Insan" - missing chapter:verse!
  * "In Surah 76, it is stated" - missing verse number!
- CORRECT format: "In Surah Al-Insan (76:8), Allah says..." or "As mentioned in Surah Al-Isra (17:9)..."
- The pattern is ALWAYS: Surah + Name + (Chapter:Verse) - all three parts are required
- Hadith: Always write "Sahih Bukhari (#[Number])" — e.g., "Sahih Bukhari (#5590)"

**LANGUAGE:**
- Reply in the same language/script as the user (English, Urdu, or Roman Urdu).
"""


# =====================================================
# REQUEST MODELS
# =====================================================
class ChatRequest(BaseModel):
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
# RESPONSE PARSING (for <think> tags from Qwen thinking models)
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
# LLM CALL (Using OpenRouter - OpenAI-compatible)
# =====================================================
def call_llm(prompt: str, system: str = None, think_mode: bool = True) -> tuple[str, str]:
    """Call the LLM via OpenRouter and return (thinking, answer).

    Args:
        prompt: The user prompt
        system: System prompt (optional)
        think_mode: If False, append /no_think to disable Qwen3 deep reasoning
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    # For Qwen3: append /no_think to disable deep reasoning mode
    final_prompt = prompt
    if not think_mode:
        final_prompt = prompt + " /no_think"

    messages.append({"role": "user", "content": final_prompt})

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
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
# FASTAPI INITIALIZATION
# =====================================================
app = FastAPI(
    title="Quran-Talk API",
    description="Connected Scholar - Conversational Quran & Hadith with OpenRouter",
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
print(f"🤖 LLM: {OPENROUTER_MODEL} via OpenRouter")


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
        surah_name = item.get('surah_name', 'Unknown')
        surah_num = item.get('surah_number', '?')
        verse_num = item.get('verse_number', '?')
        # Format: CITATION_FORMAT: Surah Al-Insan (76:8) - use this exact format in your response
        return (f"📖 QURAN VERSE - CITE AS: Surah {surah_name} ({surah_num}:{verse_num})\n"
                f"   Chapter: {surah_num}, Verse: {verse_num}\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")
    else:
        hadith_num = item.get('hadith_number', '')
        collection = item.get('collection', 'Hadith')
        num_display = f" #{hadith_num}" if hadith_num and str(hadith_num).lower() not in ('none', 'n/a', '') else ""
        return (f"📜 HADITH - CITE AS: {collection}{num_display}\n"
                f"   Arabic: {text_ar}\n"
                f"   English: {text_en}")


def format_source_reference(item: dict) -> dict:
    if item.get("source_type") == "quran":
        return {
            "type": "quran",
            "surah_name": item.get("surah_name", "Unknown"),
            "verse_number": item.get("verse_number", "?")
        }
    else:
        hadith_num = item.get("hadith_number", "")
        # Filter out empty, None, or placeholder values
        if not hadith_num or str(hadith_num).lower() in ("none", "n/a", ""):
            hadith_num = None
        return {
            "type": "hadith",
            "collection": item.get("collection", "Hadith"),
            "hadith_number": hadith_num
        }


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
def generate_response(query: str, sources: list[dict], history: list[dict], think_mode: bool = True) -> dict:
    # Format local context
    if sources:
        local_context = "📚 LOCAL QURAN/HADITH SOURCES:\n" + "\n\n".join(
            [format_source_for_context(s) for s in sources]
        )
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

CRITICAL REMINDER - CITATION FORMAT:
When citing Quran verses, use EXACTLY this format: "Surah [Name] ([Chapter]:[Verse])"

✅ CORRECT: "In Surah Al-Insan (76:8), Allah says..."
❌ WRONG: "In Surah 76, Allah says..." (missing verse!)
❌ WRONG: "In Surah Al-Insan, it is stated" (missing chapter:verse!)

Each source above shows: CITATION_FORMAT: Surah [Name] ([Chapter]:[Verse])
Copy this format exactly - include the verse number in parentheses.

Respond as the Fluid Mentor:"""

    try:
        thinking, answer = call_llm(user_prompt, system=SYSTEM_PROMPT, think_mode=think_mode)
        if answer:
            return {"response": answer, "thinking": thinking, "success": True}
        raise Exception("Empty response")
    except Exception as e:
        # Fallback: just show sources
        fallback = "Bismillah. Here are the most relevant sources:\n\n"
        for s in sources:
            if s.get("source_type") == "quran":
                fallback += f"📖 **{s.get('surah_name', 'Quran')} ({s.get('surah_number', '?')}:{s.get('verse_number', '?')})**\n"
            else:
                h_num = s.get('hadith_number', '')
                num_str = f" #{h_num}" if h_num and str(h_num).lower() not in ('none', 'n/a', '') else ""
                fallback += f"📜 **{s.get('collection', 'Hadith')}{num_str}**\n"

            text_en = s.get('text_en', '')
            text = text_en[:400] + "..." if len(text_en) > 400 else text_en
            fallback += f"> {text}\n\n"
        return {"response": fallback, "thinking": "", "success": False}


def handle_small_talk(query: str, history: list[dict]) -> dict:
    history_text = format_history_for_prompt(history)
    prompt = f"{history_text}User: {query}"
    system = "You are AlQuran Scholar, a warm and friendly Islamic scholar. Be conversational and remember previous context. Start with 'Assalamu Alaikum' if appropriate."

    try:
        thinking, answer = call_llm(prompt, system=system)
        return {"response": answer or "Assalamu Alaikum! How can I help you today?", "thinking": thinking, "success": True}
    except Exception:
        return {"response": "Assalamu Alaikum! 🌙 How can I help?", "thinking": "", "success": False}


# =====================================================
# API ENDPOINTS
# =====================================================
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Quran-Talk API v5.0 - Connected Scholar (OpenRouter)",
        "quran_verses": quran_count,
        "hadith_count": hadith_count,
        "total_indexed": len(metadata),
        "llm": OPENROUTER_MODEL,
        "features": ["OpenRouter/Qwen3", "DuckDuckGo Fallback", "Fluid Mentor Persona"]
    }


@app.post("/chat")
def chat(request: ChatRequest):
    """Conversational endpoint with history, web fallback, and think mode toggle."""
    query = request.query
    history = request.history or []
    think_mode = request.think_mode if request.think_mode is not None else True

    if is_small_talk(query):
        result = handle_small_talk(query, history)
        return {"response": result["response"], "thinking": result["thinking"], "sources_used": []}

    sources = retrieve_sources(query, k=5)
    result = generate_response(query, sources, history, think_mode=think_mode)

    return {
        "response": result["response"],
        "thinking": result["thinking"],
        "sources_used": [format_source_reference(s) for s in sources] if result["success"] else []
    }


@app.get("/search")
def search(query: str = Query(...)):
    """Legacy endpoint without history."""
    if is_small_talk(query):
        result = handle_small_talk(query, [])
        return {"response": result["response"], "thinking": result["thinking"], "sources_used": []}

    sources = retrieve_sources(query, k=5)
    result = generate_response(query, sources, [])

    return {
        "response": result["response"],
        "thinking": result["thinking"],
        "sources_used": [format_source_reference(s) for s in sources] if result["success"] else []
    }
