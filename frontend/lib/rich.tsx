/* renderRich — the one place the client understands inline **bold** markup, plus
   optional change-highlighting (neon green) and number "verify" flags for the
   AI Tailor preview.

   With no options and no "**", it returns the text unchanged, so the deterministic
   /format preview renders byte-identically — it never passes markup or options. */
import { Fragment, type ReactNode } from "react";

export interface RichOpts {
  /* Terms to paint neon-green (added skills / newly-inserted JD keywords). */
  highlightTerms?: string[];
}

const NEON: React.CSSProperties = {
  background: "#caff5e",
  boxShadow: "0 0 0 1px #aee63a",
  borderRadius: "2px",
  padding: "0 1px",
};

const BOLD_RE = /\*\*(.+?)\*\*/g;

/* Build a case-insensitive alternation that matches any highlight term as a whole
   word (or substring for multiword/symbol terms). Longest-first so "power bi"
   wins over "bi". */
function buildTermRe(terms: string[]): RegExp | null {
  const cleaned = Array.from(new Set(terms.map((t) => t.trim()).filter(Boolean))).sort(
    (a, b) => b.length - a.length
  );
  if (!cleaned.length) return null;
  const parts = cleaned.map((t) => {
    const esc = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return /^[a-z0-9]+$/i.test(t) ? `\\b${esc}\\b` : esc;
  });
  return new RegExp(`(${parts.join("|")})`, "gi");
}

/* Split a plain (no-markup) chunk into nodes, painting highlight terms neon-green. */
function decorate(text: string, key: string, opts: RichOpts): ReactNode {
  const termRe = opts.highlightTerms?.length ? buildTermRe(opts.highlightTerms) : null;
  if (!termRe) return text;
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  for (let m = termRe.exec(text); m; m = termRe.exec(text)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<mark key={`${key}-h${i}`} style={NEON}>{m[0]}</mark>);
    last = m.index + m[0].length;
    i++;
    if (m.index === termRe.lastIndex) termRe.lastIndex++; // guard zero-width
  }
  if (last < text.length) out.push(text.slice(last));
  return <Fragment key={key}>{out}</Fragment>;
}

export function renderRich(text: string, opts: RichOpts = {}): ReactNode {
  const src = text ?? "";
  if (!src) return src;
  // Fast path: no markup, no decoration requested -> return the raw string so the
  // /format preview is unchanged.
  if (!src.includes("**") && !opts.highlightTerms?.length) return src;

  const nodes: ReactNode[] = [];
  let last = 0;
  let i = 0;
  BOLD_RE.lastIndex = 0;
  for (let m = BOLD_RE.exec(src); m; m = BOLD_RE.exec(src)) {
    if (m.index > last) nodes.push(decorate(src.slice(last, m.index), `t${i}`, opts));
    nodes.push(<strong key={`b${i}`}>{decorate(m[1], `bd${i}`, opts)}</strong>);
    last = m.index + m[0].length;
    i++;
  }
  if (last < src.length) nodes.push(decorate(src.slice(last), `tEnd`, opts));
  return <Fragment>{nodes}</Fragment>;
}

/* Strip **markup** to plain text (for measuring / non-React contexts). */
export const plain = (s: string) => (s || "").replace(/\*\*(.+?)\*\*/g, "$1");
