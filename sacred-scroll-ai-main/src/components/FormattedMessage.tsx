import React from 'react';
import { cn } from '@/lib/utils';

interface FormattedMessageProps {
  content: string;
  className?: string;
}

/**
 * FormattedMessage v4 — Robust Islamic Text Formatter
 *
 * FIXES from v3:
 *  ✅ English translations NO LONGER render as Arabic verse cards
 *  ✅ Multi-line *"..."* quotes → proper blockquote (left-aligned, border)
 *  ✅ Stray asterisks and broken *". patterns cleaned up
 *  ✅ Arabic detection: requires BOTH high ratio AND minimum 10 Arabic chars AND low Latin ratio
 *  ✅ Hadith #N/A gracefully hidden in badges
 *  ✅ Safety: max iteration cap prevents infinite loops
 */
const FormattedMessage: React.FC<FormattedMessageProps> = ({ content, className }) => {
  // Pre-process: handle multi-line quoted translations, clean broken markers
  const processed = preprocessContent(content);
  const blocks = processed.split(/\n\n+/);

  return (
    <div className={cn('text-[15px] leading-relaxed', className)}>
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        // Blockquote (from preprocessing of *"..."* patterns)
        if (trimmed.startsWith('___BQ___')) {
          const quoteText = trimmed.replace('___BQ___', '').trim();
          return (
            <blockquote
              key={bIdx}
              className="my-4 py-3 px-4 text-[15px] leading-relaxed text-left
                bg-amber-50/50 dark:bg-amber-900/10
                rounded-r-lg italic text-gray-700 dark:text-gray-300"
              style={{ borderLeft: '3px solid #D4AF37' }}
            >
              &ldquo;{quoteText}&rdquo;
            </blockquote>
          );
        }

        // Full Arabic block (STRICT detection)
        if (isArabicBlock(trimmed)) {
          return (
            <div
              key={bIdx}
              dir="rtl"
              className="my-4 px-5 py-4 rounded-xl text-center
                bg-gradient-to-r from-emerald-50/80 to-amber-50/60
                dark:from-emerald-900/20 dark:to-amber-900/10
                border border-emerald-200/60 dark:border-emerald-800/40"
            >
              <p
                className="text-[1.35rem] leading-[2.4] text-emerald-900 dark:text-emerald-100"
                style={{ fontFamily: "'Amiri', 'Traditional Arabic', 'Scheherazade New', serif" }}
              >
                {trimmed}
              </p>
            </div>
          );
        }

        // Regular paragraph(s)
        const lines = block.split('\n');
        return (
          <div key={bIdx} className="mb-3 last:mb-0">
            {lines.map((line, lIdx) => renderLine(line, `${bIdx}-${lIdx}`))}
          </div>
        );
      })}
    </div>
  );
};

/* ═══════════════════════════════════════════
   PRE-PROCESSING — fixes the main bugs
   ═══════════════════════════════════════════ */

function preprocessContent(content: string): string {
  let result = content;

  // 1. Multi-line *"..."* → blockquote (THE MAIN FIX)
  //    This was causing English translations to appear in the verse card
  result = result.replace(
    /\*\s*"([\s\S]*?)"\s*\*/g,
    (_, quote) => {
      const cleaned = quote.replace(/\s*\n\s*/g, ' ').replace(/\s+/g, ' ').trim();
      return `\n\n___BQ___${cleaned}\n\n`;
    }
  );

  // 2. Standalone long "..." paragraph (no asterisks, 80+ chars)
  result = result.replace(
    /^"([^"]{80,})"$/gm,
    (_, quote) => `___BQ___${quote.trim()}`
  );

  // 3. Clean orphaned *" at start or "* at end of lines
  //    e.g. *".Merciful → .Merciful
  result = result.replace(/\*"\s*\./g, '.');
  result = result.replace(/"\*\s*$/gm, '"');
  result = result.replace(/^\*"\s*/gm, '"');

  // 4. Clean stray solo asterisks at line boundaries (not part of **bold**)
  result = result.replace(/(^|\n)\*([^*\n])/g, '$1$2');
  result = result.replace(/([^*\n])\*($|\n)/g, '$1$2');

  return result;
}

/* ═══════════════════════════════════════════
   LINE-LEVEL RENDERING
   ═══════════════════════════════════════════ */

function renderLine(line: string, key: string): React.ReactNode {
  const trimmed = line.trim();
  if (!trimmed) return null;

  // Horizontal rule
  if (trimmed === '---') {
    return <hr key={key} className="my-4 border-emerald-200 dark:border-emerald-800" />;
  }

  // Sources header
  if (/📚\s*Sources/i.test(trimmed)) {
    return (
      <p key={key} className="mt-4 mb-2 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
        📚 Sources
      </p>
    );
  }

  // Source chips (📖 📜 ⚖️) — hide #N/A
  if (/^-\s*(📖|📜|⚖️)/.test(trimmed)) {
    let sourceText = trimmed.replace(/^-\s*/, '');
    sourceText = sourceText.replace(/#?N\/A/gi, '').replace(/\s+/g, ' ').trim();
    // Skip empty-looking sources
    if (sourceText.length < 5) return null;
    
    // Different styling for different source types
    const isIjma = sourceText.includes('Ijma') || sourceText.includes('Consensus');
    const isQiyas = sourceText.includes('Qiyas') || sourceText.includes('Analogy');
    
    let badgeClass = "inline-block mr-2 mb-2 px-3 py-1.5 text-xs font-medium rounded-full ";
    if (isIjma) {
      badgeClass += "bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-300 dark:border-emerald-700";
    } else if (isQiyas) {
      badgeClass += "bg-purple-50 text-purple-800 border border-purple-200 dark:bg-purple-900/20 dark:text-purple-300 dark:border-purple-700";
    } else {
      badgeClass += "bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-700";
    }
    
    return (
      <span key={key} className={badgeClass}>
        {sourceText}
      </span>
    );
  }

  // Full Arabic line (STRICT check)
  if (isArabicBlock(trimmed)) {
    return (
      <div
        key={key}
        dir="rtl"
        className="my-4 px-5 py-4 rounded-xl text-center
          bg-gradient-to-r from-emerald-50/80 to-amber-50/60
          dark:from-emerald-900/20 dark:to-amber-900/10
          border border-emerald-200/60 dark:border-emerald-800/40"
      >
        <p
          className="text-[1.35rem] leading-[2.4] text-emerald-900 dark:text-emerald-100"
          style={{ fontFamily: "'Amiri', 'Traditional Arabic', 'Scheherazade New', serif" }}
        >
          {trimmed}
        </p>
      </div>
    );
  }

  // Default paragraph with inline formatting
  return (
    <p key={key} className="mb-1 last:mb-0 leading-relaxed">
      {parseInline(trimmed)}
    </p>
  );
}

/* ═══════════════════════════════════════════
   ARABIC DETECTION (STRICT — the key fix)
   ═══════════════════════════════════════════ */

/**
 * Returns true ONLY for genuine Arabic text blocks.
 * Must meet ALL THREE conditions:
 *   1. > 60% Arabic characters
 *   2. >= 10 Arabic characters (filters out honorifics like ﷺ)
 *   3. < 15% Latin characters (filters out English with some Arabic)
 */
function isArabicBlock(text: string): boolean {
  const stripped = text.replace(/\s/g, '');
  if (stripped.length === 0) return false;

  const arabicChars = text.match(/[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF]/g) || [];
  const latinChars = text.match(/[a-zA-Z]/g) || [];

  const arabicCount = arabicChars.length;
  const latinCount = latinChars.length;
  const arabicRatio = arabicCount / stripped.length;
  const latinRatio = latinCount / stripped.length;

  return arabicRatio > 0.6 && arabicCount >= 10 && latinRatio < 0.15;
}

/* ═══════════════════════════════════════════
   INLINE PARSING
   ═══════════════════════════════════════════ */

function parseInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;
  let iterations = 0;

  while (remaining.length > 0 && iterations < 200) {
    iterations++;
    let best: { index: number; length: number; node: React.ReactNode } | null = null;

    // ── Pattern matchers (ordered by specificity) ──

    // 1. Bold Surah/Hadith markdown: **Sahih Bukhari [#5590]**
    match(remaining, /\*\*((?:Surah|Sahih|Quran|Hadith|Al-|Bukhari|Muslim|Tirmidhi|Abu Dawud|Ibn Majah|Nasai|Muwatta)[^*]{2,80})\*\*/i,
      m => <GoldBadge key={key++} text={m[1]} />);

    // 2. "Surah Al-Baqarah, verse 153" or "Surah 7, verse 180"
    match(remaining, /Surah\s+([\w'''-]+(?:\s[\w'''-]+){0,3}),?\s*verse\s*(\d+)/i,
      m => <GoldBadge key={key++} text={`📖 ${m[1]}:${m[2]}`} />);

    // 3. (Quran 7:28) or (Surah 24:32)
    match(remaining, /\((?:Quran|Surah|Q)\s*(\d{1,3})\s*:\s*(\d{1,3})\)/i,
      m => <GoldBadge key={key++} text={`📖 Quran ${m[1]}:${m[2]}`} />);

    // 4. Quran 7:28 (no parens)
    match(remaining, /(?:Quran|Q)\s+(\d{1,3})\s*:\s*(\d{1,3})/i,
      m => <GoldBadge key={key++} text={`📖 Quran ${m[1]}:${m[2]}`} />);

    // 5. "verse X of Surah Y"
    match(remaining, /verse\s+(\d{1,3})\s+of\s+Surah\s+([\w'''-]+(?:\s[\w'''-]+){0,3})/i,
      m => <GoldBadge key={key++} text={`📖 ${m[2]}:${m[1]}`} />);

    // 6. Hadith refs: "Sahih Bukhari #5590"
    match(remaining, /(Sahih\s+(?:Bukhari|Muslim)|Tirmidhi|Abu\s+Dawud|Ibn\s+Majah|Muwatta)\s*(?:\[?\s*#?\s*(\d+)\s*\]?|Hadith\s*#?\s*(\d+))?/i,
      m => {
        const num = m[2] || m[3] || '';
        return <GoldBadge key={key++} text={`📜 ${m[1]}${num ? ` #${num}` : ''}`} />;
      });

    // 6a. Ijma (Consensus) references
    match(remaining, /(?:Ijma|Consensus)\s+(?:of\s+)?(?:the\s+)?(?:scholars|ulema|jurists)/i,
      m => <GoldBadge key={key++} text={`⚖️ Ijma (Consensus)`} />);

    // 6b. Qiyas (Analogy) references  
    match(remaining, /(?:Qiyas|Analogy)\s+(?:to\s+)?/i,
      m => <GoldBadge key={key++} text={`⚖️ Qiyas (Analogy)`} />);

    // 7. Generic bold: **text**
    match(remaining, /\*\*(.+?)\*\*/,
      m => <strong key={key++} className="font-semibold text-emerald-800 dark:text-emerald-300">{m[1]}</strong>);

    // 8. Italic: *text* (not *" quote patterns)
    match(remaining, /\*([^*"]{2,100})\*/,
      m => <em key={key++} className="italic text-gray-600 dark:text-gray-400">{m[1]}</em>);

    // 9. Inline Arabic (short honorifics/phrases, 2-40 chars)
    match(remaining, /([\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF\u0610-\u061A\u064B-\u065F]{2,40})/,
      m => (
        <span key={key++} dir="rtl" className="inline text-[1.05em] text-emerald-800 dark:text-emerald-200 mx-0.5"
          style={{ fontFamily: "'Amiri', serif" }}>
          {m[1]}
        </span>
      ));

    // ── Apply best match ──

    if (best) {
      if (best.index > 0) {
        nodes.push(<span key={key++}>{remaining.slice(0, best.index)}</span>);
      }
      nodes.push(best.node);
      remaining = remaining.slice(best.index + best.length);
    } else {
      nodes.push(<span key={key++}>{remaining}</span>);
      break;
    }

    // Helper: match pattern and update best if earlier
    function match(
      str: string,
      pattern: RegExp,
      makeNode: (m: RegExpMatchArray) => React.ReactNode
    ) {
      const m = str.match(pattern);
      if (m && m.index !== undefined && (!best || m.index < best.index)) {
        best = { index: m.index, length: m[0].length, node: makeNode(m) };
      }
    }
  }

  return nodes;
}

/* ═══════════════════════════════════════════
   REUSABLE COMPONENTS
   ═══════════════════════════════════════════ */

function GoldBadge({ text }: { text: string }) {
  // Clean up: remove #N/A, extra spaces
  const clean = text.replace(/#?N\/A/gi, '').replace(/\s+/g, ' ').trim();
  if (clean.length < 3) return null;
  
  // Determine badge style based on content
  const isQuran = clean.includes('📖') || /Surah|Quran/i.test(clean);
  const isIjma = clean.includes('Ijma') || clean.includes('Consensus') || clean.includes('⚖️') && clean.includes('Consensus');
  const isQiyas = clean.includes('Qiyas') || clean.includes('Analogy');
  
  let badgeClass = "inline-flex items-center mx-1 px-2.5 py-0.5 text-xs font-semibold rounded-full shadow-sm whitespace-nowrap ";
  
  if (isIjma) {
    // Green for Ijma (consensus)
    badgeClass += "bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-600";
  } else if (isQiyas) {
    // Purple for Qiyas (analogy)
    badgeClass += "bg-purple-50 text-purple-800 border border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-600";
  } else if (isQuran) {
    // Blue for Quran
    badgeClass += "bg-blue-50 text-blue-800 border border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-600";
  } else {
    // Amber for Hadith (default)
    badgeClass += "bg-amber-50 text-amber-800 border border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-600";
  }
  
  return (
    <span className={badgeClass}>
      {clean}
    </span>
  );
}

export default FormattedMessage;
