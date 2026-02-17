// QuranAI Backend API Service
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Message {
    role: 'user' | 'assistant';
    content: string;
}

export interface ChatResponse {
    response: string;
    sources_used?: Array<{
        type: 'quran' | 'hadith';
        surah_name?: string;
        verse_number?: number;
        collection?: string;
        hadith_number?: string;
    }>;
}

export async function sendMessage(
    query: string,
    history: Message[]
): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            query,
            history: history.slice(-6), // Last 6 messages for context
        }),
    });

    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
}

export async function checkHealth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/`);
        return response.ok;
    } catch {
        return false;
    }
}
