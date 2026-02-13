"""
title: Quran-Talk Pipeline
author: QuranAI
version: 1.0.0
description: Islamic Scholar RAG Pipeline - wraps QuranAI backend for Open WebUI
"""

import requests
from typing import Generator, Iterator, Union
from pydantic import BaseModel, Field


class Pipeline:
    """
    Quran-Talk Pipeline
    Wraps the QuranAI FastAPI backend as an OpenAI-compatible model for Open WebUI.
    """
    
    class Valves(BaseModel):
        """Configurable settings for the pipeline."""
        QURANAI_API_URL: str = Field(
            default="http://host.docker.internal:8000",
            description="URL of the QuranAI backend API"
        )
        REQUEST_TIMEOUT: int = Field(
            default=180,
            description="Timeout in seconds for API requests"
        )

    def __init__(self):
        self.name = "Quran-Talk"
        self.valves = self.Valves()

    async def on_startup(self):
        """Called when the pipeline starts."""
        print(f"🕌 Quran-Talk Pipeline starting...")
        print(f"📡 Backend URL: {self.valves.QURANAI_API_URL}")

    async def on_shutdown(self):
        """Called when the pipeline shuts down."""
        print("🕌 Quran-Talk Pipeline shutting down...")

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list,
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline method - processes chat messages.
        
        Args:
            user_message: The current user message
            model_id: The model ID (will be "quran-talk")
            messages: Full conversation history in OpenAI format
            body: Full request body
        
        Returns:
            The assistant's response string
        """
        # Convert OpenAI-style messages to QuranAI history format
        history = []
        for msg in messages[:-1]:  # Exclude the current message
            if msg.get("role") in ["user", "assistant"]:
                history.append({
                    "role": msg["role"],
                    "content": msg.get("content", "")
                })
        
        # Call QuranAI backend
        try:
            response = requests.post(
                f"{self.valves.QURANAI_API_URL}/chat",
                json={
                    "query": user_message,
                    "history": history[-6:]  # Last 6 messages for context
                },
                timeout=self.valves.REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                return f"⚠️ Backend Error ({response.status_code}): Unable to reach the Islamic scholar at this time."
            
            data = response.json()
            answer = data.get("response", "I apologize, I could not formulate a response.")
            thinking = data.get("thinking", "")
            sources = data.get("sources_used", [])
            
            # Format the response with optional reasoning and sources
            formatted_response = answer
            
            # Add sources footer if available
            if sources:
                formatted_response += "\n\n---\n**📚 Sources:**\n"
                for src in sources:
                    if src.get("type") == "quran":
                        formatted_response += f"- 📖 {src.get('surah_name', 'Quran')}:{src.get('verse_number', '?')}\n"
                    else:
                        formatted_response += f"- 📜 {src.get('collection', 'Hadith')} #{src.get('hadith_number', '?')}\n"
            
            return formatted_response
            
        except requests.exceptions.Timeout:
            return "⏳ The scholar is taking longer than expected. Please try again."
        except requests.exceptions.ConnectionError:
            return "🔌 Unable to connect to the Islamic knowledge base. Please ensure the backend is running."
        except Exception as e:
            return f"⚠️ An error occurred: {str(e)}"
