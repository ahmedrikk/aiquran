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
# Use comprehensive jurisprudence database (Quran + Hadith + Ijma + Qiyas)
INDEX_PATH = os.path.join(DATA_DIR, "jurisprudence.index")
METADATA_PATH = os.path.join(DATA_DIR, "jurisprudence_metadata.json")
# Fallback to old database if new one doesn't exist
if not os.path.exists(INDEX_PATH):
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
• For Ijma sources: cite them as "The consensus (Ijma) of the scholars is..."
• For Qiyas sources: explain the analogy when relevant - "By analogy (Qiyas) to the case of..."
• If local context is insufficient, use EXTERNAL SCHOLARLY RESOURCES but cite the website explicitly.
• If NO sources are found: say *"My library doesn't have the specific text for this right now, but the general scholarly consensus is..."* then give the ruling.

═══ RELEVANCE CHECK (CRITICAL) ═══
• Before citing any retrieved source, ask yourself: "Is this verse/hadith DIRECTLY about the topic asked?"
• If the retrieved sources are only loosely or indirectly related, DO NOT force them to fit. Say: *"My library returned general verses, but the specific ruling comes from..."* then state the well-known scholarly consensus (Ijma) from your knowledge.
• NEVER use a verse about fornication (zina) to answer a question about homosexuality — these are different rulings with different evidences.
• NEVER use a hadith about a man-woman act to make qiyas for a man-man act without explicitly noting the difference.

═══ ANTI-HALLUCINATION PROTOCOL (CRITICAL) ═══
• NEVER quote or cite a Quran verse or Hadith that is NOT in the provided context. Fabricating religious text is a MAJOR SIN.
• NEVER invent Arabic text, Hadith numbers, or verse references.
• NEVER invent verse numbers that are not literally present in the context provided to you.
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
ijma_count = sum(1 for m in metadata if m.get("source_type") == "ijma")
qiyas_count = sum(1 for m in metadata if m.get("source_type") == "qiyas")
print(f"✅ Backend ready! Quran: {quran_count}, Hadith: {hadith_count}, Ijma: {ijma_count}, Qiyas: {qiyas_count}")


# =====================================================
# RETRIEVAL FUNCTIONS
# =====================================================
def retrieve_sources(query: str, k: int = 5) -> list[dict]:
    query_embedding = embedding_model.encode([query]).astype('float32')
    labels, distances = index.knn_query(query_embedding, k=k)
    return [metadata[idx] for idx in labels[0]]


def format_source_for_context(item: dict) -> str:
    """Format source for LLM context with proper labeling."""
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
        if not hadith_num or str(hadith_num).lower() in ("none", "n/a", "", "na", "null"):
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
    """Format source reference for frontend display badges."""
    source_type = item.get("source_type", "unknown")
    
    if source_type == "quran":
        return {
            "type": "quran",
            "surah_name": item.get("surah_name", "Unknown"),
            "verse_number": item.get("verse_number", "?")
        }
    
    elif source_type == "hadith":
        hadith_num = item.get("hadith_number", "")
        # Filter out empty, None, or placeholder values
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
    # Format local context with all source types
    if sources:
        # Group sources by type for better organization
        quran_sources = [s for s in sources if s.get("source_type") == "quran"]
        hadith_sources = [s for s in sources if s.get("source_type") == "hadith"]
        ijma_sources = [s for s in sources if s.get("source_type") == "ijma"]
        qiyas_sources = [s for s in sources if s.get("source_type") == "qiyas"]
        
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
            source_type = s.get("source_type", "unknown")
            if source_type == "quran":
                fallback += f"📖 **{s['surah_name']}:{s['verse_number']}**\n"
            elif source_type == "hadith":
                hadith_num = s.get('hadith_number', '?')
                fallback += f"📜 **{s['collection']} #{hadith_num}**\n"
            elif source_type == "ijma":
                fallback += f"⚖️ **Ijma: {s.get('topic', 'Scholarly Consensus')}**\n"
            elif source_type == "qiyas":
                fallback += f"⚖️ **Qiyas: {s.get('case', 'Analogical Reasoning')}**\n"
            
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
        "message": "Quran-Talk API v6.0 - Complete Usul al-Fiqh",
        "quran_verses": quran_count,
        "hadith_count": hadith_count,
        "ijma_records": ijma_count,
        "qiyas_cases": qiyas_count,
        "total_indexed": len(metadata),
        "features": ["ChatOllama", "DuckDuckGo Fallback", "Complete Jurisprudence (Quran, Hadith, Ijma, Qiyas)"],
        "source_types": ["quran", "hadith", "ijma", "qiyas"]
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
