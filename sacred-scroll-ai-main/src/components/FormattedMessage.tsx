import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

// ── Arabic detection ───────────────────────────────────────────────────────
const HAS_ARABIC = /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/;

function isArabicLine(text: string): boolean {
  const stripped = text.replace(/\s/g, "");
  if (stripped.length < 3) return false;
  const arabicCount = [...stripped].filter((c) => HAS_ARABIC.test(c)).length;
  return arabicCount / stripped.length > 0.4;
}

// ── Reference tagging ──────────────────────────────────────────────────────
// Require "Surah" keyword or "Al-" prefix to avoid false positives on "2:155" alone
const SURAH_SRC =
  "(?:Surah\\s+[A-Z][A-Za-z'-]*(?:\\s+[A-Za-z'-]+)*|Al-[A-Z][A-Za-z'-]*(?:\\s+[A-Za-z'-]+)*)\\s*\\(?\\d{1,3}:\\d{1,3}(?:-\\d{1,3})?\\)?";

// Collector name + optional Sahih prefix + #number
const HADITH_SRC =
  "(?:Sahih\\s+)?(?:Bukhari|Muslim|Tirmidhi|Abu\\s+Dawud|Nasa[\u2019']?i|Ibn\\s+Majah|Muwatta|Ahmad)\\s*(?:\\[)?#\\d+(?:\\])?";

// Wrap detected references in backtick markers so the ReactMarkdown `code`
// renderer can intercept them and render as gold badge pills.
function tagRefs(text: string): string {
  // Create fresh regex instances every call — global regexes carry stateful lastIndex
  const hadithRe = new RegExp(HADITH_SRC, "gi");
  const surahRe = new RegExp(SURAH_SRC, "g");
  let out = text.replace(hadithRe, (m) => `\`__H__${m}\``);
  out = out.replace(surahRe, (m) => `\`__S__${m}\``);
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
  "bg-amber-100 text-amber-800 border border-amber-300 rounded-full px-3 py-0.5 font-semibold text-sm inline-block whitespace-nowrap mx-0.5 my-0.5";

// ── Arabic block ───────────────────────────────────────────────────────────
function ArabicBlock({ text }: { text: string }) {
  return (
    <p
      dir="rtl"
      style={{
        fontFamily: "'Amiri', serif",
        fontSize: "1.3em",
        lineHeight: 2.2,
        textAlign: "right",
        borderLeft: "3px solid #D4AF37",
        paddingLeft: "1rem",
        margin: "0.75rem 0",
      }}
    >
      {text}
    </p>
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
            <code className="bg-slate-100 dark:bg-black/30 rounded px-1.5 py-0.5 text-[0.82em] font-mono text-primary dark:text-primary-foreground">
              {children}
            </code>
          );
        },
        pre({ children }) {
          return <div className="my-3 rounded-xl overflow-hidden text-sm">{children}</div>;
        },
        // Bold → emerald
        strong({ children }) {
          return (
            <strong className="font-semibold text-emerald-800 dark:text-emerald-300">
              {children}
            </strong>
          );
        },
        // Blockquote (*"quoted translation"*) → gold left border
        blockquote({ children }) {
          return (
            <blockquote className="border-l-4 border-amber-400/70 pl-4 italic text-slate-600 dark:text-slate-300 my-3">
              {children}
            </blockquote>
          );
        },
        p({ children }) {
          return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>;
        },
        li({ children }) {
          return <li className="leading-relaxed">{children}</li>;
        },
        h1({ children }) {
          return <h1 className="text-xl font-bold text-primary mb-2 mt-3">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-lg font-bold text-primary mb-1 mt-3">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-base font-semibold text-primary mb-1 mt-2">{children}</h3>;
        },
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
    <div className="space-y-1">
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
