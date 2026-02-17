import { useState, useCallback, useRef } from 'react';

/**
 * Custom hook for voice input (STT) and read-aloud (TTS) using the Web Speech API.
 * Browser-native — no backend dependencies needed.
 */

// ─── Speech-to-Text (Microphone) ───────────────────────────────
interface UseVoiceReturn {
    // STT
    isListening: boolean;
    startListening: (onResult: (text: string) => void) => void;
    stopListening: () => void;
    sttSupported: boolean;

    // TTS
    isSpeaking: boolean;
    speak: (text: string) => void;
    stopSpeaking: () => void;
    ttsSupported: boolean;
}

/** Strip markdown formatting for cleaner TTS output */
function cleanForSpeech(text: string): string {
    return text
        .replace(/\*\*(.+?)\*\*/g, '$1')   // **bold** → bold
        .replace(/\*(.+?)\*/g, '$1')       // *italic* → italic
        .replace(/#{1,6}\s*/g, '')          // ### headers
        .replace(/---/g, '')                // horizontal rules
        .replace(/📖|📜|📚|✨|🔊/g, '')     // emojis
        .replace(/\[(.+?)\]\(.+?\)/g, '$1') // [text](url) → text
        .trim();
}

export function useVoice(): UseVoiceReturn {
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const recognitionRef = useRef<any>(null);

    // Check browser support
    const SpeechRecognition =
        typeof window !== 'undefined'
            ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
            : null;
    const sttSupported = !!SpeechRecognition;
    const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

    // ─── Speech-to-Text ──────────────────────────────
    const startListening = useCallback(
        (onResult: (text: string) => void) => {
            if (!SpeechRecognition) return;

            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;
            recognition.continuous = false;

            recognition.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                onResult(transcript);
                setIsListening(false);
            };

            recognition.onerror = (event: any) => {
                console.error('Speech recognition error:', event.error);
                setIsListening(false);
            };

            recognition.onend = () => {
                setIsListening(false);
            };

            recognitionRef.current = recognition;
            recognition.start();
            setIsListening(true);
        },
        [SpeechRecognition]
    );

    const stopListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
            recognitionRef.current = null;
        }
        setIsListening(false);
    }, []);

    // ─── Text-to-Speech ──────────────────────────────
    const speak = useCallback((text: string) => {
        if (!ttsSupported) return;

        // Stop any current speech first
        window.speechSynthesis.cancel();

        const cleaned = cleanForSpeech(text);
        const utterance = new SpeechSynthesisUtterance(cleaned);
        utterance.rate = 0.95;
        utterance.pitch = 1.0;

        // Try to pick a good English voice
        const voices = window.speechSynthesis.getVoices();
        const preferred = voices.find(
            (v) => v.lang.startsWith('en') && v.name.toLowerCase().includes('google')
        ) || voices.find((v) => v.lang.startsWith('en'));
        if (preferred) {
            utterance.voice = preferred;
        }

        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);

        setIsSpeaking(true);
        window.speechSynthesis.speak(utterance);
    }, [ttsSupported]);

    const stopSpeaking = useCallback(() => {
        if (ttsSupported) {
            window.speechSynthesis.cancel();
        }
        setIsSpeaking(false);
    }, [ttsSupported]);

    return {
        isListening,
        startListening,
        stopListening,
        sttSupported,
        isSpeaking,
        speak,
        stopSpeaking,
        ttsSupported,
    };
}
