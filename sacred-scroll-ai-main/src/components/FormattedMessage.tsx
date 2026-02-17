import React from 'react';
import { cn } from '@/lib/utils';

interface FormattedMessageProps {
    content: string;
    className?: string;
}

/**
 * Renders AI response with special formatting:
 * - **Surah X:Y** → Gold badge
 * - Full Arabic verses → Styled card block with Amiri font
 * - Short Arabic (honorifics like جل جلاله) → Inline, subtle
 * - *"quoted text"* → Styled italic quote
 * - Sources section → Gold chips
 */
const FormattedMessage: React.FC<FormattedMessageProps> = ({ content, className }) => {
    const lines = content.split('\n');

    return (
        <div className={cn("text-[15px] leading-relaxed", className)}>
            {lines.map((line, lineIndex) => {
                // Empty line = line break
                if (!line.trim()) return <br key={lineIndex} />;

                // Horizontal rule
                if (line.trim() === '---') {
                    return <hr key={lineIndex} className="my-4 border-emerald-200 dark:border-emerald-800" />;
                }

                // Sources header
                if (line.includes('📚 Sources') || line.includes('**📚 Sources')) {
                    return (
                        <p key={lineIndex} className="mt-4 mb-2 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
                            📚 Sources
                        </p>
                    );
                }

                // Source list items (📖 Quran or 📜 Hadith)
                if (line.trim().startsWith('- 📖') || line.trim().startsWith('- 📜')) {
                    const sourceText = line.replace(/^-\s*/, '');
                    return (
                        <span
                            key={lineIndex}
                            className="inline-block mr-2 mb-2 px-3 py-1 text-xs font-medium rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-700"
                        >
                            {sourceText}
                        </span>
                    );
                }

                // Check if line is PRIMARILY Arabic (more than 50% Arabic chars = verse line)
                const arabicRatio = getArabicRatio(line);
                if (arabicRatio > 0.5) {
                    return (
                        <div
                            key={lineIndex}
                            dir="rtl"
                            className="my-4 p-4 rounded-xl bg-gradient-to-r from-emerald-50 to-amber-50 dark:from-emerald-900/20 dark:to-amber-900/10 border border-emerald-200 dark:border-emerald-800"
                        >
                            <p
                                className="text-xl leading-loose text-emerald-900 dark:text-emerald-100 text-center"
                                style={{ fontFamily: "'Amiri', 'Traditional Arabic', serif" }}
                            >
                                {line}
                            </p>
                        </div>
                    );
                }

                // Parse inline formatting for mixed content
                const formattedContent = parseInlineFormatting(line);

                return (
                    <p key={lineIndex} className="mb-3 last:mb-0">
                        {formattedContent}
                    </p>
                );
            })}
        </div>
    );
};

/**
 * Calculate ratio of Arabic characters in text
 */
function getArabicRatio(text: string): number {
    const arabicChars = text.match(/[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]/g) || [];
    const totalChars = text.replace(/\s/g, '').length;
    return totalChars > 0 ? arabicChars.length / totalChars : 0;
}

/**
 * Check if text is a short Arabic phrase (honorific, not a verse)
 * Short = less than ~15 chars (typically 1-3 words like جل جلاله or ﷺ)
 */
function isShortArabic(text: string): boolean {
    const arabicOnly = text.replace(/[^\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]/g, '');
    return arabicOnly.length < 15;
}

/**
 * Parse inline markdown: **bold**, *italic*, Surah references, inline Arabic
 */
function parseInlineFormatting(text: string): React.ReactNode[] {
    const elements: React.ReactNode[] = [];
    let remaining = text;
    let key = 0;

    while (remaining.length > 0) {
        // Check for bold **text** - could be Surah reference, Arabic verse, or emphasis
        const boldMatch = remaining.match(/^\*\*(.+?)\*\*/);
        if (boldMatch) {
            const content = boldMatch[1];

            // Is it a Surah/verse reference?
            if (isSurahReference(content)) {
                elements.push(
                    <span
                        key={key++}
                        className="inline-flex items-center mx-1 px-2 py-0.5 text-sm font-semibold rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-700 whitespace-nowrap"
                    >
                        {content}
                    </span>
                );
            } else if (getArabicRatio(content) > 0.4 && !isShortArabic(content)) {
                // Bold Arabic verse → render as card block
                elements.push(
                    <span
                        key={key++}
                        dir="rtl"
                        className="block my-3 p-3 rounded-xl bg-gradient-to-r from-emerald-50 to-amber-50 dark:from-emerald-900/20 dark:to-amber-900/10 border border-emerald-200 dark:border-emerald-800 text-xl leading-loose text-emerald-900 dark:text-emerald-100 text-center font-semibold"
                        style={{ fontFamily: "'Amiri', 'Traditional Arabic', serif" }}
                    >
                        {content}
                    </span>
                );
            } else {
                // Regular bold text
                elements.push(
                    <strong key={key++} className="font-semibold text-emerald-800 dark:text-emerald-200">
                        {content}
                    </strong>
                );
            }
            remaining = remaining.slice(boldMatch[0].length);
            continue;
        }

        // Check for italic *text* (often quotes) - but not ** which is bold
        const italicMatch = remaining.match(/^\*([^*]+)\*/);
        if (italicMatch) {
            const content = italicMatch[1];
            elements.push(
                <em key={key++} className="italic text-emerald-700 dark:text-emerald-300">
                    {content.startsWith('"') || content.startsWith("'") || content.startsWith('\u201c')
                        ? content
                        : `"${content}"`}
                </em>
            );
            remaining = remaining.slice(italicMatch[0].length);
            continue;
        }

        // Check for inline Arabic text
        const arabicMatch = remaining.match(/^([\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF\s]+)/);
        if (arabicMatch && arabicMatch[1].trim()) {
            const arabicText = arabicMatch[1].trim();

            if (isShortArabic(arabicText)) {
                // Short Arabic (honorific like ﷻ ﷺ) - keep inline, subtle green, fix baseline
                elements.push(
                    <span
                        key={key++}
                        className="inline-block text-emerald-600 dark:text-emerald-400 align-middle"
                        style={{ fontFamily: "'Amiri', serif", lineHeight: '1' }}
                    >
                        {' '}{arabicText}{' '}
                    </span>
                );
            } else {
                // Long Arabic (Quranic verse) - break out into a styled card block
                elements.push(
                    <span
                        key={key++}
                        dir="rtl"
                        className="block my-3 p-3 rounded-xl bg-gradient-to-r from-emerald-50 to-amber-50 dark:from-emerald-900/20 dark:to-amber-900/10 border border-emerald-200 dark:border-emerald-800 text-xl leading-loose text-emerald-900 dark:text-emerald-100 text-center"
                        style={{ fontFamily: "'Amiri', 'Traditional Arabic', serif" }}
                    >
                        {arabicText}
                    </span>
                );
            }
            remaining = remaining.slice(arabicMatch[0].length);
            continue;
        }

        // Check for standalone Surah reference without markdown
        const surahMatch = remaining.match(/^(Surah\s+[\w'-]+\s*\(?\d+:\d+\)?)/i);
        if (surahMatch) {
            elements.push(
                <span
                    key={key++}
                    className="inline-flex items-center mx-1 px-2 py-0.5 text-sm font-semibold rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-700 whitespace-nowrap"
                >
                    {surahMatch[1]}
                </span>
            );
            remaining = remaining.slice(surahMatch[0].length);
            continue;
        }

        // Find next special pattern
        const nextSpecial = findNextSpecialIndex(remaining);

        if (nextSpecial === -1) {
            // No more special patterns, add rest as plain text
            elements.push(<span key={key++}>{remaining}</span>);
            break;
        } else if (nextSpecial === 0) {
            // At a special char but no pattern matched, move forward by one
            elements.push(<span key={key++}>{remaining[0]}</span>);
            remaining = remaining.slice(1);
        } else {
            // Add text before the special pattern
            elements.push(<span key={key++}>{remaining.slice(0, nextSpecial)}</span>);
            remaining = remaining.slice(nextSpecial);
        }
    }

    return elements;
}

/**
 * Check if text is a Surah/verse reference
 */
function isSurahReference(text: string): boolean {
    const patterns = [
        /Surah\s+[\w'-]+/i,           // Surah Al-Baqarah
        /^[\w'-]+\s+\d+:\d+$/,        // Al-Baqarah 2:153
        /^[\w'-]+\s*\(\d+:\d+\)$/,    // Al-Baqarah (2:153)
        /^\d+:\d+$/,                   // 2:153
        /Sahih\s+(Bukhari|Muslim)/i,  // Sahih Bukhari
        /Hadith\s*#?\d+/i,            // Hadith #123
    ];
    return patterns.some(p => p.test(text.trim()));
}

/**
 * Find index of next special pattern
 */
function findNextSpecialIndex(text: string): number {
    const patterns = [
        /\*\*/,                                           // Bold
        /\*[^*]/,                                         // Italic (not bold)
        /Surah\s+[\w'-]+/i,                              // Surah reference
        /[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]/,    // Arabic char
    ];

    let minIndex = -1;

    for (const regex of patterns) {
        const match = text.search(regex);
        if (match !== -1 && (minIndex === -1 || match < minIndex)) {
            minIndex = match;
        }
    }

    return minIndex;
}

export default FormattedMessage;
