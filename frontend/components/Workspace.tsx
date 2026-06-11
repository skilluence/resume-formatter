"use client";

import { useState, useRef, useCallback, useEffect, CSSProperties } from "react";
import Link from "next/link";
import axios from "axios";
import { tk } from "@/lib/tokens";
import {
  Resume,
  StatusMap,
  SectionStatus,
  getSections,
  reviewedCount,
  allReviewed,
  buildPayload,
  isCoursework,
} from "@/lib/resume";
import SectionCard, { SectionEditor } from "@/components/SectionCard";
import ResumePreview from "@/components/ResumePreview";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

type Stage = "idle" | "uploading" | "formatting" | "review" | "error";

const THINKING_WORDS = ["Reading", "Parsing", "Structuring", "Organizing", "Aligning", "Mapping", "Tidying", "Arranging"];

/* ════════════════════════════════════════════════════════════════════════
   Workspace — header / two-pane / footer.
   LEFT rail: upload → review (section cards + inline edit).  RIGHT: the live
   resume as a real, paginated Word document. Editing lives on the left so the
   right stays a clean document.
═══════════════════════════════════════════════════════════════════════ */
export default function Workspace() {
  const [inputMode, setInputMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [plainText, setPlainText] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<Stage>("idle");
  const [progress, setProgress] = useState(0);
  const [resume, setResume] = useState<Resume | null>(null);
  const [candidateName, setCandidateName] = useState("");
  const [error, setError] = useState("");

  const [status, setStatusMap] = useState<StatusMap>({});
  const [showGpa, setShowGpa] = useState(true);
  const [showCoursework, setShowCoursework] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);
  const [buildError, setBuildError] = useState("");
  const [narrow, setNarrow] = useState(false);
  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [dragId, setDragId] = useState<string | null>(null);

  const isLoading = stage === "uploading" || stage === "formatting";

  useEffect(() => {
    if (!isLoading) return;
    const id = setInterval(() => setProgress((p) => (p >= 90 ? p : Math.min(90, p + Math.max(0.6, (90 - p) * 0.07)))), 150);
    return () => clearInterval(id);
  }, [isLoading]);

  useEffect(() => {
    const f = () => setNarrow(window.innerWidth < 880);
    f();
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);

  const resetReview = () => {
    setStatusMap({});
    setShowGpa(true);
    setShowCoursework(false);
    setEditing(null);
    setBuildError("");
    setSectionOrder([]);
    setDragId(null);
  };
  const startOver = () => {
    setFile(null);
    setPlainText("");
    setInputMode("file");
    setDragging(false);
    setStage("idle");
    setProgress(0);
    setResume(null);
    setCandidateName("");
    setError("");
    resetReview();
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFormat = async () => {
    if (!file && !plainText.trim()) return;
    setStage("uploading");
    setError("");
    setResume(null);
    setProgress(0);
    resetReview();
    const fd = new FormData();
    if (file) fd.append("file", file);
    else fd.append("plain_text", plainText);
    try {
      setStage("formatting");
      const res = await axios.post(`${API_URL}/format`, fd);
      const parsed = res.data?.resume;
      if (!parsed || !parsed.name) throw new Error("The formatter returned an unexpected response.");
      setResume(parsed);
      // Coursework toggle defaults ON when the uploaded resume actually has it.
      setShowCoursework((parsed.education || []).some((e: { details?: string[] }) => (e.details || []).some(isCoursework)));
      setCandidateName(res.data.candidate_name || "Your");
      setProgress(100);
      setTimeout(() => setStage("review"), 350);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? err.response?.data?.detail || `Couldn't reach the formatter at ${API_URL || "the API"}.`
        : err instanceof Error
        ? err.message
        : "Something went wrong.";
      setError(msg);
      setStage("error");
    }
  };

  const sections = resume ? getSections(resume) : [];
  const done = reviewedCount(sections, status);
  const total = sections.length;
  const canDownload = resume != null && allReviewed(sections, status) && !building;
  const pct = total ? Math.round((done / total) * 100) : 0;

  // Reorderable body = every section after the summary. Reconcile the user's
  // chosen order with the sections actually present (skipped ones stay; new ones
  // append) so the order is always valid.
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
      if (next && id !== "header" && status[id] !== "skipped") setStatus(id, "kept");
      return next;
    });
  const skip = (id: string) => {
    setStatus(id, "skipped");
    setEditing((cur) => (cur === id ? null : cur));
  };
  const approveAll = () =>
    setStatusMap((m) => {
      const n = { ...m };
      for (const s of sections) if (n[s.id] !== "skipped") n[s.id] = "kept";
      return n;
    });

  const safeName = (resume?.name || "resume").trim().replace(/\s+/g, "_") || "resume";

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

  // Local safety net: never lose the user's edits even if the server is down.
  const exportFallback = () => {
    if (!resume) return;
    const payload = buildPayload(resume, status, showGpa, orderedBodyIds, showCoursework);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    triggerBlobDownload(blob, `${safeName}_edits.json`);
  };

  const download = async (format: "docx" | "pdf") => {
    if (!resume) return;
    if (!API_URL) {
      setBuildError("This app isn't configured with a backend URL (NEXT_PUBLIC_API_URL). Set it and redeploy.");
      return;
    }
    setBuilding(true);
    setBuildError("");
    const endpoint = format === "pdf" ? "/build/pdf" : "/build";
    const filename = `${safeName}.${format}`;
    const body = JSON.stringify({ resume: buildPayload(resume, status, showGpa, orderedBodyIds, showCoursework) });

    let lastErr = "";
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        if (attempt > 0) {
          // Warm a possibly-cold server (Render free tier sleeps), then back off.
          await fetch(`${API_URL}/`, { method: "GET" }).catch(() => {});
          await new Promise((r) => setTimeout(r, 800 * attempt));
        }
        const res = await fetch(`${API_URL}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
        });
        if (!res.ok) {
          // The server answered — a real error, not connectivity. Show it, stop.
          const detail = (await res.json().catch(() => null))?.detail;
          throw new Error(detail || `Build failed (HTTP ${res.status}).`);
        }
        triggerBlobDownload(await res.blob(), filename);
        setBuilding(false);
        return;
      } catch (e) {
        lastErr = e instanceof Error ? e.message : String(e);
        const isNetwork = e instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(lastErr);
        if (!isNetwork) break; // a real server error — don't keep retrying
      }
    }
    setBuilding(false);
    const networkish = /failed to fetch|networkerror|load failed/i.test(lastErr);
    setBuildError(
      networkish
        ? "Couldn't reach the server — it may be waking up. Save your work with “Download my edits”, then try again in a moment."
        : lastErr || "Couldn't build your resume."
    );
  };

  const inReview = stage === "review" && resume != null;

  return (
    <div style={{ height: narrow ? "auto" : "100vh", minHeight: "100vh", display: "flex", flexDirection: "column", overflow: narrow ? "visible" : "hidden", background: tk.surface, fontFamily: tk.sans }}>
      <Header />
      <div style={{ flex: 1, display: "flex", flexDirection: narrow ? "column" : "row", alignItems: "stretch", minHeight: 0 }}>
        {/* LEFT rail */}
        <aside style={narrow ? railStyleNarrow : railStyle}>
          {inReview && resume ? (
            <ReviewRail
              name={candidateName}
              resume={resume}
              summaryMeta={summaryMeta}
              bodyIds={orderedBodyIds}
              labelOf={labelOf}
              status={status}
              showGpa={showGpa}
              showCoursework={showCoursework}
              editing={editing}
              done={done}
              total={total}
              pct={pct}
              canDownload={canDownload}
              building={building}
              buildError={buildError}
              dragId={dragId}
              onChange={setResume}
              onKeep={(id) => setStatus(id, "kept")}
              onSkip={skip}
              onToggleEdit={toggleEdit}
              onToggleGpa={() => setShowGpa((v) => !v)}
              onToggleCoursework={() => setShowCoursework((v) => !v)}
              onApproveAll={approveAll}
              onDownload={download}
              onStartOver={startOver}
              onExportFallback={exportFallback}
              onDragStartSection={(id) => setDragId(id)}
              onDropSection={(id) => { if (dragId) reorderSection(dragId, id); setDragId(null); }}
              onDragEndSection={() => setDragId(null)}
            />
          ) : (
            <UploadCard
              inputMode={inputMode}
              setInputMode={setInputMode}
              file={file}
              setFile={setFile}
              plainText={plainText}
              setPlainText={setPlainText}
              dragging={dragging}
              setDragging={setDragging}
              fileInputRef={fileInputRef}
              isLoading={isLoading}
              progress={progress}
              error={stage === "error" ? error : ""}
              onClearError={() => stage === "error" && setStage("idle")}
              onFormat={handleFormat}
            />
          )}
        </aside>

        {/* RIGHT canvas */}
        <main style={canvasStyle}>
          {inReview && resume ? (
            <ResumePreview resume={resume} status={status} showGpa={showGpa} sectionOrder={orderedBodyIds} showCoursework={showCoursework} />
          ) : isLoading ? (
            <SkeletonPage progress={progress} />
          ) : (
            <EmptyHint />
          )}
        </main>
      </div>
      <Footer />
    </div>
  );
}

/* ════════════════════════════ Header / Footer ═══════════════════════ */
function Header() {
  return (
    <header style={headerStyle}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
        <Asterisk />
        <span style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface, letterSpacing: "-0.01em" }}>Resume Formatter</span>
      </Link>
      <Link href="/tailor" style={{ marginLeft: "auto", fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceTertiary, textDecoration: "none" }}>
        Tailor to a job <sup style={{ fontSize: "9px", color: tk.clay, fontWeight: 700 }}>BETA</sup>
      </Link>
    </header>
  );
}
function Footer() {
  return (
    <footer style={{ borderTop: `1px solid ${tk.borderTertiary}`, background: tk.surfaceSecondary, padding: "16px clamp(16px,4vw,40px)", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px" }}>
        <span style={{ fontFamily: tk.serif, fontSize: "13.5px", color: tk.onSurfaceSecondary }}>Resume Formatter</span>
        <span style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceTertiary }}>The cleanest way to format a resume — every word preserved.</span>
      </div>
    </footer>
  );
}

/* ════════════════════════════ Review rail (left) ════════════════════ */
interface RailProps {
  name: string;
  resume: Resume;
  summaryMeta: { id: string; label: string } | null;
  bodyIds: string[];
  labelOf: (id: string) => string;
  status: StatusMap;
  showGpa: boolean;
  showCoursework: boolean;
  editing: string | null;
  done: number;
  total: number;
  pct: number;
  canDownload: boolean;
  building: boolean;
  buildError: string;
  dragId: string | null;
  onChange: (r: Resume) => void;
  onKeep: (id: string) => void;
  onSkip: (id: string) => void;
  onToggleEdit: (id: string) => void;
  onToggleGpa: () => void;
  onToggleCoursework: () => void;
  onApproveAll: () => void;
  onDownload: (f: "docx" | "pdf") => void;
  onStartOver: () => void;
  onExportFallback: () => void;
  onDragStartSection: (id: string) => void;
  onDropSection: (id: string) => void;
  onDragEndSection: () => void;
}
function ReviewRail(p: RailProps) {
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
      <div>
        <h1 style={{ fontFamily: tk.serif, fontSize: "20px", fontWeight: 500, color: tk.onSurface, margin: "0 0 2px", lineHeight: 1.2 }}>{p.name}&rsquo;s resume</h1>
        <p style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceTertiary, margin: 0 }}>Keep, skip or edit each section. The preview on the right updates live.</p>
      </div>

      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontFamily: tk.sans, fontSize: "12.5px", fontWeight: 500, color: tk.onSurfaceSecondary }}>Progress</span>
          <span style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceTertiary }}>{p.done} of {p.total}</span>
        </div>
        <div role="progressbar" aria-valuenow={p.pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${p.done} of ${p.total} sections reviewed`} style={{ height: "7px", background: tk.surfaceTertiary, borderRadius: "999px", marginTop: "8px", overflow: "hidden" }}>
          <span style={{ display: "block", height: "100%", width: `${p.pct}%`, background: p.canDownload ? tk.green : `linear-gradient(90deg, ${tk.clay}, ${tk.clayInteractive})`, transition: "width 0.3s ease, background 0.3s ease" }} />
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

      {/* Summary is pinned at the top; everything below is drag-to-reorder. */}
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

      <div style={{ ...cardStyle, background: tk.surfaceTertiary }}>
        {p.done < p.total && (
          <button type="button" onClick={p.onApproveAll} style={{ ...ghostBtn, marginTop: 0, marginBottom: "9px", borderColor: tk.clayInteractive, color: tk.clayInteractive, fontWeight: 600 }}>
            ✓ Approve all remaining ({p.total - p.done})
          </button>
        )}
        {!p.canDownload && <p style={{ fontFamily: tk.sans, fontSize: "11.5px", color: tk.onSurfaceTertiary, margin: "0 0 9px", textAlign: "center" }}>{p.building ? "Building…" : `Review all ${p.total} sections to unlock`}</p>}
        <div style={{ display: "flex", gap: "8px" }}>
          <button type="button" disabled={!p.canDownload} onClick={() => p.onDownload("docx")} style={{ ...dlBtn(p.canDownload, true), flex: 1 }}>↓ Download DOCX</button>
          <button type="button" disabled={!p.canDownload} onClick={() => p.onDownload("pdf")} style={{ ...dlBtn(p.canDownload, false), flex: 1 }}>↓ Download PDF</button>
        </div>
        {p.buildError && (
          <>
            <p role="alert" style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.red, margin: "9px 0 0", textAlign: "center" }}>{p.buildError}</p>
            <button type="button" onClick={p.onExportFallback} style={{ ...ghostBtn }}>↓ Download my edits (.json)</button>
          </>
        )}
        <button type="button" onClick={p.onStartOver} style={{ ...ghostBtn, border: "none", color: tk.onSurfaceTertiary }}>Format another resume</button>
      </div>
    </div>
  );
}

/* ════════════════════════════ Upload card (left) ════════════════════ */
interface UploadProps {
  inputMode: "file" | "text";
  setInputMode: (m: "file" | "text") => void;
  file: File | null;
  setFile: (f: File | null) => void;
  plainText: string;
  setPlainText: (t: string) => void;
  dragging: boolean;
  setDragging: (b: boolean) => void;
  fileInputRef: React.RefObject<HTMLInputElement>;
  isLoading: boolean;
  progress: number;
  error: string;
  onClearError: () => void;
  onFormat: () => void;
}
function UploadCard(p: UploadProps) {
  const canSubmit = !p.isLoading && (!!p.file || !!p.plainText.trim());
  const openPicker = () => p.fileInputRef.current?.click();
  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      p.setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) {
        p.setFile(f);
        p.onClearError();
      }
    },
    [p]
  );
  return (
    <div>
      <h1 style={{ fontFamily: tk.serif, fontSize: "23px", fontWeight: 500, color: tk.onSurface, margin: "2px 0 4px", lineHeight: 1.15 }}>Format your resume</h1>
      <p style={{ fontFamily: tk.sans, fontSize: "13px", color: tk.onSurfaceTertiary, margin: "0 0 16px", lineHeight: 1.55 }}>
        Upload a PDF or Word file. Review every section as a live document, then download. Nothing is added or lost.
      </p>

      <div style={{ display: "flex", gap: "7px", marginBottom: "14px" }}>
        {(["file", "text"] as const).map((m) => {
          const active = p.inputMode === m;
          return (
            <button key={m} type="button" onClick={() => p.setInputMode(m)} style={{ fontFamily: tk.sans, fontSize: "13px", padding: "6px 13px", borderRadius: "8px", cursor: "pointer", fontWeight: active ? 500 : 400, border: `1px solid ${active ? tk.clayInteractive : tk.borderTertiary}`, background: active ? "color-mix(in srgb, #c96442 12%, white)" : "#fff", color: active ? tk.clayInteractive : tk.onSurfaceTertiary }}>
              {m === "file" ? "Upload file" : "Paste text"}
            </button>
          );
        })}
      </div>

      {p.inputMode === "file" ? (
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload your resume. Drop a PDF or DOCX here, or activate to browse."
          onDragOver={(e) => {
            e.preventDefault();
            p.setDragging(true);
          }}
          onDragLeave={() => p.setDragging(false)}
          onDrop={onDrop}
          onClick={openPicker}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openPicker();
            }
          }}
          style={{ border: `2px dashed ${p.dragging ? tk.clay : p.file ? tk.green : tk.borderSecondary}`, borderRadius: "12px", padding: "30px 18px", textAlign: "center", cursor: "pointer", transition: "all 0.2s ease", background: p.dragging ? tk.surfaceTertiary : p.file ? tk.greenSurface : "#fff" }}
        >
          <input ref={p.fileInputRef} type="file" accept=".pdf,.docx,.doc" style={{ display: "none" }} onChange={(e) => { const f = e.target.files?.[0]; if (f) { p.setFile(f); p.onClearError(); } }} />
          {p.file ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "7px" }}>
              <FileGlyph color={tk.green} />
              <span style={{ fontFamily: tk.sans, fontSize: "13.5px", fontWeight: 500, color: tk.greenInteractive, wordBreak: "break-all" }}>{p.file.name}</span>
              <button type="button" onClick={(e) => { e.stopPropagation(); p.setFile(null); p.onClearError(); if (p.fileInputRef.current) p.fileInputRef.current.value = ""; }} style={{ background: "none", border: "none", color: tk.onSurfaceTertiary, fontSize: "12.5px", cursor: "pointer", fontFamily: tk.sans }}>
                × Remove file
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "9px" }}>
              <UploadGlyph color={tk.onSurfaceTertiary} />
              <span style={{ fontFamily: tk.sans, fontSize: "13.5px", color: tk.onSurfaceSecondary }}>Drop your resume or <span style={{ color: tk.clayInteractive, fontWeight: 500 }}>browse</span></span>
              <span style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceTertiary }}>PDF or DOCX</span>
            </div>
          )}
        </div>
      ) : (
        <textarea rows={10} placeholder="Paste your resume text here…" value={p.plainText} onChange={(e) => { p.setPlainText(e.target.value); p.onClearError(); }} style={{ width: "100%", fontFamily: tk.sans, fontSize: "14px", lineHeight: 1.55, padding: "13px 14px", borderRadius: "12px", border: `1px solid ${tk.borderSecondary}`, resize: "vertical", outline: "none", background: "#fff", color: tk.onSurface }} />
      )}

      {p.isLoading && <Loader progress={p.progress} />}

      {!p.isLoading && (
        <button type="button" onClick={p.onFormat} disabled={!canSubmit} style={{ width: "100%", marginTop: "14px", padding: "13px", borderRadius: "11px", fontFamily: tk.sans, fontSize: "15px", fontWeight: 600, cursor: canSubmit ? "pointer" : "not-allowed", border: `1px solid ${canSubmit ? tk.clayInteractive : tk.borderTertiary}`, background: canSubmit ? tk.clayInteractive : tk.surfaceTertiary, color: canSubmit ? "#faf9f5" : tk.onSurfaceTertiary, boxShadow: canSubmit ? "0 2px 12px color-mix(in srgb, #c96442 28%, transparent)" : "none", transition: "all 0.15s ease" }}>
          Format resume →
        </button>
      )}

      {p.error && <p role="alert" style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.red, margin: "12px 0 0", textAlign: "center" }}>{p.error}</p>}
    </div>
  );
}

/* ════════════════════════════ right-canvas states ═══════════════════ */
function EmptyHint() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", minHeight: "440px", textAlign: "center", color: tk.onSurfaceTertiary }}>
      <DocGlyph />
      <p style={{ fontFamily: tk.serif, fontSize: "18px", margin: "16px 0 6px" }}>Your formatted resume appears here</p>
      <p style={{ fontFamily: tk.sans, fontSize: "13px", color: tk.onSurfaceGhost, maxWidth: "320px", margin: 0 }}>Upload a file on the left and hit Format. It&rsquo;ll render as a real Word-style page you can review and edit.</p>
    </div>
  );
}
function SkeletonPage({ progress }: { progress: number }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % THINKING_WORDS.length), 1600);
    return () => clearInterval(id);
  }, []);
  const bar = (w: string, mt = "9px"): CSSProperties => ({ height: "9px", width: w, marginTop: mt, borderRadius: "4px", background: `linear-gradient(90deg, ${tk.surfaceTertiary} 25%, ${tk.surfaceSecondary} 37%, ${tk.surfaceTertiary} 63%)`, backgroundSize: "400% 100%", animation: "rf-shimmer 1.4s ease infinite" });
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div role="status" aria-live="polite" style={{ display: "flex", alignItems: "center", gap: "9px", margin: "0 0 18px" }}>
        <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: tk.clay, animation: "rf-pulse 1.1s ease infinite" }} />
        <span key={i} style={{ fontFamily: tk.sans, fontSize: "15px", fontWeight: 500, color: tk.clayInteractive }}>{THINKING_WORDS[i]}…</span>
        <span style={{ fontFamily: tk.sans, fontSize: "13px", color: tk.onSurfaceTertiary }}>{Math.round(progress)}%</span>
      </div>
      <div style={{ width: "794px", maxWidth: "100%", height: "1000px", background: "#fff", borderRadius: "2px", boxShadow: "rgba(20,20,19,0.13) 0px 6px 30px", padding: "40px" }}>
        <div style={{ ...bar("40%", "0"), height: "16px", margin: "0 auto 12px" }} />
        <div style={{ ...bar("58%"), margin: "0 auto 20px" }} />
        {["26%", "96%", "90%", "93%", "70%", "24%", "92%", "88%", "94%", "85%"].map((w, k) => (
          <div key={k} style={bar(w, k === 5 ? "22px" : "9px")} />
        ))}
      </div>
    </div>
  );
}
function Loader({ progress }: { progress: number }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % THINKING_WORDS.length), 1600);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ marginTop: "14px", border: `1px solid ${tk.borderTertiary}`, borderRadius: "12px", background: "#fff", padding: "16px" }}>
      <div role="status" aria-live="polite" style={{ display: "flex", alignItems: "center", gap: "9px", justifyContent: "center" }}>
        <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: tk.clay, animation: "rf-pulse 1.1s ease infinite" }} />
        <span key={i} style={{ fontFamily: tk.sans, fontSize: "15px", fontWeight: 500, color: tk.clayInteractive }}>{THINKING_WORDS[i]}…</span>
      </div>
      <div style={{ height: "7px", background: tk.surfaceTertiary, borderRadius: "999px", marginTop: "12px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${progress}%`, borderRadius: "999px", background: `linear-gradient(90deg, ${tk.clay}, ${tk.clayInteractive})`, transition: "width 0.3s ease" }} />
      </div>
    </div>
  );
}

/* ════════════════════════════ glyphs / styles ═══════════════════════ */
function Asterisk({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={tk.clay} strokeWidth="2" strokeLinecap="round" aria-hidden>
      <line x1="12" y1="2" x2="12" y2="22" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /><line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}
function FileGlyph({ color }: { color: string }) {
  return <svg width={30} height={30} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>;
}
function UploadGlyph({ color }: { color: string }) {
  return <svg width={32} height={32} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.25} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>;
}
function DocGlyph() {
  return <svg width={52} height={52} viewBox="0 0 24 24" fill="none" stroke={tk.onSurfaceGhost} strokeWidth={1} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="14" y2="17" /></svg>;
}

const headerStyle: CSSProperties = {
  height: "60px",
  display: "flex",
  alignItems: "center",
  padding: "0 clamp(16px,4vw,28px)",
  borderBottom: `1px solid ${tk.borderTertiary}`,
  background: "#faf9f5",
  position: "sticky",
  top: 0,
  zIndex: 40,
  flexShrink: 0,
};
const railStyle: CSSProperties = {
  width: "clamp(360px, 40%, 600px)",
  flexShrink: 0,
  borderRight: `1px solid ${tk.borderTertiary}`,
  background: tk.surfaceSecondary,
  padding: "20px 18px 40px",
  overflowY: "auto",
};
const railStyleNarrow: CSSProperties = {
  width: "100%",
  borderBottom: `1px solid ${tk.borderTertiary}`,
  background: tk.surfaceSecondary,
  padding: "18px 16px 28px",
};
const canvasStyle: CSSProperties = {
  flex: 1,
  overflow: "auto",
  padding: "32px 28px 60px",
  background: "radial-gradient(1000px 520px at 70% -10%, #fff 0%, transparent 60%), " + tk.surface,
};
const cardStyle: CSSProperties = { background: "#fff", border: `1px solid ${tk.borderTertiary}`, borderRadius: "12px", padding: "13px 15px" };
const ghostBtn: CSSProperties = { width: "100%", marginTop: "10px", padding: "8px", borderRadius: "9px", border: `1px solid ${tk.borderSecondary}`, background: "#fff", fontFamily: tk.sans, fontSize: "12.5px", fontWeight: 500, color: tk.onSurfaceSecondary, cursor: "pointer" };
function dlBtn(enabled: boolean, filled: boolean): CSSProperties {
  return { padding: "11px", borderRadius: "10px", fontFamily: tk.sans, fontSize: "14px", fontWeight: 600, cursor: enabled ? "pointer" : "not-allowed", border: `1px solid ${enabled ? tk.clayInteractive : tk.borderTertiary}`, background: !enabled ? tk.surfaceSecondary : filled ? tk.clayInteractive : "#fff", color: !enabled ? tk.onSurfaceTertiary : filled ? "#faf9f5" : tk.clayInteractive, transition: "all 0.15s ease" };
}
