"use client";

import { useState, CSSProperties, ReactNode, useMemo } from "react";
import Link from "next/link";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

/* ─── Design tokens ─── */
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
  danger: "#c0524a",
  dangerSoft: "color-mix(in srgb, #c0524a 12%, transparent)",
  serif: "var(--font-lora, Georgia, serif)",
  sans: "var(--font-inter, Inter, system-ui, sans-serif)",
} as const;

/* ─── Validators ─── */
const V = {
  required: (v: string): string | null => (v.trim() ? null : "Required"),
  email: (v: string): string | null => {
    if (!v) return null;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? null : "Enter a valid email address";
  },
  phone: (v: string): string | null => {
    if (!v) return null;
    return /^[+\d][\d\s\-().]{5,}$/.test(v.trim()) ? null : "Digits, +, -, spaces only";
  },
  linkedin: (v: string): string | null => {
    if (!v) return null;
    const t = v.trim();
    const handle = /^[a-zA-Z0-9._-]{2,}$/;
    const url = /^https?:\/\/([\w-]+\.)?linkedin\.com\/.+/i;
    return handle.test(t) || url.test(t) ? null : "Handle (e.g. jane-doe) or full LinkedIn URL";
  },
  github: (v: string): string | null => {
    if (!v) return null;
    const t = v.trim();
    const handle = /^[a-zA-Z0-9-]{1,39}$/;
    const url = /^https?:\/\/(www\.)?github\.com\/.+/i;
    return handle.test(t) || url.test(t) ? null : "Handle (e.g. octocat) or full GitHub URL";
  },
};

/* ─── Types ─── */
type EduRow = { degree: string; institution: string; city: string; graduation_date: string };
type ExpRow = { title: string; company: string; city: string; start_date: string; end_date: string; bullets_raw: string };
type ProjRow = { name: string; tech_stack: string; bullets_raw: string };
type CertRow = { name: string; issuer: string; date: string };

interface JobLead {
  company: string;
  city: string;
  country: string;
  why: string;
}

interface BuildResult {
  job_id: string;
  candidate_name: string;
  job_leads: JobLead[];
}

/* ─── Icons ─── */
function AsteriskMark({ size = 18, color = tk.clay }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      <line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}
function IconPlus({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function IconX({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
function IconDownload({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
function IconCheck({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function IconAlert({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

/* ─── Styles ─── */
const inputBase: CSSProperties = {
  fontFamily: tk.sans,
  fontSize: "14px",
  color: tk.onSurface,
  backgroundColor: "#ffffff",
  border: `1px solid ${tk.borderTertiary}`,
  borderRadius: "8px",
  padding: "10px 12px",
  outline: "none",
  width: "100%",
  transition: "border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease",
};

const labelStyle: CSSProperties = {
  fontFamily: tk.sans,
  fontSize: "12px",
  fontWeight: 500,
  color: tk.onSurfaceTertiary,
  marginBottom: "5px",
  display: "block",
  letterSpacing: "0.005em",
};

const hintStyle: CSSProperties = {
  fontFamily: tk.sans,
  fontSize: "11.5px",
  color: tk.onSurfaceGhost,
  margin: "5px 0 0",
  lineHeight: 1.45,
};

const errorTextStyle: CSSProperties = {
  fontFamily: tk.sans,
  fontSize: "11.5px",
  fontWeight: 500,
  color: tk.danger,
  margin: "5px 0 0",
  display: "flex",
  alignItems: "center",
  gap: "5px",
  lineHeight: 1.45,
};

/* ─── Field wrapper ─── */
function Field({
  label, hint, required, error, children,
}: {
  label: string; hint?: string; required?: boolean; error?: string; children: ReactNode;
}) {
  return (
    <div>
      <label style={labelStyle}>
        {label}
        {required && <span style={{ color: tk.clay, marginLeft: "3px" }} aria-label="required">*</span>}
      </label>
      {children}
      {error ? (
        <p style={errorTextStyle}>
          <IconAlert size={12} />
          {error}
        </p>
      ) : hint ? (
        <p style={hintStyle}>{hint}</p>
      ) : null}
    </div>
  );
}

/* ─── Inputs ─── */
type InputExtras = { invalid?: boolean };

function TextInput({ invalid, ...props }: InputExtras & React.InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false);
  const borderColor = invalid ? tk.danger : focused ? tk.clayInteractive : tk.borderTertiary;
  const ringColor = invalid ? tk.dangerSoft : `color-mix(in srgb, ${tk.clayInteractive} 12%, transparent)`;
  return (
    <input
      {...props}
      onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
      style={{
        ...inputBase,
        borderColor,
        boxShadow: focused ? `0 0 0 3px ${ringColor}` : "none",
      }}
    />
  );
}

function TextArea({ invalid, ...props }: InputExtras & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const [focused, setFocused] = useState(false);
  const borderColor = invalid ? tk.danger : focused ? tk.clayInteractive : tk.borderTertiary;
  const ringColor = invalid ? tk.dangerSoft : `color-mix(in srgb, ${tk.clayInteractive} 12%, transparent)`;
  return (
    <textarea
      {...props}
      onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
      style={{
        ...inputBase,
        resize: "vertical",
        minHeight: "84px",
        lineHeight: 1.55,
        borderColor,
        boxShadow: focused ? `0 0 0 3px ${ringColor}` : "none",
      }}
    />
  );
}

/* ─── Section card (premium, shadowless, hairline border) ─── */
function SectionCard({
  index, title, subtitle, children,
}: {
  index?: number; title: string; subtitle?: string; children: ReactNode;
}) {
  return (
    <section
      style={{
        backgroundColor: "#ffffff",
        border: `1px solid ${tk.borderTertiary}`,
        borderRadius: "14px",
        padding: "22px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <header style={{ display: "flex", alignItems: "baseline", gap: "10px" }}>
        {typeof index === "number" && (
          <span
            style={{
              fontFamily: tk.sans,
              fontSize: "11px",
              fontWeight: 500,
              letterSpacing: "0.08em",
              color: tk.clay,
              textTransform: "uppercase",
              minWidth: "22px",
            }}
          >
            {String(index).padStart(2, "0")}
          </span>
        )}
        <div style={{ flex: 1 }}>
          <h2 style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface, margin: 0, lineHeight: 1.3, letterSpacing: "-0.005em" }}>
            {title}
          </h2>
          {subtitle && (
            <p style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceGhost, margin: "3px 0 0", lineHeight: 1.55 }}>
              {subtitle}
            </p>
          )}
        </div>
      </header>
      {children}
    </section>
  );
}

/* ─── Repeatable row (lighter, no nested-card feel) ─── */
function Row({ onRemove, children }: { onRemove: () => void; children: ReactNode }) {
  return (
    <div
      style={{
        position: "relative",
        backgroundColor: tk.surfaceSecondary,
        borderRadius: "10px",
        padding: "14px 14px 14px 14px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove"
        style={{
          position: "absolute",
          top: "8px",
          right: "8px",
          width: "24px",
          height: "24px",
          borderRadius: "6px",
          border: "none",
          backgroundColor: "transparent",
          color: tk.onSurfaceGhost,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background-color 0.15s ease, color 0.15s ease",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#ffffff"; e.currentTarget.style.color = tk.danger; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; e.currentTarget.style.color = tk.onSurfaceGhost; }}
      >
        <IconX size={12} />
      </button>
      {children}
    </div>
  );
}

function EmptyHint({ children }: { children: ReactNode }) {
  return (
    <p style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceGhost, margin: "0 0 4px", fontStyle: "italic" }}>
      {children}
    </p>
  );
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        alignSelf: "flex-start",
        fontFamily: tk.sans,
        fontSize: "13px",
        fontWeight: 500,
        backgroundColor: "transparent",
        color: tk.clayInteractive,
        border: `1px dashed color-mix(in srgb, ${tk.clayInteractive} 60%, transparent)`,
        borderRadius: "8px",
        padding: "7px 12px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "6px",
        transition: "background-color 0.15s ease, border-color 0.15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = "color-mix(in srgb, #c96442 6%, white)";
        e.currentTarget.style.borderColor = tk.clayInteractive;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = "transparent";
        e.currentTarget.style.borderColor = `color-mix(in srgb, ${tk.clayInteractive} 60%, transparent)`;
      }}
    >
      <IconPlus size={12} />
      {label}
    </button>
  );
}

/* ═══════════ PAGE ═══════════ */
export default function BuilderPage() {
  // Personal / domain
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [github, setGithub] = useState("");
  const [location, setLocation] = useState("");
  const [domain, setDomain] = useState("");
  const [summary, setSummary] = useState("");
  const [skills, setSkills] = useState("");

  // Repeatable arrays
  const [eduIN, setEduIN] = useState<EduRow[]>([]);
  const [eduUS, setEduUS] = useState<EduRow[]>([]);
  const [expIN, setExpIN] = useState<ExpRow[]>([]);
  const [expUS, setExpUS] = useState<ExpRow[]>([]);
  const [projects, setProjects] = useState<ProjRow[]>([]);
  const [certs, setCerts] = useState<CertRow[]>([]);

  // Validation state
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const touch = (k: string) => setTouched((p) => (p.has(k) ? p : new Set(p).add(k)));

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<BuildResult | null>(null);

  // Per-field errors (always computed; visibility controlled by touched/submitAttempted)
  const fieldErrors = useMemo(() => {
    const e: Record<string, string | null> = {
      name: V.required(name),
      domain: V.required(domain),
      email: V.email(email),
      phone: V.phone(phone),
      linkedin: V.linkedin(linkedin),
      github: V.github(github),
    };
    return e;
  }, [name, domain, email, phone, linkedin, github]);

  const showErr = (key: string): string | undefined => {
    if (!touched.has(key) && !submitAttempted) return undefined;
    return fieldErrors[key] ?? undefined;
  };

  const hasBlockingErrors = useMemo(
    () => Object.values(fieldErrors).some((e) => !!e),
    [fieldErrors]
  );

  const blankEdu = (): EduRow => ({ degree: "", institution: "", city: "", graduation_date: "" });
  const blankExp = (): ExpRow => ({ title: "", company: "", city: "", start_date: "", end_date: "", bullets_raw: "" });
  const blankProj = (): ProjRow => ({ name: "", tech_stack: "", bullets_raw: "" });
  const blankCert = (): CertRow => ({ name: "", issuer: "", date: "" });

  const updateAt = <T,>(setter: React.Dispatch<React.SetStateAction<T[]>>) =>
    (idx: number, patch: Partial<T>) =>
      setter((prev) => prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)));

  const removeAt = <T,>(setter: React.Dispatch<React.SetStateAction<T[]>>) =>
    (idx: number) => setter((prev) => prev.filter((_, i) => i !== idx));

  const canSubmit = !submitting && !hasBlockingErrors;

  const handleSubmit = async () => {
    setSubmitAttempted(true);
    if (hasBlockingErrors) {
      // Scroll to the first error
      const firstErrKey = Object.keys(fieldErrors).find((k) => !!fieldErrors[k]);
      if (firstErrKey) {
        const el = document.querySelector(`[data-field="${firstErrKey}"]`);
        if (el && "scrollIntoView" in el) {
          (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
      return;
    }
    if (submitting) return;

    setSubmitting(true);
    setError("");
    setResult(null);

    const payload = {
      contact: { name, email, phone, linkedin, github, location },
      domain,
      summary_raw: summary,
      skills_raw: skills,
      education_india: eduIN.map((e) => ({ ...e, country: "India" })),
      education_usa: eduUS.map((e) => ({ ...e, country: "USA" })),
      experience_india: expIN.map((e) => ({ ...e, country: "India" })),
      experience_usa: expUS.map((e) => ({ ...e, country: "USA" })),
      projects,
      certifications: certs,
    };

    try {
      const res = await axios.post(`${API_URL}/build`, payload);
      setResult(res.data);
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    } catch (err: unknown) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || "Build failed."
        : "Build failed.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  const downloadFile = (format: "docx" | "pdf") => {
    if (!result) return;
    window.open(`${API_URL}/download/${result.job_id}/${format}`, "_blank");
  };

  /* ─── Repeatable row renderers ─── */
  const renderEduRow = (row: EduRow, idx: number, set: React.Dispatch<React.SetStateAction<EduRow[]>>) => {
    const update = updateAt(set);
    const remove = removeAt(set);
    return (
      <Row key={idx} onRemove={() => remove(idx)}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <Field label="Degree">
            <TextInput value={row.degree} onChange={(e) => update(idx, { degree: e.target.value })} placeholder="B.Tech in Computer Science" />
          </Field>
          <Field label="Institution">
            <TextInput value={row.institution} onChange={(e) => update(idx, { institution: e.target.value })} placeholder="IIT Bombay" />
          </Field>
          <Field label="City">
            <TextInput value={row.city} onChange={(e) => update(idx, { city: e.target.value })} placeholder="Mumbai" />
          </Field>
          <Field label="Graduation date" hint="e.g. May 2024">
            <TextInput value={row.graduation_date} onChange={(e) => update(idx, { graduation_date: e.target.value })} placeholder="May 2024" />
          </Field>
        </div>
      </Row>
    );
  };

  const renderExpRow = (row: ExpRow, idx: number, set: React.Dispatch<React.SetStateAction<ExpRow[]>>) => {
    const update = updateAt(set);
    const remove = removeAt(set);
    return (
      <Row key={idx} onRemove={() => remove(idx)}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <Field label="Job title">
            <TextInput value={row.title} onChange={(e) => update(idx, { title: e.target.value })} placeholder="Software Engineer" />
          </Field>
          <Field label="Company">
            <TextInput value={row.company} onChange={(e) => update(idx, { company: e.target.value })} placeholder="Acme Corp" />
          </Field>
          <Field label="City">
            <TextInput value={row.city} onChange={(e) => update(idx, { city: e.target.value })} placeholder="Bengaluru" />
          </Field>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <Field label="Start" hint="Jun 2023">
              <TextInput value={row.start_date} onChange={(e) => update(idx, { start_date: e.target.value })} placeholder="Jun 2023" />
            </Field>
            <Field label="End" hint="or Present">
              <TextInput value={row.end_date} onChange={(e) => update(idx, { end_date: e.target.value })} placeholder="Present" />
            </Field>
          </div>
        </div>
        <Field label="What you did" hint="One line per bullet — rough is fine, AI will polish and expand.">
          <TextArea
            value={row.bullets_raw}
            onChange={(e) => update(idx, { bullets_raw: e.target.value })}
            placeholder={"built a React dashboard for the sales team\nset up CI/CD on GitHub Actions\nrefactored the auth module"}
            rows={4}
          />
        </Field>
      </Row>
    );
  };

  const renderProjRow = (row: ProjRow, idx: number, set: React.Dispatch<React.SetStateAction<ProjRow[]>>) => {
    const update = updateAt(set);
    const remove = removeAt(set);
    return (
      <Row key={idx} onRemove={() => remove(idx)}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          <Field label="Project name">
            <TextInput value={row.name} onChange={(e) => update(idx, { name: e.target.value })} placeholder="Resume Formatter" />
          </Field>
          <Field label="Tech stack">
            <TextInput value={row.tech_stack} onChange={(e) => update(idx, { tech_stack: e.target.value })} placeholder="Next.js, FastAPI, OpenAI" />
          </Field>
        </div>
        <Field label="What you built" hint="One line per bullet — even a one-liner is fine, AI will expand it.">
          <TextArea
            value={row.bullets_raw}
            onChange={(e) => update(idx, { bullets_raw: e.target.value })}
            placeholder={"parsed PDF/DOCX resumes with pdfplumber\nused GPT-4o-mini to structure into JSON"}
            rows={3}
          />
        </Field>
      </Row>
    );
  };

  const renderCertRow = (row: CertRow, idx: number, set: React.Dispatch<React.SetStateAction<CertRow[]>>) => {
    const update = updateAt(set);
    const remove = removeAt(set);
    return (
      <Row key={idx} onRemove={() => remove(idx)}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "12px" }}>
          <Field label="Name">
            <TextInput value={row.name} onChange={(e) => update(idx, { name: e.target.value })} placeholder="AWS Solutions Architect" />
          </Field>
          <Field label="Issuer">
            <TextInput value={row.issuer} onChange={(e) => update(idx, { issuer: e.target.value })} placeholder="Amazon Web Services" />
          </Field>
          <Field label="Date">
            <TextInput value={row.date} onChange={(e) => update(idx, { date: e.target.value })} placeholder="Mar 2024" />
          </Field>
        </div>
      </Row>
    );
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: tk.surface, fontFamily: tk.sans }}>
      {/* NAVBAR */}
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
        <div style={{ maxWidth: "900px", margin: "0 auto", width: "100%", display: "flex", alignItems: "center", gap: "10px" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
            <AsteriskMark size={18} color={tk.clay} />
            <span style={{ fontFamily: tk.serif, fontSize: "16px", fontWeight: 500, color: tk.onSurface, letterSpacing: "-0.01em" }}>
              Resume Formatter
            </span>
          </Link>
          <nav style={{ marginLeft: "auto", display: "flex", gap: "2px" }}>
            <Link
              href="/"
              style={{
                fontFamily: tk.sans, fontSize: "13px", fontWeight: 500,
                color: tk.onSurfaceTertiary, textDecoration: "none",
                padding: "6px 12px", borderRadius: "6px",
              }}
            >
              Format
            </Link>
            <Link
              href="/builder"
              style={{
                fontFamily: tk.sans, fontSize: "13px", fontWeight: 500,
                color: tk.clayInteractive,
                backgroundColor: "color-mix(in srgb, #c96442 10%, white)",
                textDecoration: "none",
                padding: "6px 12px", borderRadius: "6px",
              }}
            >
              Build
            </Link>
          </nav>
        </div>
      </header>

      {/* HERO */}
      <section style={{ padding: "clamp(40px, 6vw, 72px) 24px clamp(20px, 3vw, 36px)" }}>
        <div style={{ maxWidth: "720px", margin: "0 auto", textAlign: "center" }}>
          <span
            style={{
              fontFamily: tk.sans, fontSize: "11px", fontWeight: 500,
              letterSpacing: "0.14em", color: tk.clay, textTransform: "uppercase",
              display: "inline-block", marginBottom: "14px",
            }}
          >
            AI Resume Builder
          </span>
          <h1
            style={{
              fontFamily: tk.serif,
              fontSize: "clamp(30px, 4.2vw, 46px)",
              fontWeight: 500,
              color: tk.onSurface,
              lineHeight: 1.15,
              letterSpacing: "-0.015em",
              marginBottom: "14px",
            }}
          >
            Build a resume from scratch with <span style={{ color: tk.clay }}>AI polish</span>
          </h1>
          <p style={{ fontFamily: tk.sans, fontSize: "clamp(15px, 1.8vw, 17px)", color: tk.onSurfaceTertiary, lineHeight: 1.65, maxWidth: "540px", margin: "0 auto" }}>
            Fill in what you know — rough bullets are fine. AI sharpens the writing, generates a strong summary, and suggests real companies near your school to apply to.
          </p>
        </div>
      </section>

      {/* FORM */}
      <main style={{ padding: "0 24px clamp(48px, 6vw, 80px)" }}>
        <div style={{ maxWidth: "720px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "14px" }}>

          <SectionCard index={1} title="Personal" subtitle="Name and domain are required. The rest is optional but helps the AI write a stronger resume.">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
              <div data-field="name">
                <Field label="Full name" required error={showErr("name")}>
                  <TextInput
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    onBlur={() => touch("name")}
                    placeholder="Ada Lovelace"
                    invalid={!!showErr("name")}
                  />
                </Field>
              </div>
              <div data-field="domain">
                <Field label="Domain" required error={showErr("domain")} hint={showErr("domain") ? undefined : "Used to derive the title shown below your name."}>
                  <TextInput
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    onBlur={() => touch("domain")}
                    placeholder="Software Engineering"
                    invalid={!!showErr("domain")}
                  />
                </Field>
              </div>
              <div data-field="email">
                <Field label="Email" error={showErr("email")}>
                  <TextInput
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onBlur={() => touch("email")}
                    placeholder="ada@example.com"
                    invalid={!!showErr("email")}
                  />
                </Field>
              </div>
              <div data-field="phone">
                <Field label="Phone" error={showErr("phone")}>
                  <TextInput
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    onBlur={() => touch("phone")}
                    placeholder="+91 98765 43210"
                    invalid={!!showErr("phone")}
                  />
                </Field>
              </div>
              <div data-field="linkedin">
                <Field label="LinkedIn" hint={showErr("linkedin") ? undefined : "Handle or full URL — AI will normalize to a clickable link."} error={showErr("linkedin")}>
                  <TextInput
                    value={linkedin}
                    onChange={(e) => setLinkedin(e.target.value)}
                    onBlur={() => touch("linkedin")}
                    placeholder="ada-lovelace"
                    invalid={!!showErr("linkedin")}
                  />
                </Field>
              </div>
              <div data-field="github">
                <Field label="GitHub" hint={showErr("github") ? undefined : "Handle or full URL."} error={showErr("github")}>
                  <TextInput
                    value={github}
                    onChange={(e) => setGithub(e.target.value)}
                    onBlur={() => touch("github")}
                    placeholder="adalovelace"
                    invalid={!!showErr("github")}
                  />
                </Field>
              </div>
              <div style={{ gridColumn: "span 2" }}>
                <Field label="Current location">
                  <TextInput value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Mumbai, India" />
                </Field>
              </div>
            </div>
          </SectionCard>

          <SectionCard index={2} title="Professional summary" subtitle="Optional — leave blank and AI will write one based on your domain, education, and experience.">
            <TextArea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="A short paragraph about who you are professionally…" rows={4} />
          </SectionCard>

          <SectionCard index={3} title="Technical skills" subtitle="Comma-separated. AI will group them into sensible categories.">
            <TextArea value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="Python, TypeScript, React, FastAPI, PostgreSQL, AWS, Docker, …" rows={3} />
          </SectionCard>

          <SectionCard index={4} title="Education — India" subtitle="One row per degree.">
            {eduIN.length === 0 && <EmptyHint>No Indian education added yet.</EmptyHint>}
            {eduIN.map((row, i) => renderEduRow(row, i, setEduIN))}
            <AddButton label="Add Indian education" onClick={() => setEduIN((p) => [...p, blankEdu()])} />
          </SectionCard>

          <SectionCard index={5} title="Education — USA" subtitle="One row per degree.">
            {eduUS.length === 0 && <EmptyHint>No US education added yet.</EmptyHint>}
            {eduUS.map((row, i) => renderEduRow(row, i, setEduUS))}
            <AddButton label="Add US education" onClick={() => setEduUS((p) => [...p, blankEdu()])} />
          </SectionCard>

          <SectionCard index={6} title="Experience — India" subtitle="Optional. Roles you held in India.">
            {expIN.length === 0 && <EmptyHint>No Indian experience added — skip if you have none.</EmptyHint>}
            {expIN.map((row, i) => renderExpRow(row, i, setExpIN))}
            <AddButton label="Add Indian experience" onClick={() => setExpIN((p) => [...p, blankExp()])} />
          </SectionCard>

          <SectionCard index={7} title="Experience — USA" subtitle="Optional. Roles you held in the USA.">
            {expUS.length === 0 && <EmptyHint>No US experience added — skip if you have none.</EmptyHint>}
            {expUS.map((row, i) => renderExpRow(row, i, setExpUS))}
            <AddButton label="Add US experience" onClick={() => setExpUS((p) => [...p, blankExp()])} />
          </SectionCard>

          <SectionCard index={8} title="Projects" subtitle="Especially useful if you don't have full-time experience yet.">
            {projects.length === 0 && <EmptyHint>No projects added.</EmptyHint>}
            {projects.map((row, i) => renderProjRow(row, i, setProjects))}
            <AddButton label="Add project" onClick={() => setProjects((p) => [...p, blankProj()])} />
          </SectionCard>

          <SectionCard index={9} title="Certifications" subtitle="Optional.">
            {certs.length === 0 && <EmptyHint>No certifications added.</EmptyHint>}
            {certs.map((row, i) => renderCertRow(row, i, setCerts))}
            <AddButton label="Add certification" onClick={() => setCerts((p) => [...p, blankCert()])} />
          </SectionCard>

          {/* Submit */}
          <div style={{ display: "flex", flexDirection: "column", gap: "10px", paddingTop: "8px" }}>
            {submitting ? (
              <div
                style={{
                  width: "100%",
                  borderRadius: "10px",
                  border: `1px solid color-mix(in srgb, #c96442 35%, transparent)`,
                  backgroundColor: "color-mix(in srgb, #c96442 6%, white)",
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
            ) : (
              <>
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  style={{
                    width: "100%",
                    padding: "14px 18px",
                    borderRadius: "10px",
                    backgroundColor: canSubmit ? tk.clayInteractive : tk.surfaceSecondary,
                    color: canSubmit ? "#faf9f5" : tk.onSurfaceGhost,
                    border: `1px solid ${canSubmit ? tk.clayInteractive : tk.borderTertiary}`,
                    fontFamily: tk.sans,
                    fontSize: "15px",
                    fontWeight: 500,
                    letterSpacing: "0.005em",
                    cursor: submitting ? "not-allowed" : "pointer",
                    transition: "transform 0.12s ease, box-shadow 0.15s ease",
                    boxShadow: canSubmit ? "0 1px 2px color-mix(in srgb, #c96442 25%, transparent)" : "none",
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
                  Build my resume
                </button>
                {submitAttempted && hasBlockingErrors && (
                  <p style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.danger, textAlign: "center", margin: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: "6px" }}>
                    <IconAlert size={12} />
                    Fix the highlighted fields above to continue.
                  </p>
                )}
              </>
            )}

            {error && (
              <p style={{ fontFamily: tk.sans, fontSize: "13px", color: tk.danger, textAlign: "center", margin: 0 }}>
                {error}
              </p>
            )}
          </div>

          {/* Result */}
          {result && (
            <div
              className="animate-in fade-in slide-in-from-bottom-4 duration-300"
              style={{
                marginTop: "8px",
                backgroundColor: tk.surfaceSecondary,
                border: `1px solid ${tk.borderTertiary}`,
                borderRadius: "16px",
                padding: "24px",
                display: "flex",
                flexDirection: "column",
                gap: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div
                  style={{
                    width: "36px", height: "36px", borderRadius: "50%",
                    backgroundColor: "color-mix(in srgb, #c96442 14%, white)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    flexShrink: 0, color: tk.clayInteractive,
                  }}
                >
                  <IconCheck size={18} />
                </div>
                <div>
                  <p style={{ fontFamily: tk.serif, fontSize: "15px", fontWeight: 500, color: tk.onSurface, margin: 0, lineHeight: 1.3 }}>
                    Resume built successfully
                  </p>
                  <p style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceGhost, margin: "3px 0 0" }}>
                    {result.candidate_name}
                  </p>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                <button
                  onClick={() => downloadFile("docx")}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center", gap: "7px",
                    padding: "12px", borderRadius: "10px", backgroundColor: "#ffffff",
                    color: tk.clayInteractive, border: `1px solid ${tk.clayInteractive}`,
                    fontFamily: tk.sans, fontSize: "14px", fontWeight: 500, cursor: "pointer",
                    transition: "background-color 0.15s ease",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "color-mix(in srgb, #c96442 8%, white)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#ffffff"; }}
                >
                  <IconDownload size={14} />
                  Download DOCX
                </button>
                <button
                  onClick={() => downloadFile("pdf")}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center", gap: "7px",
                    padding: "12px", borderRadius: "10px", backgroundColor: tk.clayInteractive,
                    color: "#faf9f5", border: `1px solid ${tk.clayInteractive}`,
                    fontFamily: tk.sans, fontSize: "14px", fontWeight: 500, cursor: "pointer",
                    transition: "box-shadow 0.15s ease, transform 0.12s ease",
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

              {/* Job leads */}
              {result.job_leads && result.job_leads.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px", paddingTop: "6px", borderTop: `1px solid ${tk.borderTertiary}` }}>
                  <div>
                    <h3 style={{ fontFamily: tk.serif, fontSize: "15px", fontWeight: 500, color: tk.onSurface, margin: "12px 0 2px" }}>
                      Companies to apply to
                    </h3>
                    <p style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceGhost, margin: 0, lineHeight: 1.5 }}>
                      Real firms in {domain} near your education cities. Verify before applying — AI suggestions can be out of date.
                    </p>
                  </div>
                  <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "8px" }}>
                    {result.job_leads.map((lead, i) => (
                      <li
                        key={i}
                        style={{
                          backgroundColor: "#ffffff",
                          border: `1px solid ${tk.borderTertiary}`,
                          borderRadius: "10px",
                          padding: "12px 14px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "3px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "12px" }}>
                          <span style={{ fontFamily: tk.sans, fontSize: "14px", fontWeight: 500, color: tk.onSurface }}>
                            {lead.company}
                          </span>
                          <span style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceGhost, whiteSpace: "nowrap" }}>
                            {lead.city}{lead.country ? `, ${lead.country}` : ""}
                          </span>
                        </div>
                        {lead.why && (
                          <p style={{ fontFamily: tk.sans, fontSize: "13px", color: tk.onSurfaceTertiary, margin: 0, lineHeight: 1.5 }}>
                            {lead.why}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* FOOTER */}
      <footer style={{ backgroundColor: tk.surfaceDark, padding: "32px 24px", marginTop: "auto" }}>
        <div style={{ maxWidth: "720px", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <AsteriskMark size={16} color={tk.clay} />
            <span style={{ fontFamily: tk.serif, fontSize: "14px", fontWeight: 500, color: tk.onDarkMuted }}>
              Resume Formatter
            </span>
          </div>
          <p style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onDarkMuted, margin: 0 }}>
            ATS-ready · AI-powered · Instant
          </p>
        </div>
      </footer>
    </div>
  );
}
