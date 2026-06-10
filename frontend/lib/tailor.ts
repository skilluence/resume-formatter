/* Types + helpers for the AI Tailor (beta) feature. Mirrors the backend
   /tailor response and drives the editable review + downloads. */
import type { Resume } from "./resume";

export interface CoverLetter {
  greeting: string;
  body_paragraphs: string[];
  closing: string;
  signature: string;
}

export interface EmailDraft {
  subject: string;
  greeting: string;
  body_paragraphs: string[];
  closing: string;
  signature: string;
}

/* Per-list delta: what the JD asked for that was missing before tailoring, what is
   still missing after, and what tailoring ADDED (present after, absent before). */
export interface KeywordDelta {
  missing_before: string[];
  missing_after: string[];
  added: string[];
}

export interface MatchInfo {
  score_before: number;
  score_after: number;
  skills: KeywordDelta;
  keywords: KeywordDelta;
  jd_skills: string[];
  jd_keywords: string[];
}

/* The terms to paint neon-green in the preview = everything tailoring added
   (skills + keywords now present that the original resume lacked). */
export function highlightTermsFromMatch(match: MatchInfo): string[] {
  const all = [...(match?.skills?.added || []), ...(match?.keywords?.added || [])];
  const seen = new Set<string>();
  return all.filter((t) => {
    const k = t.trim().toLowerCase();
    if (!k || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

export interface TailorDrafts {
  tailored_resume: Resume;
  original_resume: Resume;
  cover_letter: CoverLetter;
  email: EmailDraft;
  match: MatchInfo;
  /* 4-5 short "what changed" bullets (jobright-style change log). */
  changes: string[];
  gaps: string[];
}


export type TailorKind = "resume" | "cover_letter" | "email";
export type DownloadFormat = "docx" | "pdf";

/* Render the email as a plain-text block for the copy-to-clipboard box and the
   Gmail body. **bold** markup is stripped so it pastes cleanly. */
export function emailToPlainText(email: EmailDraft): string {
  const lines: string[] = [];
  if (email.greeting) lines.push(stripBold(email.greeting), "");
  for (const p of email.body_paragraphs || []) lines.push(stripBold(p), "");
  if (email.closing) lines.push(stripBold(email.closing));
  if (email.signature) lines.push(email.signature);
  return lines.join("\n").trim();
}

export const stripBold = (s: string) => (s || "").replace(/\*\*(.+?)\*\*/g, "$1");

/* True if the text still has an unfilled [placeholder] the user should replace. */
export const hasPlaceholder = (s: string) => /\[[^\]]+\]/.test(s || "");

const triggerBlobDownload = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
};

/* Build one output (resume / cover letter / email) as DOCX or PDF. Retries with
   a warm-up ping for cold-start servers, matching the /format download flow. */
export async function downloadTailorOutput(
  apiUrl: string,
  kind: TailorKind,
  format: DownloadFormat,
  drafts: TailorDrafts,
  baseName: string
): Promise<void> {
  if (!apiUrl) throw new Error("This app isn't configured with a backend URL.");
  const suffix = kind === "resume" ? "Resume" : kind === "cover_letter" ? "CoverLetter" : "Email";
  const filename = `${baseName}_${suffix}.${format}`;
  const body = JSON.stringify({
    kind,
    format,
    tailored_resume: drafts.tailored_resume,
    cover_letter: drafts.cover_letter,
    email: drafts.email,
  });

  let lastErr = "";
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      if (attempt > 0) {
        await fetch(`${apiUrl}/`, { method: "GET" }).catch(() => {});
        await new Promise((r) => setTimeout(r, 800 * attempt));
      }
      const res = await fetch(`${apiUrl}/tailor/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail || `Build failed (HTTP ${res.status}).`);
      }
      triggerBlobDownload(await res.blob(), filename);
      return;
    } catch (e) {
      lastErr = e instanceof Error ? e.message : String(e);
      const isNetwork = e instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(lastErr);
      if (!isNetwork) break;
    }
  }
  throw new Error(lastErr || "Couldn't build the document.");
}
