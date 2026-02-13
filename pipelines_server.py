"""
Local Pipelines Server for Quran-Talk
Runs the pipeline locally - serves an OpenAI-compatible API for Open WebUI.
Supports streaming responses.
"""

import json
import time
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests
from typing import Optional, AsyncGenerator
from pydantic import BaseModel

# Configuration
QURANAI_API_URL = "http://localhost:8000"
PIPELINE_PORT = 9099
API_KEY = "0p3n-w3bu!"

app = FastAPI(
    title="Quran-Talk Pipelines",
    description="OpenAI-compatible API wrapping QuranAI for Open WebUI",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: Optional[bool] = False


# =====================================================
# MODEL LIST (reusable)
# =====================================================
def get_models_response():
    """Return the models list."""
    return {
        "object": "list",
        "data": [
            {
                "id": "quran-talk",
                "object": "model",
                "created": 1700000000,
                "owned_by": "quranai",
                "name": "Quran-Talk",
                "description": "Islamic Scholar AI - Conversational Quran & Hadith 🕌"
            }
        ]
    }


# =====================================================
# ENDPOINTS
# =====================================================
@app.get("/")
def root():
    """Root endpoint."""
    return {
        "status": "ok",
        "message": "Quran-Talk Pipelines Server",
        "version": "3.0.0",
        "endpoints": ["/v1/models", "/v1/chat/completions", "/health"]
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# Both /models and /v1/models for compatibility
@app.get("/models")
def list_models_legacy():
    """Return available models (legacy endpoint)."""
    return get_models_response()


@app.get("/v1/models")
def list_models():
    """Return available models for Open WebUI."""
    return get_models_response()


async def stream_response(answer: str, model: str) -> AsyncGenerator[str, None]:
    """Stream the response word by word for typing animation effect."""
    words = answer.split(' ')
    
    for i, word in enumerate(words):
        chunk_content = word + (' ' if i < len(words) - 1 else '')
        
        chunk = {
            "id": f"chatcmpl-{model}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": chunk_content},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)  # Small delay for typing effect
    
    # Send final chunk
    final_chunk = {
        "id": f"chatcmpl-{model}",
        "object": "chat.completion.chunk", 
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"


async def call_quranai(user_message: str, history: list) -> str:
    """Call QuranAI backend and return response."""
    try:
        response = requests.post(
            f"{QURANAI_API_URL}/chat",
            json={
                "query": user_message,
                "history": history[-6:]
            },
            timeout=180
        )
        
        if response.status_code != 200:
            return f"⚠️ Backend Error ({response.status_code})"
        
        data = response.json()
        answer = data.get("response", "I could not formulate a response.")
        sources = data.get("sources_used", [])
        
        # Add sources footer
        if sources:
            answer += "\n\n---\n**📚 Sources:**\n"
            for src in sources:
                if src.get("type") == "quran":
                    answer += f"- 📖 {src.get('surah_name', 'Quran')}:{src.get('verse_number', '?')}\n"
                else:
                    answer += f"- 📜 {src.get('collection', 'Hadith')} #{src.get('hadith_number', '?')}\n"
        
        return answer
        
    except requests.exceptions.Timeout:
        return "⏳ The scholar is taking longer than expected. Please try again."
    except requests.exceptions.ConnectionError:
        return "🔌 Unable to connect to the Islamic knowledge base. Please ensure the backend is running."
    except Exception as e:
        return f"⚠️ An error occurred: {str(e)}"


# Both /chat/completions and /v1/chat/completions for compatibility
@app.post("/chat/completions")
async def chat_completions_legacy(request: ChatRequest):
    """OpenAI-compatible chat completion (legacy endpoint)."""
    return await chat_completions(request)


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completion endpoint with streaming."""
    
    messages = request.messages
    user_message = ""
    history = []
    
    for msg in messages:
        if msg.role == "user":
            user_message = msg.content
        if msg.role in ["user", "assistant"]:
            history.append({"role": msg.role, "content": msg.content})
    
    # Remove last user message from history
    if history and history[-1]["role"] == "user":
        history = history[:-1]
    
    # Call QuranAI backend
    answer = await call_quranai(user_message, history)
    
    # Handle streaming
    if request.stream:
        return StreamingResponse(
            stream_response(answer, request.model),
            media_type="text/event-stream"
        )
    
    # Non-streaming response
    return {
        "id": f"chatcmpl-{request.model}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(answer.split()),
            "total_tokens": len(user_message.split()) + len(answer.split())
        }
    }


if __name__ == "__main__":
    print("🕌 Starting Quran-Talk Pipelines Server v3.0...")
    print(f"📡 QuranAI Backend: {QURANAI_API_URL}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"🌐 Server: http://localhost:{PIPELINE_PORT}")
    print("")
    print("Connect Open WebUI to:")
    print(f"  URL: http://localhost:{PIPELINE_PORT}")
    print(f"  Key: {API_KEY}")
    print("")
    uvicorn.run(app, host="0.0.0.0", port=PIPELINE_PORT)
