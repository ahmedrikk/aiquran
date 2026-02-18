import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import React from 'react';

// ── Arabic detection ───────────────────────────────────────────────────────
const HAS_ARABIC = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/;

function isArabicLine(text: string): boolean {
  const stripped = text.replace(/\s/g, "");
  if (stripped.length < 3) return false;
  const arabicCount = [...stripped].filter((c) => HAS_ARABIC.test(c)).length;
  return arabicCount / stripped.length > 0.4;
}

// ── Reference tagging ──────────────────────────────────────────────────────

// 1. Natural language Surah References:
//    "Surah 7, verse 180", "Surah Al-Baqarah 2:155", "(Quran 7:28)"
//    Matches: Surah Name (optional), Chapter:Verse or Chapter, verse Verse
const SURAH_SRC = [
  // Pattern A: "Surah Al-Baqarah 2:155" or "Surah 7, verse 180"
  /(?:Surah\s+(?:[A-Z][A-Za-z'-]*\s*)*)?\d{1,3}(?::\d{1,3}|,\s*verse\s*\d{1,3})/,
  // Pattern B: "(Quran 7:28)"
  /\(Quran\s+\d{1,3}:\d{1,3}\)/,
  // Pattern C: Standard "2:155" but carefully to avoid times (requires context usually, but here we can be a bit aggressive if "Surah" is near, or just match explicit "Surah X:Y")
  /Surah\s+[A-Z][A-Za-z'-]*(?:\s+[A-Za-z'-]+)*\s*\(?\d{1,3}:\d{1,3}(?:-\d{1,3})?\)?/
].map(r => r.source).join("|");

// Combined and robust regex for Quran citations
const QURAN_REGEX = new RegExp(`(?:${SURAH_SRC})`, 'gi');

// 2. Hadith References
//    "Sahih Bukhari [#5590]", "Muslim 1234", "Sunan Abi Dawud 4000"
const HADITH_SRC =
  "(?:Sahih\\s+)?(?:Bukhari|Muslim|Tirmidhi|Abu\\s+Dawud|Nasa[\u2019']?i|Ibn\\s+Majah|Muwatta|Ahmad)\\s*(?:\\[)?#?\\d+(?:\\])?";

const HADITH_REGEX = new RegExp(HADITH_SRC, "gi");

// Wrap detected references in backtick markers so the ReactMarkdown `code`
// renderer can intercept them and render as gold badge pills.
function tagRefs(text: string): string {
  // We use replace with a callback to avoid replacing inside existing code blocks
  // (Simplified for now: we assume LLM doesn't output code blocks with these patterns inside)

  let out = text.replace(HADITH_REGEX, (m) => `\`__H__${m}\``);
  // Using a specific token for Quran to differ styles if needed, or same style
  out = out.replace(QURAN_REGEX, (m) => `\`__S__${m}\``);
  return out;
}

// ── Content segmentation ───────────────────────────────────────────────────
// Split content line-by-line; collect runs of Arabic lines into "arabic"
// segments and everything else into "markdown" segments.
type Segment = { type: "arabic"; text: string } | { type: "markdown"; text: string };

function segmentContent(content: string): Segment[] {
  const lines = content.split("\n");
  const segments: Segment[] = [];
  let mdLines: string[] = [];

  const flushMd = () => {
    const joined = mdLines.join("\n").trim();
    if (joined) segments.push({ type: "markdown", text: joined });
    mdLines = [];
  };

  for (const line of lines) {
    if (isArabicLine(line)) {
      flushMd();
      segments.push({ type: "arabic", text: line.trim() });
    } else {
      mdLines.push(line);
    }
  }
  flushMd();
  return segments;
}

// ── Shared badge style ─────────────────────────────────────────────────────
const BADGE =
  "bg-amber-100 text-amber-800 border border-amber-300 rounded-full px-3 py-0.5 font-semibold text-sm inline-block whitespace-nowrap mx-0.5 my-0.5 align-middle shadow-sm";

// ── Arabic block ───────────────────────────────────────────────────────────
function ArabicBlock({ text }: { text: string }) {
  return (
    <div
      dir="rtl"
      className="w-full my-4 px-6 py-4 bg-[#FDFBF7] dark:bg-[#1E293B] rounded-xl border-r-4 border-[#D4AF37] shadow-sm"
    >
      <p
        style={{
          fontFamily: "'Amiri', serif",
          fontSize: "1.6em",
          lineHeight: 2.2,
          textAlign: "center",
          color: "#064E3B" // Islamic green
        }}
        className="dark:text-emerald-100"
      >
        {text}
      </p>
    </div>
  );
}

// ── Markdown block with all custom renderers ───────────────────────────────
function MarkdownBlock({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Intercept inline code spans to render Surah/Hadith badges
        code({ className, children }) {
          const raw = String(children).trim();

          if (raw.startsWith("__S__"))
            return <span className={BADGE}>📖 {raw.slice(5)}</span>;
          if (raw.startsWith("__H__"))
            return <span className={BADGE}>📜 {raw.slice(5)}</span>;

          const lang = /language-(\w+)/.exec(className || "")?.[1];
          if (lang) {
            return (
              <SyntaxHighlighter
                language={lang}
                style={oneDark}
                customStyle={{ margin: 0, borderRadius: "0.75rem", fontSize: "0.8rem" }}
              >
                {raw.replace(/\n$/, "")}
              </SyntaxHighlighter>
            );
          }
          return (
            <code className="bg-slate-100 dark:bg-slate-800 rounded px-1.5 py-0.5 text-[0.85em] font-mono text-primary dark:text-emerald-300 border border-slate-200 dark:border-slate-700">
              {children}
            </code>
          );
        },
        pre({ children }) {
          return <div className="my-3 rounded-xl overflow-hidden text-sm shadow-md">{children}</div>;
        },
        // Bold → emerald for emphasis
        strong({ children }) {
          return (
            <strong className="font-bold text-emerald-800 dark:text-emerald-400">
              {children}
            </strong>
          );
        },
        // Italic -> Stylized quote
        em({ children }) {
          return (
            <span className="italic text-slate-600 dark:text-slate-400 font-serif">
              {children}
            </span>
          );
        },
        // Blockquote (*"quoted translation"*) → gold left border with background
        blockquote({ children }) {
          return (
            <blockquote className="border-l-4 border-amber-400/50 bg-amber-50/50 dark:bg-amber-900/10 pl-4 py-2 pr-2 italic text-slate-700 dark:text-slate-300 my-4 rounded-r-lg">
              {children}
            </blockquote>
          );
        },
        p({ children }) {
          // Check for inline Arabic to apply Amiri font
          const kids = React.Children.toArray(children);
          const hasArabic = kids.some(k => typeof k === 'string' && HAS_ARABIC.test(k));

          if (hasArabic) {
            return (
              <p className="mb-3 last:mb-0 leading-loose text-gray-800 dark:text-gray-200">
                {React.Children.map(children, child => {
                  if (typeof child === 'string') {
                    // Split by non-Arabic parts to isolate Arabic words
                    const parts = child.split(/([\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\s]+)/g);
                    return parts.map((part, i) => {
                      if (HAS_ARABIC.test(part)) {
                        return <span key={i} style={{ fontFamily: "Amiri, serif", fontSize: "1.25em" }}>{part}</span>;
                      }
                      return part;
                    });
                  }
                  return child;
                })}
              </p>
            );
          }
          return <p className="mb-3 last:mb-0 leading-relaxed text-gray-800 dark:text-gray-200">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 mb-4 space-y-1 marker:text-emerald-600 dark:marker:text-emerald-500">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 mb-4 space-y-1 marker:text-emerald-600 dark:marker:text-emerald-500">{children}</ol>;
        },
        h1({ children }) {
          return <h1 className="text-2xl font-bold text-emerald-900 dark:text-emerald-100 mb-4 mt-6 border-b border-emerald-100 dark:border-emerald-900/30 pb-2">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-xl font-bold text-emerald-800 dark:text-emerald-200 mb-3 mt-5">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-lg font-semibold text-emerald-700 dark:text-emerald-300 mb-2 mt-4">{children}</h3>;
        },
        a({ href, children }) {
          return <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300 underline underline-offset-2 transition-colors">{children}</a>
        }
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

// ── Main export ────────────────────────────────────────────────────────────
export default function FormattedMessage({ content }: { content: string }) {
  const segments = segmentContent(content);

  return (
    <div className="space-y-1 text-[15px]">
      {segments.map((seg, i) =>
        seg.type === "arabic" ? (
          <ArabicBlock key={i} text={seg.text} />
        ) : (
          <MarkdownBlock key={i} text={tagRefs(seg.text)} />
        )
      )}
    </div>
  );
}
