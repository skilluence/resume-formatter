"use client";

import { useMemo, useState, CSSProperties } from "react";
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
import ResumePreview from "./ResumePreview";
import {
  type TailorDrafts,
  type TailorKind,
  type DownloadFormat,
  downloadTailorOutput,
  emailToPlainText,
  hasPlaceholder,
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

  const setResume = (r: Resume) => setDrafts((d) => ({ ...d, tailored_resume: r }));

  const baseName = (resume.name || "Application").replace(/[^A-Za-z0-9._-]+/g, "_") || "Application";

  const placeholders = useMemo(() => countPlaceholders(drafts), [drafts]);

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
      // /format does before building.
      const payload: TailorDrafts =
        kind === "resume"
          ? { ...drafts, tailored_resume: buildPayload(resume, status, showGpa, orderedBodyIds, showCoursework) }
          : drafts;
      await downloadTailorOutput(apiUrl, kind, format, payload, baseName);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Download failed.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div style={shell}>
      <Header onStartOver={onStartOver} />
      <div style={betaBanner}>
        <span style={betaPill}>BETA</span>
        <span style={{ fontSize: "13px", color: tk.onSurfaceSecondary }}>
          Everything below is editable. {placeholders > 0
            ? <><b style={{ color: tk.clayInteractive }}>{placeholders} placeholder{placeholders === 1 ? "" : "s"}</b> still need real numbers before you send.</>
            : "No placeholders left - review the wording, then download."}
        </span>
      </div>

      <div style={tabBar}>
        <TabBtn active={tab === "resume"} onClick={() => setTab("resume")}>Resume</TabBtn>
        <TabBtn active={tab === "cover_letter"} onClick={() => setTab("cover_letter")}>Cover letter</TabBtn>
        <TabBtn active={tab === "email"} onClick={() => setTab("email")}>HR email</TabBtn>
      </div>

      {err && <p style={errStyle}>{err}</p>}

      <div style={body}>
        {tab === "resume" && (
          <div style={twoCol}>
            {/* LEFT: the same section-card review rail as /format */}
            <aside style={editCol}>
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
            {/* RIGHT: large live preview */}
            <div style={previewCol}>
              <span style={previewLabel}>Live preview — your one-page DOCX</span>
              <div style={previewFrame}>
                <ResumePreview resume={resume} status={status} showGpa={showGpa} sectionOrder={orderedBodyIds} showCoursework={showCoursework} />
              </div>
            </div>
          </div>
        )}

        {tab === "cover_letter" && (
          <div style={scrollPane}>
            <LetterPanel drafts={drafts} onChange={(cl) => setDrafts((d) => ({ ...d, cover_letter: cl }))} onDownload={download} busy={busy} />
          </div>
        )}
        {tab === "email" && (
          <div style={scrollPane}>
            <EmailPanel drafts={drafts} onChange={(em) => setDrafts((d) => ({ ...d, email: em }))} onDownload={download} busy={busy} />
          </div>
        )}
      </div>
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
      {/* Download bar pinned to the top of the rail */}
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
      padding: "9px 18px", fontSize: "14px", fontWeight: 600, cursor: "pointer", background: "none", border: "none",
      color: active ? tk.onSurface : tk.onSurfaceTertiary, borderBottom: `2px solid ${active ? tk.clayInteractive : "transparent"}`,
    }}>{children}</button>
  );
}
function Header({ onStartOver }: { onStartOver: () => void }) {
  return (
    <header style={headerStyle}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
        <span style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface }}>Resume Formatter</span>
      </Link>
      <button type="button" onClick={onStartOver} style={{ marginLeft: "auto", ...ghostInline }}>← Tailor another</button>
    </header>
  );
}

/* ── helpers ─────────────────────────────────────────────────────────────── */
function countPlaceholders(d: TailorDrafts): number {
  const texts: string[] = [];
  const r = d.tailored_resume;
  if (r.summary) texts.push(r.summary);
  r.experience.forEach((j) => texts.push(...j.bullets));
  r.projects.forEach((pr) => texts.push(...pr.bullets));
  d.cover_letter.body_paragraphs.forEach((pp) => texts.push(pp));
  d.email.body_paragraphs.forEach((pp) => texts.push(pp));
  return texts.filter(hasPlaceholder).reduce((n, t) => n + (t.match(/\[[^\]]+\]/g)?.length || 0), 0);
}

/* ── styles ──────────────────────────────────────────────────────────────── */
const shell: CSSProperties = { height: "100vh", display: "flex", flexDirection: "column", background: tk.surface, fontFamily: tk.sans, overflow: "hidden" };
const headerStyle: CSSProperties = { height: "56px", flexShrink: 0, display: "flex", alignItems: "center", padding: "0 clamp(16px,4vw,28px)", borderBottom: `1px solid ${tk.borderTertiary}`, background: "#faf9f5", zIndex: 40 };
const betaBanner: CSSProperties = { flexShrink: 0, display: "flex", alignItems: "center", gap: "10px", padding: "9px clamp(16px,4vw,28px)", background: tk.surfaceTertiary, borderBottom: `1px solid ${tk.borderTertiary}` };
const betaPill: CSSProperties = { fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", color: "#fff", background: tk.clayInteractive, padding: "3px 8px", borderRadius: "6px" };
const tabBar: CSSProperties = { flexShrink: 0, display: "flex", gap: "8px", padding: "10px clamp(16px,4vw,28px) 0", borderBottom: `1px solid ${tk.borderTertiary}` };
const body: CSSProperties = { flex: 1, minHeight: 0, display: "flex", flexDirection: "column" };
const twoCol: CSSProperties = { flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "clamp(420px, 40%, 600px) 1fr" };
const editCol: CSSProperties = { minWidth: 0, overflowY: "auto", padding: "16px clamp(14px,2vw,20px) 40px", borderRight: `1px solid ${tk.borderTertiary}`, background: tk.surfaceSecondary };
const previewCol: CSSProperties = { minWidth: 0, overflowY: "auto", padding: "16px clamp(16px,2vw,28px) 40px", background: "#e9e7df", display: "flex", flexDirection: "column" };
const previewLabel: CSSProperties = { display: "block", fontSize: "12px", color: tk.onSurfaceSecondary, fontWeight: 600, marginBottom: "10px", flexShrink: 0 };
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
