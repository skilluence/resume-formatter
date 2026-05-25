"use client";

import { useState, useRef, useCallback, CSSProperties } from "react";
import Link from "next/link";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type Stage = "idle" | "uploading" | "formatting" | "done" | "error";

interface Result {
  job_id: string;
  candidate_name: string;
}

/* ─────────────────────────────────────────────
   Claude-brand-inspired design tokens (CSS vars)
───────────────────────────────────────────── */
const tk = {
  surface: "var(--color-surface, #faf9f5)",
  surfaceSecondary: "var(--color-surface-secondary, #f5f4ed)",
  surfaceTertiary: "var(--color-surface-tertiary, #f0eee6)",
  surfaceDark: "var(--color-surface-dark, #1a1918)",
  clay: "var(--color-clay, #d97757)",
  clayInteractive: "var(--color-clay-interactive, #c96442)",
  onSurface: "var(--color-on-surface, #141413)",
  onSurfaceSecondary: "var(--color-on-surface-secondary, #30302e)",
  onSurfaceTertiary: "var(--color-on-surface-tertiary, #5e5d59)",
  onSurfaceGhost: "var(--color-on-surface-ghost, #9c9a92)",
  borderTertiary: "var(--color-border-tertiary, #e8e6dc)",
  borderSecondary: "var(--color-border-secondary, #d1cfc5)",
  onDarkMuted: "var(--color-on-dark-muted, #9c9a92)",
  serif: "var(--font-lora, Georgia, serif)",
  sans: "var(--font-inter, Inter, system-ui, sans-serif)",
} as const;

/* ─── Asterisk brand mark (clay, matches Anthropic style) ─── */
function AsteriskMark({ size = 20, color = tk.clay }: { size?: number; color?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      <line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}

/* ─── Inline icon helpers ─── */
function IconUpload({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}
function IconDownload({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
function IconCheck({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function IconFile({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  );
}
function IconSpinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="animate-spin">
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-80" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

/* ─── Small reusable styled chip ─── */
function Chip({ label }: { label: string }) {
  return (
    <span
      style={{
        fontFamily: tk.sans,
        fontSize: "12px",
        backgroundColor: tk.surfaceSecondary,
        color: tk.onSurfaceTertiary,
        border: `1px solid ${tk.borderTertiary}`,
        borderRadius: "6px",
        padding: "4px 10px",
        display: "inline-block",
      }}
    >
      {label}
    </span>
  );
}

/* ─── Step card for "How it works" section ─── */
function StepCard({ step, title, desc }: { step: string; title: string; desc: string }) {
  return (
    <div
      style={{
        backgroundColor: tk.surface,
        border: `1px solid ${tk.borderTertiary}`,
        borderRadius: "12px",
        padding: "24px",
      }}
    >
      <span
        style={{
          fontFamily: tk.sans,
          fontSize: "11px",
          fontWeight: 500,
          letterSpacing: "0.12em",
          color: tk.clay,
          display: "block",
          marginBottom: "12px",
          textTransform: "uppercase",
        }}
      >
        {step}
      </span>
      <h3
        style={{
          fontFamily: tk.serif,
          fontSize: "17px",
          fontWeight: 500,
          color: tk.onSurface,
          marginBottom: "6px",
          lineHeight: 1.3,
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontFamily: tk.sans,
          fontSize: "14px",
          color: tk.onSurfaceTertiary,
          lineHeight: 1.6,
          margin: 0,
        }}
      >
        {desc}
      </p>
    </div>
  );
}

/* ═══════════════════════════════════════════
   MAIN PAGE
═══════════════════════════════════════════ */
export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [plainText, setPlainText] = useState("");
  const [inputMode, setInputMode] = useState<"file" | "text">("file");
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [textareaFocused, setTextareaFocused] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleFormat = async () => {
    if (!file && !plainText.trim()) return;
    setStage("uploading");
    setError("");
    setResult(null);

    const formData = new FormData();
    if (file) formData.append("file", file);
    else formData.append("plain_text", plainText);
    formData.append("format_type", "compact");

    try {
      setStage("formatting");
      const res = await axios.post(`${API_URL}/format`, formData);
      setResult(res.data);
      setStage("done");
    } catch (err: unknown) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || "Something went wrong."
        : "Something went wrong.";
      setError(message);
      setStage("error");
    }
  };

  const downloadFile = (format: "docx" | "pdf") => {
    if (!result) return;
    window.open(`${API_URL}/download/${result.job_id}/${format}`, "_blank");
  };

  const reset = () => {
    setFile(null);
    setPlainText("");
    setStage("idle");
    setResult(null);
    setError("");
  };

  const isLoading = stage === "uploading" || stage === "formatting";
  const canSubmit = !isLoading && (!!file || !!plainText.trim());

  /* ─── Drop zone styles (dynamic) ─── */
  const dropZoneStyle: CSSProperties = {
    border: `2px dashed ${
      dragging ? "#d97757" : file ? "#7aab7e" : tk.borderSecondary
    }`,
    borderRadius: "10px",
    padding: "40px 20px",
    textAlign: "center",
    cursor: "pointer",
    transition: "all 0.2s ease",
    backgroundColor: dragging
      ? tk.surfaceTertiary
      : file
      ? "#f0f7f0"
      : tk.surfaceSecondary,
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: tk.surface, fontFamily: tk.sans }}
    >
      {/* ═══════════ NAVBAR ═══════════ */}
      <header
        className="sticky top-0 z-50"
        style={{
          height: "64px",
          backgroundColor: "color-mix(in srgb, #faf9f5 92%, transparent)",
          backdropFilter: "saturate(180%) blur(10px)",
          WebkitBackdropFilter: "saturate(180%) blur(10px)",
          borderBottom: `1px solid ${tk.borderTertiary}`,
          display: "flex",
          alignItems: "center",
          padding: "0 24px",
        }}
      >
        <div
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Link href="/" className="flex items-center gap-2.5 no-underline min-w-0">
            <AsteriskMark size={18} color={tk.clay} />
            <span
              className="truncate text-[15px] sm:text-base"
              style={{
                fontFamily: tk.serif,
                fontWeight: 500,
                color: tk.onSurface,
                letterSpacing: "-0.01em",
              }}
            >
              Resume Formatter
            </span>
          </Link>
          <nav style={{ marginLeft: "auto", display: "flex", gap: "4px" }}>
            <Link
              href="/"
              style={{
                fontFamily: tk.sans,
                fontSize: "13px",
                fontWeight: 500,
                color: tk.clayInteractive,
                backgroundColor: "color-mix(in srgb, #c96442 10%, white)",
                textDecoration: "none",
                padding: "6px 12px",
                borderRadius: "6px",
              }}
            >
              Format
            </Link>
            <Link
              href="/builder"
              style={{
                fontFamily: tk.sans,
                fontSize: "13px",
                fontWeight: 500,
                color: tk.onSurfaceTertiary,
                textDecoration: "none",
                padding: "6px 12px",
                borderRadius: "6px",
              }}
            >
              Build
            </Link>
          </nav>
        </div>
      </header>

      {/* ═══════════ MAIN ═══════════ */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>

        {/* ─── Hero Section ─── */}
        <section
          style={{
            padding: "clamp(64px, 10vw, 120px) 24px clamp(48px, 6vw, 80px)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div style={{ width: "100%", maxWidth: "640px" }}>

            {/* Headline */}
            <div style={{ textAlign: "center", marginBottom: "40px" }}>
              <span
                style={{
                  fontFamily: tk.sans,
                  fontSize: "11px",
                  fontWeight: 500,
                  letterSpacing: "0.14em",
                  color: tk.clay,
                  textTransform: "uppercase",
                  display: "inline-block",
                  marginBottom: "14px",
                }}
              >
                Format Existing Resume
              </span>
              <h1
                style={{
                  fontFamily: tk.serif,
                  fontSize: "clamp(34px, 5vw, 58px)",
                  fontWeight: 500,
                  color: tk.onSurface,
                  lineHeight: 1.1,
                  letterSpacing: "-0.015em",
                  marginBottom: "16px",
                }}
              >
                Transform any resume into a{" "}
                <span style={{ color: tk.clay }}>professional format</span>
              </h1>
              <p
                style={{
                  fontFamily: tk.sans,
                  fontSize: "clamp(16px, 2vw, 19px)",
                  color: tk.onSurfaceTertiary,
                  lineHeight: 1.65,
                  maxWidth: "520px",
                  margin: "0 auto",
                }}
              >
                Upload an unformatted resume — get back a clean, ATS-optimized
                DOCX &amp; PDF in seconds.
              </p>
            </div>

            {/* ─────── Upload Card ─────── */}
            <div
              className="p-4 sm:p-6"
              style={{
                backgroundColor: "#ffffff",
                border: `1px solid ${tk.borderTertiary}`,
                borderRadius: "16px",
                boxShadow: "rgba(20, 20, 19, 0.04) 0px 2px 6px, rgba(20, 20, 19, 0.02) 0px 8px 24px",
                display: "flex",
                flexDirection: "column",
                gap: "18px",
              }}
            >
              {/* Mode toggle chips */}
              <div style={{ display: "flex", gap: "8px" }}>
                {(["file", "text"] as const).map((mode) => {
                  const active = inputMode === mode;
                  return (
                    <button
                      key={mode}
                      onClick={() => setInputMode(mode)}
                      style={{
                        fontFamily: tk.sans,
                        fontSize: "14px",
                        padding: "6px 14px",
                        borderRadius: "8px",
                        border: `1px solid ${active ? tk.clayInteractive : tk.borderTertiary}`,
                        backgroundColor: active
                          ? "color-mix(in srgb, #c96442 12%, white)"
                          : tk.surfaceSecondary,
                        color: active ? tk.clayInteractive : tk.onSurfaceTertiary,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                        fontWeight: active ? 500 : 400,
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      {mode === "file" ? (
                        <>
                          <IconUpload size={14} />
                          Upload File
                        </>
                      ) : (
                        <>
                          <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.75}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6M9 16h6M17 21H7a2 2 0 01-2-2V5a2 2 0 012-2h7l5 5v11a2 2 0 01-2 2z" />
                          </svg>
                          Paste Text
                        </>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* File Drop Zone */}
              {inputMode === "file" && (
                <div
                  style={dropZoneStyle}
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.doc"
                    style={{ display: "none" }}
                    onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
                  />

                  {file ? (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
                      <div style={{ color: "#5a9a5f" }}>
                        <IconFile size={36} />
                      </div>
                      <p
                        style={{
                          fontFamily: tk.sans,
                          fontWeight: 500,
                          fontSize: "14px",
                          color: "#4a7a4e",
                          margin: 0,
                        }}
                      >
                        {file.name}
                      </p>
                      <p
                        style={{
                          fontFamily: tk.sans,
                          fontSize: "12px",
                          color: tk.onSurfaceGhost,
                          margin: 0,
                        }}
                      >
                        {(file.size / 1024).toFixed(1)} KB · click to change
                      </p>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                      <div style={{ color: tk.onSurfaceGhost }}>
                        <svg width="40" height="40" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.25}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                      </div>
                      <p
                        style={{
                          fontFamily: tk.sans,
                          fontSize: "14px",
                          color: tk.onSurfaceTertiary,
                          margin: 0,
                        }}
                      >
                        Drag &amp; drop your resume or{" "}
                        <span style={{ color: tk.clayInteractive, fontWeight: 500 }}>
                          browse files
                        </span>
                      </p>
                      <p
                        style={{
                          fontFamily: tk.sans,
                          fontSize: "12px",
                          color: tk.onSurfaceGhost,
                          margin: 0,
                        }}
                      >
                        Supports PDF, DOCX
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Paste Text Zone */}
              {inputMode === "text" && (
                <textarea
                  rows={9}
                  placeholder="Paste your resume text here…"
                  value={plainText}
                  onChange={(e) => setPlainText(e.target.value)}
                  onFocus={() => setTextareaFocused(true)}
                  onBlur={() => setTextareaFocused(false)}
                  style={{
                    fontFamily: tk.sans,
                    fontSize: "15px",
                    color: tk.onSurface,
                    backgroundColor: tk.surfaceSecondary,
                    border: `1px solid ${textareaFocused ? tk.clayInteractive : tk.borderSecondary}`,
                    borderRadius: "10px",
                    padding: "14px 16px",
                    resize: "none",
                    outline: "none",
                    lineHeight: 1.6,
                    transition: "border-color 0.2s ease, box-shadow 0.2s ease",
                    boxShadow: textareaFocused
                      ? "0 0 0 3px color-mix(in srgb, #c96442 15%, transparent)"
                      : "none",
                    width: "100%",
                  }}
                />
              )}

              {/* Loading indicator */}
              {isLoading && (
                <div
                  style={{
                    width: "100%",
                    borderRadius: "8px",
                    border: `1px solid color-mix(in srgb, #c96442 35%, transparent)`,
                    backgroundColor: "color-mix(in srgb, #c96442 7%, white)",
                  }}
                >
                  <div className="loader-wrapper" aria-label="Generating">
                    <span className="loader-letter">G</span>
                    <span className="loader-letter">e</span>
                    <span className="loader-letter">n</span>
                    <span className="loader-letter">e</span>
                    <span className="loader-letter">r</span>
                    <span className="loader-letter">a</span>
                    <span className="loader-letter">t</span>
                    <span className="loader-letter">i</span>
                    <span className="loader-letter">n</span>
                    <span className="loader-letter">g</span>
                    <div className="loader" />
                  </div>
                </div>
              )}

              {/* CTA Button */}
              {(stage === "idle" || stage === "error") && (
                <button
                  onClick={handleFormat}
                  disabled={!canSubmit}
                  style={{
                    width: "100%",
                    padding: "13px 18px",
                    borderRadius: "10px",
                    backgroundColor: canSubmit ? tk.clayInteractive : tk.surfaceSecondary,
                    color: canSubmit ? "#faf9f5" : tk.onSurfaceGhost,
                    border: `1px solid ${canSubmit ? tk.clayInteractive : tk.borderTertiary}`,
                    fontFamily: tk.sans,
                    fontSize: "15px",
                    fontWeight: 500,
                    letterSpacing: "0.005em",
                    cursor: canSubmit ? "pointer" : "not-allowed",
                    transition: "transform 0.12s ease, box-shadow 0.15s ease",
                    boxShadow: canSubmit ? "0 1px 2px color-mix(in srgb, #c96442 25%, transparent)" : "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                  }}
                  onMouseEnter={(e) => {
                    if (!canSubmit) return;
                    e.currentTarget.style.boxShadow = "0 4px 14px color-mix(in srgb, #c96442 32%, transparent)";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = canSubmit ? "0 1px 2px color-mix(in srgb, #c96442 25%, transparent)" : "none";
                    e.currentTarget.style.transform = "translateY(0)";
                  }}
                >
                  Format Resume
                  <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" />
                  </svg>
                </button>
              )}

              {/* Error message */}
              {stage === "error" && error && (
                <p
                  style={{
                    fontFamily: tk.sans,
                    fontSize: "13px",
                    color: "#b53333",
                    textAlign: "center",
                    margin: 0,
                  }}
                >
                  {error}
                </p>
              )}

              {/* Feature chips */}
              {stage === "idle" && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    flexWrap: "wrap",
                    paddingTop: "2px",
                  }}
                >
                  {["PDF", "DOCX", "ATS-ready", "AI-powered", "Instant"].map((label) => (
                    <Chip key={label} label={label} />
                  ))}
                </div>
              )}
            </div>

            {/* ─── Result Card ─── */}
            {stage === "done" && result && (
              <div
                className="animate-in fade-in slide-in-from-bottom-4 duration-300 p-4 sm:p-6"
                style={{
                  marginTop: "16px",
                  backgroundColor: tk.surfaceSecondary,
                  border: `1px solid ${tk.borderTertiary}`,
                  borderRadius: "16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "18px",
                }}
              >
                {/* Success header */}
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "50%",
                      backgroundColor: "color-mix(in srgb, #c96442 14%, white)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      color: tk.clayInteractive,
                    }}
                  >
                    <IconCheck size={18} />
                  </div>
                  <div>
                    <p
                      style={{
                        fontFamily: tk.serif,
                        fontSize: "15px",
                        fontWeight: 500,
                        color: tk.onSurface,
                        margin: 0,
                        lineHeight: 1.3,
                      }}
                    >
                      Resume formatted successfully
                    </p>
                    <p
                      style={{
                        fontFamily: tk.sans,
                        fontSize: "12px",
                        color: tk.onSurfaceGhost,
                        margin: "3px 0 0",
                      }}
                    >
                      {result.candidate_name}
                    </p>
                  </div>
                </div>

                {/* Download buttons */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                  {/* DOCX – outlined */}
                  <button
                    onClick={() => downloadFile("docx")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "7px",
                      padding: "12px",
                      borderRadius: "10px",
                      backgroundColor: "#ffffff",
                      color: tk.clayInteractive,
                      border: `1px solid ${tk.clayInteractive}`,
                      fontFamily: tk.sans,
                      fontSize: "14px",
                      fontWeight: 500,
                      cursor: "pointer",
                      transition: "background-color 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor =
                        "color-mix(in srgb, #c96442 8%, white)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "#ffffff";
                    }}
                  >
                    <IconDownload size={14} />
                    Download DOCX
                  </button>

                  {/* PDF – filled clay */}
                  <button
                    onClick={() => downloadFile("pdf")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "7px",
                      padding: "12px",
                      borderRadius: "10px",
                      backgroundColor: tk.clayInteractive,
                      color: "#faf9f5",
                      border: `1px solid ${tk.clayInteractive}`,
                      fontFamily: tk.sans,
                      fontSize: "14px",
                      fontWeight: 500,
                      cursor: "pointer",
                      transition: "transform 0.12s ease, box-shadow 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.boxShadow = "0 4px 14px color-mix(in srgb, #c96442 32%, transparent)";
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.boxShadow = "none";
                      e.currentTarget.style.transform = "translateY(0)";
                    }}
                  >
                    <IconDownload size={14} />
                    Download PDF
                  </button>
                </div>

                <button
                  onClick={reset}
                  style={{
                    background: "none",
                    border: "none",
                    fontFamily: tk.sans,
                    fontSize: "12px",
                    color: tk.onSurfaceGhost,
                    cursor: "pointer",
                    transition: "color 0.2s ease",
                    padding: 0,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = tk.onSurfaceTertiary;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = tk.onSurfaceGhost;
                  }}
                >
                  Format another resume →
                </button>
              </div>
            )}
          </div>
        </section>

        {/* ═══════════ HOW IT WORKS BAND ═══════════ */}
        <section
          style={{
            backgroundColor: tk.surfaceSecondary,
            padding: "clamp(48px, 6vw, 80px) 24px",
          }}
        >
          <div style={{ maxWidth: "640px", margin: "0 auto" }}>
            <h2
              style={{
                fontFamily: tk.serif,
                fontSize: "clamp(22px, 3vw, 30px)",
                fontWeight: 500,
                color: tk.onSurface,
                lineHeight: 1.2,
                textAlign: "center",
                marginBottom: "40px",
              }}
            >
              How it works
            </h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: "12px",
              }}
            >
              <StepCard
                step="01"
                title="Upload or paste"
                desc="Drop in a PDF, DOCX, or paste your resume text directly."
              />
              <StepCard
                step="02"
                title="AI structures it"
                desc="Our model parses, normalises, and structures every section cleanly."
              />
              <StepCard
                step="03"
                title="Download instantly"
                desc="Get a polished ATS-ready DOCX and PDF ready for submission."
              />
            </div>
          </div>
        </section>

        {/* ═══════════ CALLOUT BAND ═══════════ */}
        <section style={{ padding: "clamp(40px, 5vw, 64px) 24px" }}>
          <div style={{ maxWidth: "640px", margin: "0 auto" }}>
            <div
              style={{
                backgroundColor: tk.surfaceTertiary,
                borderRadius: "24px",
                padding: "clamp(28px, 4vw, 48px)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "16px",
                textAlign: "center",
              }}
            >
              <p
                style={{
                  fontFamily: tk.serif,
                  fontSize: "clamp(18px, 2.5vw, 24px)",
                  fontWeight: 500,
                  color: tk.onSurface,
                  lineHeight: 1.3,
                  margin: 0,
                  maxWidth: "420px",
                }}
              >
                Already have a structured resume?
              </p>
              <p
                style={{
                  fontFamily: tk.sans,
                  fontSize: "15px",
                  color: tk.onSurfaceTertiary,
                  lineHeight: 1.6,
                  margin: 0,
                  maxWidth: "380px",
                }}
              >
                Paste your text version and let us reformat it into a clean,
                ATS-optimized document without losing any information.
              </p>
              <button
                onClick={() => {
                  setInputMode("text");
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                style={{
                  fontFamily: tk.sans,
                  fontSize: "15px",
                  fontWeight: 500,
                  backgroundColor: tk.onSurface,
                  color: "#faf9f5",
                  border: `1px solid #30302e`,
                  borderRadius: "8px",
                  padding: "10px 20px",
                  cursor: "pointer",
                  transition: "background-color 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "#1f1e1d";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = tk.onSurface;
                }}
              >
                Try pasting text →
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* ═══════════ FOOTER ═══════════ */}
      <footer
        style={{
          backgroundColor: tk.surfaceDark,
          padding: "40px 24px",
        }}
      >
        <div
          style={{
            maxWidth: "640px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AsteriskMark size={16} color={tk.clay} />
            <span
              style={{
                fontFamily: tk.serif,
                fontSize: "14px",
                fontWeight: 500,
                color: tk.onDarkMuted,
              }}
            >
              Resume Formatter
            </span>
          </div>
          <p
            style={{
              fontFamily: tk.sans,
              fontSize: "12px",
              color: tk.onDarkMuted,
              margin: 0,
            }}
          >
            ATS-ready · AI-powered · Instant
          </p>
        </div>
      </footer>
    </div>
  );
}
