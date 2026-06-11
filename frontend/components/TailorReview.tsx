"use client";

import { useEffect, useMemo, useState, CSSProperties } from "react";
import Link from "next/link";
import { tk } from "@/lib/tokens";
import {
  type Resume,
  type StatusMap,
  type SectionStatus,
  getSections,
  buildPayload,
  isCoursework,
} from "@/lib/resume";
import SectionCard, { SectionEditor } from "./SectionCard";
import ResumePreview, { type FitInfo } from "./ResumePreview";
import LetterPreview from "./LetterPreview";
import {
  type TailorDrafts,
  type TailorKind,
  type DownloadFormat,
  type MatchInfo,
  downloadTailorOutput,
  emailToPlainText,
  highlightTermsFromMatch,
} from "@/lib/tailor";

type Tab = "resume" | "cover_letter" | "email";

interface Props {
  drafts: TailorDrafts;
  apiUrl: string;
  onStartOver: () => void;
}

export default function TailorReview({ drafts: initial, apiUrl, onStartOver }: Props) {
  const [drafts, setDrafts] = useState<TailorDrafts>(initial);
  const [tab, setTab] = useState<Tab>("resume");
  const [busy, setBusy] = useState<string>("");
  const [err, setErr] = useState("");

  // ── Resume review state (same model as the /format workspace) ──────────────
  const resume = drafts.tailored_resume;
  const [status, setStatusMap] = useState<StatusMap>(() => {
    // Default every section to "kept" so the tailored resume is ready to download
    // immediately; the user can still skip/edit/reorder any of them.
    const s: StatusMap = {};
    getSections(resume).forEach((sec) => (s[sec.id] = "kept"));
    return s;
  });
  const [showGpa, setShowGpa] = useState(true);
  const [showCoursework, setShowCoursework] = useState(() =>
    (resume.education || []).some((e) => (e.details || []).some(isCoursework))
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [dragId, setDragId] = useState<string | null>(null);
  // Page-fill result from the live preview (how many project bullets fit, page count).
  const [fit, setFit] = useState<FitInfo | null>(null);

  const setResume = (r: Resume) => setDrafts((d) => ({ ...d, tailored_resume: r }));

  const baseName = (resume.name || "Application").replace(/[^A-Za-z0-9._-]+/g, "_") || "Application";

  // Neon-green highlights = everything tailoring added (skills + keywords).
  const highlightTerms = useMemo(() => highlightTermsFromMatch(drafts.match), [drafts.match]);
  const highlight = useMemo(() => ({ highlightTerms }), [highlightTerms]);

  // Responsive layout. We track the viewport width and derive two breakpoints:
  //  • wide  (>=1180): two columns + the match card floats over a right gutter.
  //  • stack (< 900):  single column — edit rail and preview stack and the whole
  //                    page scrolls, with a sticky download bar pinned to the
  //                    bottom of the screen.
  // Between them: two columns with the match card inline above the preview.
  const [vw, setVw] = useState(1280);
  useEffect(() => {
    const f = () => setVw(window.innerWidth);
    f();
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);
  const wide = vw >= 1180;
  const stack = vw < 900;
  const narrow = !wide; // match card sits inline (not floating)

  // Section/order helpers (ported from Workspace).
  const sections = getSections(resume);
  const summaryMeta = sections.find((s) => s.id === "summary") || null;
  const bodyIds = sections.filter((s) => s.id !== "summary").map((s) => s.id);
  const orderedBodyIds = [
    ...sectionOrder.filter((id) => bodyIds.includes(id)),
    ...bodyIds.filter((id) => !sectionOrder.includes(id)),
  ];
  const labelOf = (id: string) => sections.find((s) => s.id === id)?.label || id;

  const reorderSection = (from: string, to: string) => {
    if (from === to) return;
    const arr = [...orderedBodyIds];
    const fi = arr.indexOf(from);
    const ti = arr.indexOf(to);
    if (fi < 0 || ti < 0) return;
    arr.splice(ti, 0, arr.splice(fi, 1)[0]);
    setSectionOrder(arr);
  };
  const setStatus = (id: string, v: SectionStatus) => setStatusMap((m) => ({ ...m, [id]: v }));
  const toggleEdit = (id: string) =>
    setEditing((cur) => {
      const next = cur === id ? null : id;
      if (next && id !== "header" && status[id] === "skipped") setStatus(id, "kept");
      return next;
    });
  const skip = (id: string) => {
    setStatus(id, "skipped");
    setEditing((cur) => (cur === id ? null : cur));
  };

  const download = async (kind: TailorKind, format: DownloadFormat) => {
    setErr("");
    setBusy(`${kind}-${format}`);
    try {
      // For the resume, apply the review (skips, GPA, coursework, order) just like
      // /format does, then trim project bullets to exactly what the live preview
      // fitted onto the page so the DOCX matches what's on screen.
      const payload: TailorDrafts =
        kind === "resume"
          ? { ...drafts, tailored_resume: applyFit(buildPayload(resume, status, showGpa, orderedBodyIds, showCoursework), fit) }
          : drafts;
      await downloadTailorOutput(apiUrl, kind, format, payload, baseName);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Download failed.");
    } finally {
      setBusy("");
    }
  };

  // Responsive style variants (computed from the breakpoints above).
  const shellR: CSSProperties = stack ? { ...shell, height: "auto", minHeight: "100vh", overflow: "visible" } : shell;
  const bodyR: CSSProperties = stack ? { ...body, flex: "none", minHeight: 0, display: "block" } : body;
  const tabBarR: CSSProperties = stack ? { ...tabBar, overflowX: "auto" } : tabBar;
  const twoColR: CSSProperties = stack ? { display: "flex", flexDirection: "column" } : twoCol;
  const editColR: CSSProperties = stack
    ? { ...editCol, width: "100%", overflowY: "visible", borderRight: "none", borderTop: `1px solid ${tk.borderTertiary}`, order: 2, padding: "18px clamp(14px,4vw,20px) 100px" }
    : editCol;
  const previewColR: CSSProperties = stack
    ? { ...previewCol, overflowY: "visible", order: 1, padding: "16px clamp(12px,4vw,20px) 24px" }
    : narrow ? previewCol : { ...previewCol, paddingRight: "336px" };
  const scrollPaneR: CSSProperties = stack ? { ...scrollPane, overflowY: "visible", flex: "none" } : scrollPane;
  // Cover-letter tab: editor + live preview, two columns (stack on mobile, preview first).
  const letterColsR: CSSProperties = stack ? { display: "flex", flexDirection: "column" } : twoCol;
  const letterEditR: CSSProperties = stack
    ? { ...editCol, width: "100%", overflowY: "visible", borderRight: "none", borderTop: `1px solid ${tk.borderTertiary}`, order: 2, padding: "18px clamp(14px,4vw,20px) 100px" }
    : editCol;
  const letterPreviewR: CSSProperties = stack
    ? { ...previewCol, overflowY: "visible", order: 1, padding: "16px clamp(12px,4vw,20px) 24px" }
    : previewCol;

  return (
    <div style={shellR}>
      <Header onStartOver={onStartOver} style={stack ? { position: "sticky", top: 0 } : undefined} />
      <div style={betaBanner}>
        <span style={betaPill}>BETA</span>
        <span style={{ fontSize: "13px", color: tk.onSurfaceSecondary }}>
          AI-drafted — review before sending.
        </span>
      </div>

      <div style={tabBarR}>
        <TabBtn active={tab === "resume"} onClick={() => setTab("resume")}>Resume</TabBtn>
        <TabBtn active={tab === "cover_letter"} onClick={() => setTab("cover_letter")}>Cover letter</TabBtn>
        <TabBtn active={tab === "email"} onClick={() => setTab("email")}>HR email</TabBtn>
      </div>

      {err && <p style={errStyle}>{err}</p>}

      <div style={bodyR}>
        {tab === "resume" && (
          <div style={twoColR}>
            {/* LEFT (RIGHT-on-mobile): the same section-card review rail as /format */}
            <aside style={editColR}>
              <ResumeRail
                resume={resume}
                summaryMeta={summaryMeta}
                bodyIds={orderedBodyIds}
                labelOf={labelOf}
                status={status}
                showGpa={showGpa}
                showCoursework={showCoursework}
                editing={editing}
                dragId={dragId}
                busy={busy}
                hideDownload={stack}
                onChange={setResume}
                onKeep={(id) => setStatus(id, "kept")}
                onSkip={skip}
                onToggleEdit={toggleEdit}
                onToggleGpa={() => setShowGpa((v) => !v)}
                onToggleCoursework={() => setShowCoursework((v) => !v)}
                onDownload={download}
                onDragStartSection={(id) => setDragId(id)}
                onDropSection={(id) => { if (dragId) reorderSection(dragId, id); setDragId(null); }}
                onDragEndSection={() => setDragId(null)}
              />
            </aside>
            {/* CENTER: full-width live preview with neon-green change highlights.
                On wide screens we reserve a right gutter so the floating card never covers the page. */}
            <div style={previewColR}>
              {narrow && <div style={{ marginBottom: "14px", maxWidth: "820px", marginLeft: "auto", marginRight: "auto", width: "100%" }}><MatchCard match={drafts.match} changes={drafts.changes} compact /></div>}
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px", flexWrap: "wrap" }}>
                <span style={{ ...previewLabel, marginBottom: 0 }}>Live preview</span>
                <FitChip fit={fit} />
              </div>
              <div style={previewFrame}>
                <ResumePreview resume={resume} status={status} showGpa={showGpa} sectionOrder={orderedBodyIds} showCoursework={showCoursework} highlight={highlight} fitToPages onFit={setFit} />
              </div>
            </div>
            {/* Floating JD-match card, pinned to the middle-right (wide screens). */}
            {wide && (
              <div style={floatWrap}>
                <MatchCard match={drafts.match} changes={drafts.changes} floating />
              </div>
            )}
          </div>
        )}

        {tab === "cover_letter" && (
          <div style={letterColsR}>
            <aside style={letterEditR}>
              <LetterPanel drafts={drafts} onChange={(cl) => setDrafts((d) => ({ ...d, cover_letter: cl }))} onDownload={download} busy={busy} />
            </aside>
            <div style={letterPreviewR}>
              <span style={previewLabel}>Live preview</span>
              <div style={previewFrame}>
                <LetterPreview name={resume.name} headline={resume.headline} contact={resume.contact} letter={drafts.cover_letter} />
              </div>
            </div>
          </div>
        )}
        {tab === "email" && (
          <div style={scrollPaneR}>
            <EmailPanel drafts={drafts} onChange={(em) => setDrafts((d) => ({ ...d, email: em }))} onDownload={download} busy={busy} />
          </div>
        )}
      </div>

      {/* Mobile: a sticky bottom bar keeps the resume download one tap away
          without scrolling past the whole preview to reach the rail. */}
      {stack && tab === "resume" && (
        <div style={mobileDlBar}>
          <button type="button" disabled={!!busy} onClick={() => download("resume", "docx")} style={{ ...dlBtn(true), flex: 1, padding: "12px" }}>
            {busy === "resume-docx" ? "…" : "↓ DOCX"}
          </button>
          <button type="button" disabled={!!busy} onClick={() => download("resume", "pdf")} style={{ ...dlBtn(false), flex: 1, padding: "12px" }}>
            {busy === "resume-pdf" ? "…" : "↓ PDF"}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Resume rail: identical card UX to the formatter's left rail ─────────── */
interface RailProps {
  resume: Resume;
  summaryMeta: { id: string; label: string } | null;
  bodyIds: string[];
  labelOf: (id: string) => string;
  status: StatusMap;
  showGpa: boolean;
  showCoursework: boolean;
  editing: string | null;
  dragId: string | null;
  busy: string;
  hideDownload?: boolean;
  onChange: (r: Resume) => void;
  onKeep: (id: string) => void;
  onSkip: (id: string) => void;
  onToggleEdit: (id: string) => void;
  onToggleGpa: () => void;
  onToggleCoursework: () => void;
  onDownload: (k: TailorKind, f: DownloadFormat) => void;
  onDragStartSection: (id: string) => void;
  onDropSection: (id: string) => void;
  onDragEndSection: () => void;
}
function ResumeRail(p: RailProps) {
  const renderCard = (id: string) => (
    <SectionCard
      id={id}
      label={p.labelOf(id)}
      status={p.status[id] || "pending"}
      editing={p.editing === id}
      isEducation={id === "education"}
      showGpa={p.showGpa}
      showCoursework={p.showCoursework}
      resume={p.resume}
      onChange={p.onChange}
      onKeep={() => p.onKeep(id)}
      onSkip={() => p.onSkip(id)}
      onToggleEdit={() => p.onToggleEdit(id)}
      onToggleGpa={p.onToggleGpa}
      onToggleCoursework={p.onToggleCoursework}
    />
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {/* Download bar pinned to the top of the rail (hidden on mobile, where a
          sticky bottom bar handles the resume download instead). */}
      {!p.hideDownload && (
        <div style={dlCard}>
          <span style={{ fontSize: "12px", color: tk.onSurfaceTertiary, display: "block", marginBottom: "8px" }}>Download tailored resume</span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button type="button" disabled={!!p.busy} onClick={() => p.onDownload("resume", "docx")} style={{ ...dlBtn(true), flex: 1 }}>
              {p.busy === "resume-docx" ? "…" : "↓ DOCX"}
            </button>
            <button type="button" disabled={!!p.busy} onClick={() => p.onDownload("resume", "pdf")} style={{ ...dlBtn(false), flex: 1 }}>
              {p.busy === "resume-pdf" ? "…" : "↓ PDF"}
            </button>
          </div>
        </div>
      )}

      {/* name & headline editor */}
      <div style={cardStyle}>
        <button type="button" onClick={() => p.onToggleEdit("header")} style={{ ...ghostBtn, marginTop: 0, borderColor: p.editing === "header" ? tk.clay : tk.borderSecondary, color: p.editing === "header" ? tk.clayInteractive : tk.onSurfaceSecondary }}>
          {p.editing === "header" ? "Done editing name, contact & headline" : "✎ Edit name, contact & headline"}
        </button>
        {p.editing === "header" && (
          <div style={{ marginTop: "10px" }}>
            <SectionEditor id="header" resume={p.resume} onChange={p.onChange} />
          </div>
        )}
      </div>

      {/* Summary pinned; everything below is drag-to-reorder. */}
      {p.summaryMeta && renderCard(p.summaryMeta.id)}

      {p.bodyIds.length > 1 && (
        <p style={{ fontFamily: tk.sans, fontSize: "11px", color: tk.onSurfaceTertiary, margin: "0 0 -2px", textAlign: "center" }}>
          Drag <span aria-hidden>⠿</span> to reorder sections
        </p>
      )}

      {p.bodyIds.map((id) => (
        <div
          key={id}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); p.onDropSection(id); }}
          style={{ display: "flex", alignItems: "stretch", gap: "6px", opacity: p.dragId === id ? 0.45 : 1 }}
        >
          <div
            draggable
            onDragStart={() => p.onDragStartSection(id)}
            onDragEnd={p.onDragEndSection}
            title="Drag to reorder"
            aria-label={`Reorder ${p.labelOf(id)}`}
            style={{ display: "flex", alignItems: "center", padding: "0 2px", cursor: "grab", color: tk.onSurfaceGhost, fontSize: "16px", userSelect: "none" }}
          >
            ⠿
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>{renderCard(id)}</div>
        </div>
      ))}

      <p style={hint}>
        Facts (name, contact, employers, dates, education, certifications) come straight from your resume.
        Edit any section above; the preview updates live. Skipped sections are dropped from the download.
        Project bullets auto-trim to fill the page cleanly — the live preview shows exactly what downloads.
      </p>
    </div>
  );
}

/* ── Cover letter panel ─────────────────────────────────────────────────── */
function LetterPanel({ drafts, onChange, onDownload, busy }: {
  drafts: TailorDrafts;
  onChange: (cl: TailorDrafts["cover_letter"]) => void;
  onDownload: (k: TailorKind, f: DownloadFormat) => void;
  busy: string;
}) {
  const cl = drafts.cover_letter;
  return (
    <div style={singleCol}>
      <DownloadRow kind="cover_letter" label="cover letter" onDownload={onDownload} busy={busy} />
      <FieldGroup label="Greeting">
        <input style={inp} value={cl.greeting} onChange={(e) => onChange({ ...cl, greeting: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Body (one paragraph per line)">
        <textarea style={ta} rows={12} value={cl.body_paragraphs.join("\n")}
          onChange={(e) => onChange({ ...cl, body_paragraphs: e.target.value.split("\n").filter((x) => x !== "") })} />
      </FieldGroup>
      <FieldGroup label="Closing">
        <input style={inp} value={cl.closing} onChange={(e) => onChange({ ...cl, closing: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Signature">
        <input style={inp} value={cl.signature} onChange={(e) => onChange({ ...cl, signature: e.target.value })} />
      </FieldGroup>
      <p style={hint}>Use <b>**double asterisks**</b> to bold keywords. Your email and LinkedIn are added as clickable links.</p>
    </div>
  );
}

/* ── Email panel + copy-to-clipboard ────────────────────────────────────── */
function EmailPanel({ drafts, onChange, onDownload, busy }: {
  drafts: TailorDrafts;
  onChange: (em: TailorDrafts["email"]) => void;
  onDownload: (k: TailorKind, f: DownloadFormat) => void;
  busy: string;
}) {
  const em = drafts.email;
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${em.subject ? `Subject: ${em.subject}\n\n` : ""}${emailToPlainText(em)}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked — the textarea is still selectable */ }
  };
  return (
    <div style={singleCol}>
      <DownloadRow kind="email" label="email" onDownload={onDownload} busy={busy}
        extra={<button type="button" onClick={copy} style={ghostInline}>{copied ? "Copied ✓" : "Copy for Gmail"}</button>} />
      <FieldGroup label="Subject">
        <input style={inp} value={em.subject} onChange={(e) => onChange({ ...em, subject: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Greeting">
        <input style={inp} value={em.greeting} onChange={(e) => onChange({ ...em, greeting: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Body (one paragraph per line)">
        <textarea style={ta} rows={8} value={em.body_paragraphs.join("\n")}
          onChange={(e) => onChange({ ...em, body_paragraphs: e.target.value.split("\n").filter((x) => x !== "") })} />
      </FieldGroup>
      <FieldGroup label="Closing">
        <input style={inp} value={em.closing} onChange={(e) => onChange({ ...em, closing: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Signature">
        <input style={inp} value={em.signature} onChange={(e) => onChange({ ...em, signature: e.target.value })} />
      </FieldGroup>
      <FieldGroup label="Plain-text preview (what 'Copy for Gmail' copies)">
        <textarea style={{ ...ta, background: tk.surfaceTertiary }} rows={7} readOnly value={emailToPlainText(em)} />
      </FieldGroup>
    </div>
  );
}

/* Trim each project's bullets to the count the live preview fitted onto the page,
   and rebuild each project with only name/tech_stack/bullets so the helper
   `candidate_bullets` field never reaches the DOCX. The DOCX then matches the
   preview exactly. */
function applyFit(resume: Resume, fit: FitInfo | null): Resume {
  const counts = fit?.fittedCounts;
  return {
    ...resume,
    projects: resume.projects.map((p, i) => {
      const n = counts && typeof counts[i] === "number" ? counts[i] : p.bullets.length;
      return { name: p.name, tech_stack: p.tech_stack, bullets: p.bullets.slice(0, n) };
    }),
  };
}

/* A small chip showing the live page count + how full the last page is, so the
   user can see the resume land on a clean 1 / 1.5 / 2 / 2.5 / 3-page boundary. */
function FitChip({ fit }: { fit: FitInfo | null }) {
  if (!fit || !fit.pages) return null;
  const onBoundary = fit.lastFillPct >= 88 || (fit.lastFillPct >= 40 && fit.lastFillPct <= 62);
  const over = fit.pages > 3;
  const bg = over ? "#fdecea" : onBoundary ? tk.greenSurface : "#fbf0db";
  const fg = over ? tk.red : onBoundary ? tk.green : "#9a6a1a";
  const label = `${fit.pages} page${fit.pages > 1 ? "s" : ""} · last page ${fit.lastFillPct}% full${over ? " · over 3 pages" : ""}`;
  return (
    <span style={{ fontSize: "11.5px", fontWeight: 600, color: fg, background: bg, padding: "3px 10px", borderRadius: "999px", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

/* ── shared bits ─────────────────────────────────────────────────────────── */
function DownloadRow({ kind, label, onDownload, busy, extra }: {
  kind: TailorKind; label: string; onDownload: (k: TailorKind, f: DownloadFormat) => void; busy: string; extra?: React.ReactNode;
}) {
  return (
    <div style={dlRow}>
      <span style={{ fontSize: "13px", color: tk.onSurfaceTertiary }}>Download {label}:</span>
      <button type="button" onClick={() => onDownload(kind, "docx")} disabled={!!busy} style={dlBtn(true)}>
        {busy === `${kind}-docx` ? "…" : "DOCX"}
      </button>
      <button type="button" onClick={() => onDownload(kind, "pdf")} disabled={!!busy} style={dlBtn(false)}>
        {busy === `${kind}-pdf` ? "…" : "PDF"}
      </button>
      {extra}
    </div>
  );
}
function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "16px" }}>
      <span style={fgLabel}>{label}</span>
      {children}
    </div>
  );
}
function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} style={{
      padding: "9px clamp(12px,3vw,18px)", fontSize: "14px", fontWeight: 600, cursor: "pointer", background: "none", border: "none",
      color: active ? tk.onSurface : tk.onSurfaceTertiary, borderBottom: `2px solid ${active ? tk.clayInteractive : "transparent"}`,
      flexShrink: 0, whiteSpace: "nowrap",
    }}>{children}</button>
  );
}
function Header({ onStartOver, style }: { onStartOver: () => void; style?: CSSProperties }) {
  return (
    <header style={{ ...headerStyle, ...style }}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none", minWidth: 0 }}>
        <span style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Resume Formatter</span>
      </Link>
      <button type="button" onClick={onStartOver} style={{ marginLeft: "auto", flexShrink: 0, ...ghostInline }}>← Tailor another</button>
    </header>
  );
}

/* ── MatchCard: the floating JD-match card (gauge + "what changed" + counts).
   Refined within the app's warm palette: layered shadow, a conic score ring that
   sweeps in on mount, and a tight change-log. ─────────────────────────────── */
function MatchCard({ match, changes, floating, compact }: { match: MatchInfo; changes: string[]; floating?: boolean; compact?: boolean }) {
  const after = match?.score_after ?? 0;
  const before = match?.score_before ?? 0;
  const delta = after - before;
  const color = after >= 85 ? tk.green : after >= 70 ? "#3f9b54" : after >= 50 ? "#c9851f" : tk.red;
  const grade = after >= 90 ? "Excellent" : after >= 80 ? "Strong" : after >= 65 ? "Good" : after >= 50 ? "Fair" : "Weak";
  const skillsAdded = match?.skills?.added?.length || 0;
  const kwAdded = match?.keywords?.added?.length || 0;
  const R = 34, C = 2 * Math.PI * R;
  const [open, setOpen] = useState(false);

  // Sweep the ring from empty to `after%` on mount.
  const [drawn, setDrawn] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setDrawn(after));
    return () => cancelAnimationFrame(id);
  }, [after]);

  // ── Compact horizontal bar (inline / mobile): the score reads in one row and
  //    "what changed" collapses, so the live preview stays the hero. ──────────
  if (compact) {
    const cR = 24, cC = 2 * Math.PI * cR;
    return (
      <section style={compactCard} aria-label="JD match score">
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ position: "relative", width: "58px", height: "58px", flexShrink: 0 }}>
            <svg width="58" height="58" viewBox="0 0 58 58" aria-hidden>
              <circle cx="29" cy="29" r={cR} fill="none" stroke={tk.borderTertiary} strokeWidth="6" />
              <circle cx="29" cy="29" r={cR} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
                strokeDasharray={cC} strokeDashoffset={cC - (drawn / 100) * cC} transform="rotate(-90 29 29)"
                style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1)" }} />
            </svg>
            <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <b style={{ fontFamily: tk.serif, fontSize: "18px", fontWeight: 600, color }}>{after}<span style={{ fontSize: "10px" }}>%</span></b>
            </span>
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "10.5px", fontWeight: 700, letterSpacing: "0.08em", color: tk.onSurfaceTertiary }}>JD MATCH</span>
              <span style={{ fontSize: "10px", fontWeight: 700, color: "#fff", background: color, padding: "2px 8px", borderRadius: "999px" }}>{grade}</span>
            </div>
            <div style={{ fontSize: "14px", color: tk.onSurfaceSecondary, marginTop: "3px" }}>
              <span style={{ color: tk.onSurfaceTertiary }}>{before}%</span>
              <span style={{ color: tk.onSurfaceGhost, margin: "0 5px" }}>→</span>
              <b style={{ color }}>{after}%</b>
              {delta > 0 && <span style={{ marginLeft: "8px", fontSize: "11px", fontWeight: 700, color: tk.green, background: tk.greenSurface, padding: "2px 7px", borderRadius: "6px", whiteSpace: "nowrap" }}>▲ +{delta} pts</span>}
            </div>
            {(skillsAdded > 0 || kwAdded > 0) && (
              <div style={{ fontSize: "10.5px", color: tk.onSurfaceTertiary, marginTop: "4px" }}>
                +{skillsAdded} skills · +{kwAdded} keywords · added terms <span style={{ ...chipNeon, padding: "0 4px", fontSize: "10px" }}>highlighted</span> below
              </div>
            )}
          </div>
        </div>
        {changes?.length > 0 && (
          <>
            <button type="button" onClick={() => setOpen((o) => !o)} style={changeToggle} aria-expanded={open}>
              <span>{open ? "Hide what changed" : `What changed (${changes.length})`}</span>
              <span aria-hidden>{open ? "▴" : "▾"}</span>
            </button>
            {open && (
              <ul style={{ listStyle: "none", margin: "8px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
                {changes.slice(0, 6).map((c, i) => (
                  <li key={i} style={{ display: "flex", gap: "8px", fontSize: "12.5px", color: tk.onSurfaceSecondary, lineHeight: 1.45 }}>
                    <span style={{ color: tk.green, flexShrink: 0, fontWeight: 700 }}>✓</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    );
  }

  return (
    <section style={floating ? { ...matchCard, ...matchCardFloating } : matchCard} aria-label="JD match score">
      <div style={matchCardHeader}>
        <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.1em", color: tk.onSurfaceTertiary }}>JD MATCH</span>
        <span style={{ fontSize: "10.5px", fontWeight: 700, color: "#fff", background: color, padding: "2px 9px", borderRadius: "999px" }}>{grade}</span>
      </div>

      {/* Score ring: sweeps from 0 to `after` on mount */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", margin: "4px 0 14px" }}>
        <div style={{ position: "relative", width: "88px", height: "88px", flexShrink: 0 }}>
          <svg width="88" height="88" viewBox="0 0 88 88" aria-hidden>
            <circle cx="44" cy="44" r={R} fill="none" stroke={tk.borderTertiary} strokeWidth="8" />
            <circle cx="44" cy="44" r={R} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={C - (drawn / 100) * C} transform="rotate(-90 44 44)"
              style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1)" }} />
          </svg>
          <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <b style={{ fontFamily: tk.serif, fontSize: "26px", fontWeight: 600, color }}>{after}<span style={{ fontSize: "14px" }}>%</span></b>
          </span>
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: "14px", color: tk.onSurfaceSecondary }}>
            <span style={{ color: tk.onSurfaceTertiary }}>{before}%</span>
            <span style={{ color: tk.onSurfaceGhost, margin: "0 5px" }}>→</span>
            <b style={{ color }}>{after}%</b>
          </div>
          {delta > 0 && (
            <div style={{ display: "inline-block", marginTop: "5px", fontSize: "11.5px", fontWeight: 700, color: tk.green, background: tk.greenSurface, padding: "2px 8px", borderRadius: "6px" }}>▲ +{delta} pts</div>
          )}
          {(skillsAdded > 0 || kwAdded > 0) && (
            <div style={{ fontSize: "11px", color: tk.onSurfaceTertiary, marginTop: "6px" }}>
              +{skillsAdded} skills · +{kwAdded} keywords
            </div>
          )}
        </div>
      </div>

      {/* What changed — the jobright-style change log */}
      {changes?.length > 0 && (
        <div style={{ borderTop: `1px solid ${tk.borderTertiary}`, paddingTop: "11px" }}>
          <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.04em", color: tk.onSurface }}>WHAT CHANGED</span>
          <ul style={{ listStyle: "none", margin: "9px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: "7px" }}>
            {changes.slice(0, 5).map((c, i) => (
              <li key={i} style={{ display: "flex", gap: "8px", fontSize: "12.5px", color: tk.onSurfaceSecondary, lineHeight: 1.45 }}>
                <span style={{ color: tk.green, flexShrink: 0, fontWeight: 700 }}>✓</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p style={{ fontSize: "10.5px", color: tk.onSurfaceTertiary, margin: "11px 0 0", lineHeight: 1.5 }}>
        Added terms are <span style={{ ...chipNeon, padding: "0 4px", fontSize: "10.5px" }}>highlighted</span> in the preview.
      </p>
    </section>
  );
}

/* ── styles ──────────────────────────────────────────────────────────────── */
const shell: CSSProperties = { height: "100vh", display: "flex", flexDirection: "column", background: tk.surface, fontFamily: tk.sans, overflow: "hidden" };
const headerStyle: CSSProperties = { height: "56px", flexShrink: 0, display: "flex", alignItems: "center", padding: "0 clamp(16px,4vw,28px)", borderBottom: `1px solid ${tk.borderTertiary}`, background: "#faf9f5", zIndex: 40 };
const betaBanner: CSSProperties = { flexShrink: 0, display: "flex", alignItems: "center", gap: "10px", padding: "9px clamp(16px,4vw,28px)", background: tk.surfaceTertiary, borderBottom: `1px solid ${tk.borderTertiary}` };
const betaPill: CSSProperties = { fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", color: "#fff", background: tk.clayInteractive, padding: "3px 8px", borderRadius: "6px" };
const chipNeon: CSSProperties = { fontSize: "11px", color: "#2d3a00", background: "#caff5e", border: "1px solid #aee63a", borderRadius: "999px", padding: "2px 9px" };
const tabBar: CSSProperties = { flexShrink: 0, display: "flex", gap: "8px", padding: "10px clamp(16px,4vw,28px) 0", borderBottom: `1px solid ${tk.borderTertiary}` };
const body: CSSProperties = { flex: 1, minHeight: 0, display: "flex", flexDirection: "column" };
// 2 columns: left edit rail · full-width preview. The match card floats over the right gutter.
// The rail is kept lean so the live preview (the hero) gets as much width as possible.
const twoCol: CSSProperties = { flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "clamp(340px,33%,480px) minmax(0,1fr)" };
const editCol: CSSProperties = { minWidth: 0, overflowY: "auto", padding: "16px clamp(14px,2vw,20px) 40px", borderRight: `1px solid ${tk.borderTertiary}`, background: tk.surfaceSecondary };
const previewCol: CSSProperties = { minWidth: 0, overflowY: "auto", padding: "16px clamp(16px,2vw,28px) 40px", background: "#e9e7df", display: "flex", flexDirection: "column", position: "relative" };
const previewLabel: CSSProperties = { fontSize: "12px", color: tk.onSurfaceSecondary, fontWeight: 600, paddingTop: "4px", marginBottom: "10px" };
// Floating match card: fixed to the right gutter, vertically centered, never covers the page.
const floatWrap: CSSProperties = { position: "fixed", right: "24px", top: "calc(50% + 30px)", transform: "translateY(-50%)", zIndex: 30, pointerEvents: "none" };
// Mobile-only sticky download bar (resume tab) — pinned to the bottom of the screen.
const mobileDlBar: CSSProperties = { position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 50, display: "flex", gap: "10px", padding: "10px clamp(14px,4vw,20px)", background: "color-mix(in srgb, #faf9f5 94%, transparent)", backdropFilter: "saturate(180%) blur(10px)", WebkitBackdropFilter: "saturate(180%) blur(10px)", borderTop: `1px solid ${tk.borderSecondary}`, boxShadow: "0 -4px 18px rgba(20,20,19,0.07)" };
const matchCard: CSSProperties = { background: "#fff", border: `1px solid ${tk.borderSecondary}`, borderRadius: "16px", padding: "16px 16px 14px", boxShadow: "0 4px 16px rgba(20,20,19,0.07)" };
// Compact horizontal match bar (inline / mobile) — kept short so the preview leads.
const compactCard: CSSProperties = { background: "#fff", border: `1px solid ${tk.borderSecondary}`, borderRadius: "14px", padding: "12px 14px", boxShadow: "0 2px 10px rgba(20,20,19,0.05)" };
const changeToggle: CSSProperties = { marginTop: "10px", width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", background: tk.surfaceSecondary, border: `1px solid ${tk.borderTertiary}`, borderRadius: "8px", padding: "7px 11px", fontFamily: tk.sans, fontSize: "12.5px", fontWeight: 600, color: tk.onSurfaceSecondary, cursor: "pointer" };
const matchCardFloating: CSSProperties = { width: "300px", maxWidth: "26vw", pointerEvents: "auto", boxShadow: "0 18px 50px -12px rgba(20,20,19,0.28), 0 4px 12px rgba(20,20,19,0.08)", animation: "rf-fade 0.5s cubic-bezier(0.22,1,0.36,1) both" };
const matchCardHeader: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" };
const previewFrame: CSSProperties = { width: "100%", maxWidth: "820px", margin: "0 auto" };
const scrollPane: CSSProperties = { flex: 1, minHeight: 0, overflowY: "auto", padding: "22px clamp(16px,4vw,28px) 50px" };
const singleCol: CSSProperties = { maxWidth: "760px", margin: "0 auto" };
const cardStyle: CSSProperties = { background: "#fff", border: `1px solid ${tk.borderTertiary}`, borderRadius: "12px", padding: "13px 15px" };
const dlCard: CSSProperties = { ...cardStyle, position: "sticky", top: "-16px", zIndex: 5, background: tk.surfaceSecondary, borderColor: tk.borderSecondary };
const fgLabel: CSSProperties = { display: "block", fontSize: "12px", fontWeight: 600, color: tk.onSurfaceSecondary, marginBottom: "6px" };
const ta: CSSProperties = { width: "100%", fontFamily: tk.sans, fontSize: "13.5px", lineHeight: 1.5, padding: "10px", borderRadius: "8px", border: `1px solid ${tk.borderSecondary}`, outline: "none", background: "#fff", color: tk.onSurface, resize: "vertical", boxSizing: "border-box" };
const inp: CSSProperties = { ...ta, resize: "none" } as CSSProperties;
const hint: CSSProperties = { fontSize: "12px", color: tk.onSurfaceTertiary, lineHeight: 1.55, marginTop: "4px" };
const dlRow: CSSProperties = { display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "18px", paddingBottom: "14px", borderBottom: `1px solid ${tk.borderTertiary}` };
const ghostBtn: CSSProperties = { width: "100%", marginTop: "10px", padding: "8px", borderRadius: "9px", border: `1px solid ${tk.borderSecondary}`, background: "#fff", fontFamily: tk.sans, fontSize: "12.5px", fontWeight: 500, color: tk.onSurfaceSecondary, cursor: "pointer" };
const ghostInline: CSSProperties = { padding: "7px 14px", borderRadius: "8px", fontSize: "13px", fontWeight: 500, cursor: "pointer", border: `1px solid ${tk.borderSecondary}`, background: "#fff", color: tk.onSurfaceSecondary };
const errStyle: CSSProperties = { margin: "12px clamp(16px,4vw,28px) 0", fontSize: "13px", color: tk.red, padding: "10px 14px", background: "#fff", border: `1px solid ${tk.red}`, borderRadius: "8px" };
function dlBtn(filled: boolean): CSSProperties {
  return { padding: "10px 16px", borderRadius: "9px", fontSize: "13.5px", fontWeight: 600, cursor: "pointer", border: `1px solid ${tk.clayInteractive}`, background: filled ? tk.clayInteractive : "#fff", color: filled ? "#faf9f5" : tk.clayInteractive, transition: "all 0.15s ease" };
}
