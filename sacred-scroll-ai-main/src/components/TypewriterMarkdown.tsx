import { useState, useEffect, useRef } from 'react';
import FormattedMessage from '@/components/FormattedMessage';

interface TypewriterMarkdownProps {
    content: string;
    animate: boolean;
    speed?: number;
    onComplete?: () => void;
    onTick?: () => void;
}

const TypewriterMarkdown = ({
    content,
    animate,
    speed = 12,
    onComplete,
    onTick,
}: TypewriterMarkdownProps) => {
    const safeContent = content || "";
    const [displayedLength, setDisplayedLength] = useState(animate ? 0 : safeContent.length);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const completedRef = useRef(!animate);

    useEffect(() => {
        if (!animate) {
            setDisplayedLength(safeContent.length);
            return;
        }

        intervalRef.current = setInterval(() => {
            setDisplayedLength((prev) => {
                const next = Math.min(prev + 3, safeContent.length);
                return next;
            });
        }, speed);

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [animate, safeContent, speed]);

    // Handle callbacks outside of state updater to avoid React warnings
    useEffect(() => {
        if (displayedLength > 0 && displayedLength < safeContent.length) {
            onTick?.();
        }
        if (displayedLength >= safeContent.length && !completedRef.current) {
            completedRef.current = true;
            if (intervalRef.current) clearInterval(intervalRef.current);
            onComplete?.();
        }
    }, [displayedLength, safeContent.length, onComplete, onTick]);

    const visibleText = safeContent.slice(0, displayedLength);

    return (
        <div>
            <FormattedMessage content={visibleText} />
            {animate && displayedLength < safeContent.length && (
                <span className="inline-block w-0.5 h-4 bg-emerald-600 dark:bg-emerald-400 animate-pulse ml-0.5 align-text-bottom" />
            )}
        </div>
    );
};

export default TypewriterMarkdown;
