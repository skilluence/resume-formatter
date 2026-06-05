"use client";

import { CSSProperties, useRef, useLayoutEffect } from "react";
import { tk } from "@/lib/tokens";
import { isCoursework, type Resume, type SectionStatus } from "@/lib/resume";

/* A control card in the left rail: Keep / Skip / Edit for one section, a GPA
   on/off switch on Education, and — when Edit is on — that section's fields
   right here on the left. The right pane stays a clean, paginated document. */

interface Props {
  id: string;
  label: string;
  status: SectionStatus;
  editing: boolean;
  isEducation?: boolean;
  showGpa?: boolean;
  showCoursework?: boolean;
  resume: Resume;
  onChange: (r: Resume) => void;
  onKeep: () => void;
  onSkip: () => void;
  onToggleEdit: () => void;
  onToggleGpa?: () => void;
  onToggleCoursework?: () => void;
}

export default function SectionCard(p: Props) {
  const skipped = p.status === "skipped";
  const accent = p.status === "kept" ? tk.green : skipped ? tk.borderSecondary : tk.clay;
  return (
    <div
      style={{
        background: skipped ? tk.surfaceSecondary : "#fff",
        border: `1px solid ${p.editing ? tk.clay : tk.borderTertiary}`,
        borderLeft: `3px solid ${p.editing ? tk.clay : accent}`,
        borderRadius: "10px",
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Dot status={p.status} />
        <span style={{ flex: 1, fontFamily: tk.sans, fontSize: "13.5px", fontWeight: 500, color: tk.onSurface, textDecoration: skipped ? "line-through" : "none" }}>
          {p.label}
        </span>
      </div>
      {!p.editing && snippet(p.id, p.resume) && (
        <p style={{ fontFamily: tk.sans, fontSize: "11.5px", color: tk.onSurfaceTertiary, margin: "5px 0 0", lineHeight: 1.45, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
          {snippet(p.id, p.resume)}
        </p>
      )}

      <div style={{ display: "flex", gap: "6px", marginTop: "9px" }}>
        <Pill active={p.status === "kept"} color={tk.green} onClick={p.onKeep} pressed={p.status === "kept"}>
          ✓ Keep
        </Pill>
        <Pill active={skipped} color={tk.red} onClick={p.onSkip} pressed={skipped}>
          ✕ Skip
        </Pill>
        <Pill active={p.editing} color={tk.clayInteractive} onClick={p.onToggleEdit} pressed={p.editing}>
          {p.editing ? "Done" : "✎ Edit"}
        </Pill>
      </div>

      {p.isEducation && (
        <button
          type="button"
          role="switch"
          aria-checked={!!p.showGpa}
          aria-label="Show or hide GPA on the resume"
          onClick={p.onToggleGpa}
          style={{ marginTop: "9px", width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: tk.surfaceSecondary, border: `1px solid ${tk.borderTertiary}`, borderRadius: "8px", padding: "6px 10px", cursor: "pointer", fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceSecondary }}
        >
          <span>Show GPA / CGPA</span>
          <Switch on={!!p.showGpa} />
        </button>
      )}

      {p.isEducation && (
        <button
          type="button"
          role="switch"
          aria-checked={!!p.showCoursework}
          aria-label="Show or hide relevant coursework on the resume"
          onClick={p.onToggleCoursework}
          style={{ marginTop: "7px", width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: tk.surfaceSecondary, border: `1px solid ${tk.borderTertiary}`, borderRadius: "8px", padding: "6px 10px", cursor: "pointer", fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceSecondary }}
        >
          <span>Show Relevant Coursework</span>
          <Switch on={!!p.showCoursework} />
        </button>
      )}

      {p.editing && (
        <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: `1px dashed ${tk.borderSecondary}` }}>
          <SectionEditor id={p.id} resume={p.resume} onChange={p.onChange} />
        </div>
      )}
    </div>
  );
}

/* a short at-a-glance summary of what a section contains */
function snippet(id: string, r: Resume): string {
  const join = (xs: (string | null)[]) => xs.filter(Boolean).join(" · ");
  let s = "";
  if (id === "summary") s = r.summary || "";
  else if (id === "skills") { const n = Object.keys(r.skills).length; s = `${n} categor${n === 1 ? "y" : "ies"}`; }
  else if (id === "experience") s = join(r.experience.map((j) => j.company || j.title));
  else if (id === "projects") s = join(r.projects.map((p) => p.name));
  else if (id === "certifications") s = join(r.certifications.map((c) => c.name));
  else if (id === "education") s = join(r.education.map((e) => e.institution || e.degree));
  else if (id.startsWith("additional-")) { const sec = r.additional_sections[parseInt(id.split("-")[1], 10)]; s = sec ? sec.items[0] || sec.text || `${sec.items.length} item(s)` : ""; }
  return s.length > 120 ? s.slice(0, 120) + "…" : s;
}

/* ── the per-section editor (left rail) ─────────────────────────────────── */
const clone = (r: Resume): Resume => JSON.parse(JSON.stringify(r));

export function SectionEditor({ id, resume, onChange }: { id: string; resume: Resume; onChange: (r: Resume) => void }) {
  const edit = (mutate: (r: Resume) => void) => {
    const r = clone(resume);
    mutate(r);
    onChange(r);
  };

  if (id === "header") {
    return (
      <>
        <Field label="Name" value={resume.name} onChange={(v) => edit((r) => (r.name = v))} />
        {!resume.name.trim() && (
          <p role="alert" style={{ fontFamily: tk.sans, fontSize: "11px", color: tk.red, margin: "-2px 0 6px" }}>
            A name is required to download the resume.
          </p>
        )}
        <Field label="Headline" value={resume.headline || ""} onChange={(v) => edit((r) => (r.headline = v || null))} />
        <Field label="Phone" value={resume.contact.phone || ""} onChange={(v) => edit((r) => (r.contact.phone = v || null))} />
        <NamedLink
          name="Email"
          textValue={resume.contact.email_label || ""}
          textPlaceholder={resume.contact.email || "you@email.com"}
          linkValue={resume.contact.email || ""}
          linkLabel="Email address"
          linkPlaceholder="you@email.com"
          onText={(v) => edit((r) => (r.contact.email_label = v || null))}
          onLink={(v) => edit((r) => (r.contact.email = v || null))}
        />
        <NamedLink
          name="LinkedIn"
          textValue={resume.contact.linkedin_label || ""}
          textPlaceholder="LinkedIn"
          linkValue={resume.contact.linkedin || ""}
          linkLabel="Link (URL)"
          linkPlaceholder="https://linkedin.com/in/…"
          onText={(v) => edit((r) => (r.contact.linkedin_label = v || null))}
          onLink={(v) => edit((r) => (r.contact.linkedin = v || null))}
        />
        <NamedLink
          name="GitHub"
          textValue={resume.contact.github_label || ""}
          textPlaceholder="GitHub"
          linkValue={resume.contact.github || ""}
          linkLabel="Link (URL)"
          linkPlaceholder="https://github.com/…"
          onText={(v) => edit((r) => (r.contact.github_label = v || null))}
          onLink={(v) => edit((r) => (r.contact.github = v || null))}
        />
        <Field label="Location" value={resume.contact.location || ""} onChange={(v) => edit((r) => (r.contact.location = v || null))} />
        <LinksEditor resume={resume} edit={edit} />
      </>
    );
  }
  if (id === "summary") {
    return <Area value={resume.summary || ""} onChange={(v) => edit((r) => (r.summary = v))} />;
  }
  if (id === "skills") {
    return <SkillsEditor resume={resume} edit={edit} />;
  }
  if (id === "experience") {
    return (
      <>
        {resume.experience.map((job, i) => (
          <Entry key={i} onRemove={() => edit((r) => r.experience.splice(i, 1))}>
            <Field label="Title" value={job.title} onChange={(v) => edit((r) => (r.experience[i].title = v))} />
            <Field label="Company" value={job.company} onChange={(v) => edit((r) => (r.experience[i].company = v))} />
            <Row>
              <Field label="Start" value={job.start_date} onChange={(v) => edit((r) => (r.experience[i].start_date = v))} />
              <Field label="End" value={job.end_date} onChange={(v) => edit((r) => (r.experience[i].end_date = v))} />
            </Row>
            <Field label="Location" value={job.location || ""} onChange={(v) => edit((r) => (r.experience[i].location = v || null))} />
            <List items={job.bullets} placeholder="Bullet" onChange={(b) => edit((r) => (r.experience[i].bullets = b))} />
          </Entry>
        ))}
        <Add onClick={() => edit((r) => r.experience.push({ title: "", company: "", location: null, start_date: "", end_date: "", bullets: [] }))}>+ Add role</Add>
      </>
    );
  }
  if (id === "projects") {
    return (
      <>
        {resume.projects.map((p, i) => (
          <Entry key={i} onRemove={() => edit((r) => r.projects.splice(i, 1))}>
            <Field label="Name" value={p.name} onChange={(v) => edit((r) => (r.projects[i].name = v))} />
            <Field label="Tech stack" value={p.tech_stack || ""} onChange={(v) => edit((r) => (r.projects[i].tech_stack = v || null))} />
            <List items={p.bullets} placeholder="Bullet" onChange={(b) => edit((r) => (r.projects[i].bullets = b))} />
          </Entry>
        ))}
        <Add onClick={() => edit((r) => r.projects.push({ name: "", tech_stack: null, bullets: [] }))}>+ Add project</Add>
      </>
    );
  }
  if (id === "certifications") {
    return (
      <>
        {resume.certifications.map((c, i) => (
          <Entry key={i} onRemove={() => edit((r) => r.certifications.splice(i, 1))}>
            <Field label="Name" value={c.name} onChange={(v) => edit((r) => (r.certifications[i].name = v))} />
            <Row>
              <Field label="Issuer" value={c.issuer || ""} onChange={(v) => edit((r) => (r.certifications[i].issuer = v || null))} />
              <Field label="Date" value={c.date || ""} onChange={(v) => edit((r) => (r.certifications[i].date = v || null))} />
            </Row>
            <List items={c.bullets} placeholder="Detail" onChange={(b) => edit((r) => (r.certifications[i].bullets = b))} />
          </Entry>
        ))}
        <Add onClick={() => edit((r) => r.certifications.push({ name: "", issuer: null, date: null, bullets: [] }))}>+ Add certification</Add>
      </>
    );
  }
  if (id === "education") {
    return (
      <>
        {resume.education.map((e, i) => (
          <Entry key={i} onRemove={() => edit((r) => r.education.splice(i, 1))}>
            <Field label="Degree" value={e.degree} onChange={(v) => edit((r) => (r.education[i].degree = v))} />
            <Field label="Institution" value={e.institution} onChange={(v) => edit((r) => (r.education[i].institution = v))} />
            <Row>
              <Field label="Date" value={e.graduation_date || ""} onChange={(v) => edit((r) => (r.education[i].graduation_date = v || null))} />
              <PrefixField
                label="GPA"
                prefix="GPA:"
                placeholder="4.0"
                value={(e.gpa || "").replace(/^\s*(c?gpa|grade)\s*:?\s*/i, "")}
                onChange={(v) => edit((r) => (r.education[i].gpa = v.trim() ? `GPA: ${v.trim()}` : null))}
              />
            </Row>
            <Field label="Location" value={e.location || ""} onChange={(v) => edit((r) => (r.education[i].location = v || null))} />
            <PrefixField
              label="Relevant Coursework"
              prefix="Relevant Coursework:"
              placeholder="Python, SQL, Machine Learning…"
              value={(e.details.find(isCoursework) || "").replace(/^\s*(relevant\s+)?coursework\s*:?\s*/i, "")}
              onChange={(v) => edit((r) => {
                const d = r.education[i].details;
                const ci = d.findIndex(isCoursework);
                const nv = v.trim() ? `Relevant Coursework: ${v.trim()}` : null;
                if (ci >= 0) { if (nv) d[ci] = nv; else d.splice(ci, 1); }
                else if (nv) d.push(nv);
              })}
            />
            <List
              items={e.details.filter((d) => !isCoursework(d))}
              placeholder="Honor / detail"
              onChange={(items) => edit((r) => {
                const course = r.education[i].details.filter(isCoursework);
                r.education[i].details = [...items, ...course];
              })}
            />
          </Entry>
        ))}
        <Add onClick={() => edit((r) => r.education.push({ degree: "", institution: "", location: null, graduation_date: null, gpa: null, details: [] }))}>+ Add education</Add>
      </>
    );
  }
  if (id.startsWith("additional-")) {
    const idx = parseInt(id.split("-")[1], 10);
    const sec = resume.additional_sections[idx];
    if (!sec) return null;
    return (
      <>
        <Field label="Heading" value={sec.heading} onChange={(v) => edit((r) => (r.additional_sections[idx].heading = v))} />
        {sec.items.length || !sec.text ? (
          <List items={sec.items} placeholder="Item" onChange={(items) => edit((r) => (r.additional_sections[idx].items = items))} />
        ) : (
          <Area value={sec.text || ""} onChange={(v) => edit((r) => (r.additional_sections[idx].text = v))} />
        )}
      </>
    );
  }
  return null;
}

/* ── inputs ─────────────────────────────────────────────────────────────── */
function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label style={{ display: "block", flex: 1, marginBottom: "6px" }}>
      <span style={{ fontFamily: tk.sans, fontSize: "10px", color: tk.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </label>
  );
}

/* A field with a fixed, non-editable prefix (e.g. "GPA:" or "Relevant Coursework:")
   shown before the editable value. */
function PrefixField({ label, prefix, value, placeholder, onChange }: { label: string; prefix: string; value: string; placeholder?: string; onChange: (v: string) => void }) {
  return (
    <label style={{ display: "block", flex: 1, marginBottom: "6px" }}>
      <span style={{ fontFamily: tk.sans, fontSize: "10px", color: tk.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", border: `1px solid ${tk.borderSecondary}`, borderRadius: "7px", background: "#fff" }}>
        <span style={{ fontFamily: tk.sans, fontSize: "13px", fontWeight: 600, color: tk.onSurfaceTertiary, padding: "6px 0 6px 9px", whiteSpace: "nowrap" }}>{prefix}&nbsp;</span>
        <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} style={{ flex: 1, minWidth: 0, fontFamily: tk.sans, fontSize: "13px", padding: "6px 9px 6px 2px", border: "none", outline: "none", background: "transparent", color: tk.onSurface }} />
      </div>
    </label>
  );
}

/* A named contact link (Email / LinkedIn / GitHub) with the display text and the
   real hyperlink as two separate, editable fields. */
function NamedLink({ name, textValue, textPlaceholder, linkValue, linkLabel, linkPlaceholder, onText, onLink }: {
  name: string; textValue: string; textPlaceholder: string; linkValue: string;
  linkLabel: string; linkPlaceholder: string; onText: (v: string) => void; onLink: (v: string) => void;
}) {
  return (
    <div style={{ marginBottom: "4px" }}>
      <span style={{ fontFamily: tk.sans, fontSize: "10px", fontWeight: 600, color: tk.onSurfaceSecondary, textTransform: "uppercase", letterSpacing: "0.05em" }}>{name}</span>
      <Row>
        <Field label="Text to display" value={textValue} placeholder={textPlaceholder} onChange={onText} />
        <Field label={linkLabel} value={linkValue} placeholder={linkPlaceholder} onChange={onLink} />
      </Row>
    </div>
  );
}
/* A textarea that grows to fit its content (so long bullets/summaries are fully
   visible while editing), with a generous minimum height. Still drag-resizable. */
function AutoTextarea({ value, onChange, placeholder, minHeight = 64 }: { value: string; onChange: (v: string) => void; placeholder?: string; minHeight?: number }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(minHeight, el.scrollHeight + 2)}px`;
  }, [value, minHeight]);
  return (
    <textarea
      ref={ref}
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      style={{ ...inputStyle, lineHeight: 1.55, resize: "vertical", overflow: "hidden", minHeight: `${minHeight}px` }}
    />
  );
}

function Area({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <AutoTextarea value={value} onChange={onChange} minHeight={140} />;
}
function Row({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", gap: "8px" }}>{children}</div>;
}
function Entry({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) {
  return (
    <div style={{ position: "relative", background: tk.surfaceSecondary, borderRadius: "8px", padding: "10px 10px 8px", marginBottom: "9px" }}>
      <button type="button" onClick={onRemove} aria-label="Remove entry" style={{ position: "absolute", top: "6px", right: "6px", width: "22px", height: "22px", borderRadius: "6px", border: `1px solid ${tk.borderSecondary}`, background: "#fff", color: tk.red, cursor: "pointer", fontSize: "13px", lineHeight: 1 }}>
        ×
      </button>
      {children}
    </div>
  );
}
function List({ items, onChange, placeholder }: { items: string[]; onChange: (i: string[]) => void; placeholder: string }) {
  const set = (i: number, v: string) => onChange(items.map((it, j) => (j === i ? v : it)));
  return (
    <div>
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", gap: "6px", marginBottom: "6px", alignItems: "flex-start" }}>
          <span style={{ color: tk.onSurfaceGhost, paddingTop: "10px" }}>•</span>
          <AutoTextarea value={it} onChange={(v) => set(i, v)} placeholder={placeholder} minHeight={56} />
          <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label="Remove item" style={{ flexShrink: 0, width: "26px", height: "30px", borderRadius: "6px", border: `1px solid ${tk.borderSecondary}`, background: "#fff", color: tk.red, cursor: "pointer", fontSize: "15px", lineHeight: 1 }}>
            ×
          </button>
        </div>
      ))}
      <Add onClick={() => onChange([...items, ""])}>+ Add</Add>
    </div>
  );
}
/* Add / edit / remove the extra contact links (website, portfolio, Twitter, …).
   Each link has display text + a URL — exactly what Word shows. The named
   LinkedIn/GitHub/Email fields above stay separate; this is for everything else. */
function LinksEditor({ resume, edit }: { resume: Resume; edit: (m: (r: Resume) => void) => void }) {
  const links = resume.contact.links || [];
  return (
    <div style={{ marginTop: "4px" }}>
      <span style={{ fontFamily: tk.sans, fontSize: "10px", color: tk.onSurfaceTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Other links (website, portfolio…)
      </span>
      {links.map((lnk, i) => (
        <div key={i} style={{ display: "flex", gap: "6px", marginTop: "5px", alignItems: "flex-start" }}>
          <input
            value={lnk.label}
            placeholder="Display text"
            aria-label={`Link ${i + 1} display text`}
            onChange={(e) => edit((r) => (r.contact.links[i].label = e.target.value))}
            style={{ ...inputStyle, flex: "0 0 38%" }}
          />
          <input
            value={lnk.url}
            placeholder="https://…"
            aria-label={`Link ${i + 1} URL`}
            onChange={(e) => edit((r) => (r.contact.links[i].url = e.target.value))}
            style={inputStyle}
          />
          <button
            type="button"
            onClick={() => edit((r) => r.contact.links.splice(i, 1))}
            aria-label="Remove link"
            style={{ flexShrink: 0, width: "26px", height: "30px", borderRadius: "6px", border: `1px solid ${tk.borderSecondary}`, background: "#fff", color: tk.red, cursor: "pointer", fontSize: "15px", lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      ))}
      <div style={{ marginTop: "6px" }}>
        <Add onClick={() => edit((r) => (r.contact.links = [...(r.contact.links || []), { label: "", url: "" }]))}>+ Add link</Add>
      </div>
    </div>
  );
}

function SkillsEditor({ resume, edit }: { resume: Resume; edit: (m: (r: Resume) => void) => void }) {
  const entries = Object.entries(resume.skills);
  const rename = (oldKey: string, newKey: string) =>
    edit((r) => {
      const rebuilt: Record<string, string[]> = {};
      for (const [k, v] of Object.entries(r.skills)) rebuilt[k === oldKey ? newKey : k] = v;
      r.skills = rebuilt;
    });
  return (
    <>
      {entries.map(([cat, items]) => (
        <Entry
          key={cat}
          onRemove={() =>
            edit((r) => {
              const rebuilt: Record<string, string[]> = {};
              for (const [k, v] of Object.entries(r.skills)) if (k !== cat) rebuilt[k] = v;
              r.skills = rebuilt;
            })
          }
        >
          <Field label="Category" value={cat} onChange={(v) => rename(cat, v)} />
          <Field label="Skills (comma-separated)" value={items.join(", ")} onChange={(v) => edit((r) => (r.skills[cat] = v.split(",").map((s) => s.trim()).filter(Boolean)))} />
        </Entry>
      ))}
      <Add onClick={() => edit((r) => (r.skills = { ...r.skills, "New category": [] }))}>+ Add category</Add>
    </>
  );
}
function Add({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} style={{ fontFamily: tk.sans, fontSize: "12px", fontWeight: 500, color: tk.clayInteractive, background: "color-mix(in srgb, #c96442 8%, white)", border: `1px solid ${tk.borderTertiary}`, borderRadius: "7px", padding: "5px 11px", cursor: "pointer" }}>
      {children}
    </button>
  );
}

const inputStyle: CSSProperties = {
  width: "100%",
  fontFamily: tk.sans,
  fontSize: "13px",
  padding: "6px 9px",
  border: `1px solid ${tk.borderSecondary}`,
  borderRadius: "7px",
  background: "#fff",
  outline: "none",
  color: tk.onSurface,
};

/* ── little visuals ─────────────────────────────────────────────────────── */
function Dot({ status }: { status: SectionStatus }) {
  const c = status === "kept" ? tk.green : status === "skipped" ? tk.red : tk.onSurfaceGhost;
  return <span aria-hidden style={{ width: "9px", height: "9px", borderRadius: "50%", backgroundColor: status === "pending" ? "transparent" : c, border: `1.5px solid ${c}`, flexShrink: 0 }} />;
}
function Pill({ children, active, color, onClick, pressed }: { children: React.ReactNode; active: boolean; color: string; onClick: () => void; pressed: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      style={{ flex: 1, fontFamily: tk.sans, fontSize: "12px", fontWeight: 500, padding: "5px 6px", borderRadius: "7px", cursor: "pointer", border: `1px solid ${active ? color : tk.borderTertiary}`, background: active ? `color-mix(in srgb, ${color} 12%, white)` : "#fff", color: active ? color : tk.onSurfaceTertiary }}
    >
      {children}
    </button>
  );
}
function Switch({ on }: { on: boolean }) {
  return (
    <span aria-hidden style={{ width: "32px", height: "18px", borderRadius: "999px", backgroundColor: on ? tk.green : tk.borderSecondary, position: "relative", flexShrink: 0, transition: "background-color 0.15s ease" }}>
      <span style={{ position: "absolute", top: "2px", left: on ? "16px" : "2px", width: "14px", height: "14px", borderRadius: "50%", backgroundColor: "#fff", transition: "left 0.15s ease" }} />
    </span>
  );
}
