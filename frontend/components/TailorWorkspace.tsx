"use client";

import { useState, useRef, useEffect, CSSProperties } from "react";
import Link from "next/link";
import axios from "axios";
import { tk } from "@/lib/tokens";
import type { TailorDrafts } from "@/lib/tailor";
import TailorReview from "./TailorReview";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

type Stage = "idle" | "tailoring" | "review" | "error";

export default function TailorWorkspace() {
  const [file, setFile] = useState<File | null>(null);
  const [plainText, setPlainText] = useState("");
  const [inputMode, setInputMode] = useState<"file" | "text">("file");
  const [jobDescription, setJobDescription] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<Stage>("idle");
  const [drafts, setDrafts] = useState<TailorDrafts | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [aiReady, setAiReady] = useState<boolean | null>(null);

  // Surface whether the server has an OpenAI key, so the user gets a clear
  // message before spending a click rather than a 503 after.
  useEffect(() => {
    if (!API_URL) return;
    fetch(`${API_URL}/tailor/status`)
      .then((r) => r.json())
      .then((d) => setAiReady(!!d.configured))
      .catch(() => setAiReady(null));
  }, []);

  const hasResume = inputMode === "file" ? !!file : !!plainText.trim();
  const canSubmit = stage !== "tailoring" && hasResume && !!jobDescription.trim();

  const tailor = async () => {
    if (!canSubmit) return;
    if (!API_URL) {
      setError("This app isn't configured with a backend URL (NEXT_PUBLIC_API_URL).");
      setStage("error");
      return;
    }
    setStage("tailoring");
    setError("");
    setDrafts(null);

    const fd = new FormData();
    if (inputMode === "file" && file) fd.append("file", file);
    else fd.append("plain_text", plainText);
    fd.append("job_description", jobDescription);
    if (jobUrl.trim()) fd.append("job_url", jobUrl.trim());

    try {
      const res = await axios.post(`${API_URL}/tailor`, fd, { timeout: 120000 });
      setDrafts(res.data as TailorDrafts);
      setStage("review");
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail || `Couldn't reach the API at ${API_URL}.`
        : err instanceof Error
        ? err.message
        : "Something went wrong.";
      setError(msg);
      setStage("error");
    }
  };

  const startOver = () => {
    setStage("idle");
    setDrafts(null);
    setError("");
  };

  if (stage === "review" && drafts) {
    return <TailorReview drafts={drafts} apiUrl={API_URL} onStartOver={startOver} />;
  }

  return (
    <div style={shell}>
      <Header />
      <main style={main}>
        <BetaBanner />
        <h1 style={h1}>Tailor to a job</h1>
        <p style={sub}>
          Upload your resume and paste the job description. We draft a JD-tailored resume, a cover
          letter, and an HR email - all editable before you download. The result is AI-written, so
          review every line (especially the <code style={codeTag}>[placeholders]</code>) before sending.
        </p>

        {aiReady === false && (
          <Notice tone="warn">
            Tailoring is temporarily unavailable. Please try again later.
          </Notice>
        )}

        {/* Resume input */}
        <Card>
          <Label>Your resume</Label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
            <Toggle active={inputMode === "file"} onClick={() => setInputMode("file")}>
              Upload file
            </Toggle>
            <Toggle active={inputMode === "text"} onClick={() => setInputMode("text")}>
              Paste text
            </Toggle>
          </div>

          {inputMode === "file" ? (
            <div
              role="button"
              tabIndex={0}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
              style={dropzone(dragging, !!file)}
            >
              <input ref={fileInputRef} type="file" accept=".pdf,.docx" style={{ display: "none" }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }} />
              <p style={{ margin: 0, fontSize: "14px", fontWeight: file ? 600 : 400, color: file ? tk.greenInteractive : tk.onSurfaceSecondary }}>
                {file ? file.name : "Drop your resume or click to browse (PDF or DOCX)"}
              </p>
              {file && (
                <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                  style={{ background: "none", border: "none", color: tk.onSurfaceTertiary, fontSize: "12px", cursor: "pointer", marginTop: "6px" }}>
                  × Remove
                </button>
              )}
            </div>
          ) : (
            <textarea value={plainText} onChange={(e) => setPlainText(e.target.value)} rows={8}
              placeholder="Paste your full resume text here…" style={textarea} />
          )}
        </Card>

        {/* JD input */}
        <Card>
          <Label>Job description</Label>
          <textarea value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} rows={9}
            placeholder="Paste the job description here…" style={textarea} />
          <div style={{ marginTop: "12px" }}>
            <Label>Job link (optional)</Label>
            <input type="url" value={jobUrl} onChange={(e) => setJobUrl(e.target.value)}
              placeholder="https://… we'll try to read it and add to the description above" style={input} />
            <p style={{ margin: "6px 0 0", fontSize: "12px", color: tk.onSurfaceTertiary }}>
              Some job boards block scraping. If a link doesn't work, just paste the text.
            </p>
          </div>
        </Card>

        {error && <Notice tone="error">{error}</Notice>}

        <button type="button" onClick={tailor} disabled={!canSubmit} style={submitBtn(canSubmit)}>
          {stage === "tailoring" ? "Tailoring… this can take ~20s" : "Tailor my application →"}
        </button>
        {stage === "tailoring" && (
          <div style={{ marginTop: "14px" }}>
            <Spinner />
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}

/* ── Beta banner (test mode) ────────────────────────────────────────────── */
function BetaBanner() {
  return (
    <div style={betaBanner}>
      <span style={betaPill}>BETA</span>
      <span style={{ fontSize: "13px", color: tk.onSurfaceSecondary }}>
        Test mode — AI-generated drafts. Always review and edit before you send.
      </span>
    </div>
  );
}

/* ── small UI atoms (reuse the app's tokens / inline-style convention) ───── */
function Header() {
  return (
    <header style={headerStyle}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
        <Asterisk />
        <span style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface }}>Resume Formatter</span>
      </Link>
      <nav style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "18px" }}>
        <Link href="/format" style={navLink}>Format</Link>
        <span style={{ fontSize: "12.5px", color: tk.onSurfaceTertiary }}>Tailor (beta)</span>
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer style={footerStyle}>
      <span style={{ fontFamily: tk.serif, fontSize: "13.5px", color: tk.onSurfaceSecondary }}>Resume Formatter</span>
      <span style={{ fontSize: "12px", color: tk.onSurfaceTertiary }}>Tailor • beta</span>
    </footer>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div style={card}>{children}</div>;
}
function Label({ children }: { children: React.ReactNode }) {
  return <span style={labelStyle}>{children}</span>;
}
function Toggle({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} style={{
      padding: "7px 14px", borderRadius: "8px", fontSize: "13px", fontWeight: 500, cursor: "pointer",
      border: `1px solid ${active ? tk.clayInteractive : tk.borderSecondary}`,
      background: active ? tk.clayInteractive : "#fff", color: active ? "#faf9f5" : tk.onSurfaceSecondary,
    }}>{children}</button>
  );
}
function Notice({ tone, children }: { tone: "warn" | "error"; children: React.ReactNode }) {
  const color = tone === "error" ? tk.red : "#9a6b00";
  return (
    <p role="alert" style={{ fontSize: "13px", color, margin: "4px 0 16px", padding: "12px 14px", background: "#fff",
      borderRadius: "8px", border: `1px solid ${color}`, lineHeight: 1.5 }}>{children}</p>
  );
}
function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", color: tk.clayInteractive, fontSize: "13px" }}>
      <span style={spinnerDot} /> Drafting your resume, cover letter, and email…
    </div>
  );
}
function Asterisk() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={tk.clay} strokeWidth="2" strokeLinecap="round" aria-hidden>
      <line x1="12" y1="2" x2="12" y2="22" /><line x1="2" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /><line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}

/* ── styles ──────────────────────────────────────────────────────────────── */
const shell: CSSProperties = { minHeight: "100vh", display: "flex", flexDirection: "column", background: tk.surface, fontFamily: tk.sans };
const headerStyle: CSSProperties = { height: "60px", display: "flex", alignItems: "center", padding: "0 clamp(16px,4vw,28px)", borderBottom: `1px solid ${tk.borderTertiary}`, background: "#faf9f5", position: "sticky", top: 0, zIndex: 40 };
const footerStyle: CSSProperties = { marginTop: "auto", borderTop: `1px solid ${tk.borderTertiary}`, background: tk.surfaceSecondary, padding: "16px clamp(16px,4vw,40px)", display: "flex", justifyContent: "space-between", alignItems: "center" };
const main: CSSProperties = { flex: 1, width: "100%", maxWidth: "760px", margin: "0 auto", padding: "30px clamp(16px,4vw,28px) 60px" };
const betaBanner: CSSProperties = { display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", borderRadius: "10px", background: tk.surfaceTertiary, border: `1px solid ${tk.borderSecondary}`, marginBottom: "22px" };
const betaPill: CSSProperties = { fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", color: "#fff", background: tk.clayInteractive, padding: "3px 8px", borderRadius: "6px" };
const h1: CSSProperties = { fontFamily: tk.serif, fontSize: "clamp(24px,6.4vw,30px)", fontWeight: 500, color: tk.onSurface, margin: "0 0 10px" };
const sub: CSSProperties = { fontSize: "clamp(14px,3.6vw,15px)", color: tk.onSurfaceTertiary, margin: "0 0 26px", lineHeight: 1.55 };
const codeTag: CSSProperties = { fontFamily: "ui-monospace, monospace", fontSize: "12.5px", background: tk.surfaceTertiary, padding: "1px 5px", borderRadius: "4px" };
const card: CSSProperties = { background: "#fff", border: `1px solid ${tk.borderTertiary}`, borderRadius: "12px", padding: "18px", marginBottom: "18px" };
const labelStyle: CSSProperties = { display: "block", fontSize: "12px", fontWeight: 600, color: tk.onSurfaceSecondary, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "8px" };
const textarea: CSSProperties = { width: "100%", fontFamily: tk.sans, fontSize: "14px", lineHeight: 1.55, padding: "12px", borderRadius: "8px", border: `1px solid ${tk.borderSecondary}`, outline: "none", background: "#fff", color: tk.onSurface, resize: "vertical", boxSizing: "border-box" };
const input: CSSProperties = { ...textarea, resize: "none" } as CSSProperties;
const dropzone = (drag: boolean, has: boolean): CSSProperties => ({ border: `2px dashed ${has ? tk.green : drag ? tk.clay : tk.borderSecondary}`, borderRadius: "8px", padding: "26px", textAlign: "center", cursor: "pointer", background: has ? tk.greenSurface : drag ? "#fff" : "#fff" });
const submitBtn = (on: boolean): CSSProperties => ({ width: "100%", padding: "15px", borderRadius: "10px", fontSize: "15px", fontWeight: 600, cursor: on ? "pointer" : "not-allowed", border: `1px solid ${on ? tk.clayInteractive : tk.borderTertiary}`, background: on ? tk.clayInteractive : tk.surfaceTertiary, color: on ? "#faf9f5" : tk.onSurfaceTertiary });
const navLink: CSSProperties = { fontSize: "13px", color: tk.onSurfaceSecondary, textDecoration: "none" };
const spinnerDot: CSSProperties = { width: "12px", height: "12px", borderRadius: "50%", border: `2px solid ${tk.clay}`, borderTopColor: "transparent", display: "inline-block", animation: "rf-spin 0.8s linear infinite" };
