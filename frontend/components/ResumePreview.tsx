"use client";

import { useEffect, useMemo, useRef, useState, Fragment, CSSProperties, ReactNode } from "react";
import { tk, doc } from "@/lib/tokens";
import { isCoursework, type Resume, type StatusMap } from "@/lib/resume";
import { renderRich, type RichOpts } from "@/lib/rich";

/* ────────────────────────────────────────────────────────────────────────────
   ResumePreview — the live document as real, paginated A4 pages (like Word).
   Pagination is BLOCK-BASED: the content is split into atomic blocks (a bullet,
   an entry, a heading+first-line) and packed onto pages so a line is NEVER cut
   across a page break. Tight 0.2" margins mirror the actual DOCX, and the whole
   stack scales to fit the pane (responsive). Display-only — editing is on the
   left, so skipped sections drop out and GPA hides on toggle: what you see is
   what downloads.
──────────────────────────────────────────────────────────────────────────── */

const PAGE_W = 794; // A4 width  @ 96dpi
const PAGE_H = 1123; // A4 height @ 96dpi
const PAD = 19; // 0.2" margin (mirrors compact_ats.py)
const CONTENT_W = PAGE_W - PAD * 2;
const CONTENT_H = PAGE_H - PAD * 2;
const LIMIT = CONTENT_H - 20; // small safety buffer (margins aren't in offsetHeight)
const GAP = 26; // gap between page sheets

interface Props {
  resume: Resume;
  status: StatusMap;
  showGpa: boolean;
  sectionOrder?: string[];
  showCoursework?: boolean;
  /* Optional: paint added skills/keywords neon-green (AI Tailor only).
     Absent on /format -> text renders identically (renderRich fast-path). */
  highlight?: RichOpts;
}

export default function ResumePreview({ resume, status, showGpa, sectionOrder, showCoursework, highlight }: Props) {
  const blocks = useMemo(() => buildBlocks(resume, status, showGpa, sectionOrder, showCoursework, highlight), [resume, status, showGpa, sectionOrder, showCoursework, highlight]);
  const measureRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [pages, setPages] = useState<number[][]>([blocks.map((_, i) => i)]);
  const [scale, setScale] = useState(1);

  // Pack blocks onto pages by measured height — never split a block.
  useEffect(() => {
    const c = measureRef.current;
    if (!c) return;
    const heights = Array.from(c.children).map((el) => (el as HTMLElement).offsetHeight);
    const packed: number[][] = [];
    let cur: number[] = [];
    let h = 0;
    heights.forEach((bh, i) => {
      if (cur.length && h + bh > LIMIT) {
        packed.push(cur);
        cur = [];
        h = 0;
      }
      cur.push(i);
      h += bh;
    });
    if (cur.length) packed.push(cur);
    setPages((prev) => (eqPages(prev, packed) ? prev : packed));
  });

  // Scale the page stack to fit the available width (responsive).
  useEffect(() => {
    const measure = () => {
      const w = wrapRef.current?.clientWidth ?? PAGE_W;
      setScale(Math.min(1, w / PAGE_W));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  const unscaledH = pages.length * PAGE_H + (pages.length - 1) * GAP;

  return (
    <div ref={wrapRef} style={{ width: "100%", display: "flex", justifyContent: "center" }}>
      {/* hidden per-block measurer at exact content width */}
      <div ref={measureRef} aria-hidden style={{ position: "absolute", left: -99999, top: 0, width: `${CONTENT_W}px`, visibility: "hidden", pointerEvents: "none", fontFamily: doc.font }}>
        {blocks.map((b, i) => (
          <div key={i}>{b}</div>
        ))}
      </div>

      {/* scaled page stack */}
      <div style={{ height: `${unscaledH * scale}px`, width: `${PAGE_W * scale}px` }}>
        <div style={{ transform: `scale(${scale})`, transformOrigin: "top left", width: `${PAGE_W}px`, display: "flex", flexDirection: "column", gap: `${GAP}px` }}>
          {pages.map((idxs, p) => (
            <div key={p} style={pageStyle} role="document" aria-label={`Resume page ${p + 1} of ${pages.length}`}>
              <div style={{ width: `${CONTENT_W}px` }}>
                {idxs.map((i) => (
                  <div key={i}>{blocks[i]}</div>
                ))}
              </div>
              <span style={pageNum}>{p + 1} / {pages.length}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function eqPages(a: number[][], b: number[][]) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].length !== b[i].length) return false;
    for (let j = 0; j < a[i].length; j++) if (a[i][j] !== b[i][j]) return false;
  }
  return true;
}

/* ── build the ordered list of atomic blocks ────────────────────────────── */
function buildBlocks(resume: Resume, status: StatusMap, showGpa: boolean, order?: string[], showCoursework?: boolean, opts: RichOpts = {}): ReactNode[] {
  const kept = (id: string) => status[id] !== "skipped";
  const rich = (t: string) => renderRich(t, opts);
  const out: ReactNode[] = [];

  out.push(<Identity key="id" resume={resume} />);

  // push a section: header rides along with its first content line (no orphan)
  const section = (id: string, title: string, lines: ReactNode[]) => {
    if (!kept(id) || lines.length === 0) return;
    out.push(
      <div key={`${id}-0`}>
        <SectionHeader title={title} />
        {lines[0]}
      </div>
    );
    for (let i = 1; i < lines.length; i++) out.push(<div key={`${id}-${i}`}>{lines[i]}</div>);
  };

  const emitSummary = () => {
    if (resume.summary) section("summary", "Professional Summary", [<p key="s" style={bodyJustify}>{rich(resume.summary)}</p>]);
  };

  const emitSkills = () => {
    if (resume.skills && Object.keys(resume.skills).length > 0) {
      section(
        "skills",
        "Technical Skills",
        Object.entries(resume.skills).map(([cat, items], i) => (
          <p key={i} style={{ ...bodyText, margin: "0 0 2px" }}>
            <span style={{ fontWeight: 700 }}>{cat}: </span>
            {/* render each skill individually so an added one can be highlighted */}
            {items.map((it, k) => (
              <Fragment key={k}>{k > 0 ? ", " : ""}{rich(it)}</Fragment>
            ))}
          </p>
        ))
      );
    }
  };

  const emitExperience = () => {
    if (resume.experience?.length > 0) {
      section("experience", "Professional Experience", entriesToLines(resume.experience.map((job) => ({
        head: (
          <p style={{ ...bodyText, display: "flex", justifyContent: "space-between", margin: "3px 0 0", gap: "8px" }}>
            <span style={{ fontWeight: 700 }}>
              {[job.title, job.company, job.location].filter(Boolean).join("  |  ")}
            </span>
            <span style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{[job.start_date, job.end_date].filter(Boolean).join(" – ")}</span>
          </p>
        ),
        bullets: job.bullets.map(rich),
      }))));
    }
  };

  const emitProjects = () => {
    if (resume.projects?.length > 0) {
      section("projects", "Projects", entriesToLines(resume.projects.map((p) => ({
        head: (
          <p style={{ ...bodyText, margin: "3px 0 0" }}>
            <span style={{ fontWeight: 700 }}>{p.name}</span>
            {p.tech_stack ? <span style={{ fontStyle: "italic" }}>{`  |  ${p.tech_stack}`}</span> : null}
          </p>
        ),
        bullets: p.bullets.map(rich),
      }))));
    }
  };

  const emitCertifications = () => {
    if (resume.certifications?.length > 0) {
      section("certifications", "Certifications", entriesToLines(resume.certifications.map((c) => ({
        head: (
          <p style={{ ...bodyText, display: "flex", justifyContent: "space-between", margin: "1px 0", gap: "8px" }}>
            <span>
              <span style={{ fontWeight: 700 }}>{c.name}</span>
              {c.issuer ? `  |  ${c.issuer}` : ""}
            </span>
            {c.date ? <span style={{ whiteSpace: "nowrap" }}>{c.date}</span> : null}
          </p>
        ),
        bullets: c.bullets.map(rich),
      }))));
    }
  };

  const emitEducation = () => {
    if (resume.education?.length > 0) {
      section("education", "Education", resume.education.map((e, i) => (
        <div key={i} style={{ marginBottom: "3px" }}>
          <p style={{ ...bodyText, display: "flex", justifyContent: "space-between", margin: "1px 0 0", gap: "8px" }}>
            <span style={{ fontWeight: 700 }}>{e.degree}</span>
            {e.graduation_date ? <span style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{e.graduation_date}</span> : null}
          </p>
          <p style={{ ...bodyText, margin: 0 }}>
            {[e.institution, e.location].filter(Boolean).join("  |  ")}
          </p>
          {showGpa && e.gpa ? <p style={{ ...bodyText, margin: 0 }}>{e.gpa}</p> : null}
          {e.details.filter((d) => showCoursework || !isCoursework(d)).map((d, j) => (
            <Bullet key={j}>{rich(d)}</Bullet>
          ))}
        </div>
      )));
    }
  };

  const emitAdditional = (i: number) => {
    const sec = (resume.additional_sections || [])[i];
    if (!sec) return;
    const lines: ReactNode[] = [];
    if (sec.text) lines.push(<p key="t" style={bodyJustify}>{rich(sec.text)}</p>);
    sec.items.forEach((it, j) => lines.push(<Bullet key={j}>{rich(it)}</Bullet>));
    section(`additional-${i}`, sec.heading, lines);
  };

  const emitters: Record<string, () => void> = {
    skills: emitSkills,
    experience: emitExperience,
    projects: emitProjects,
    certifications: emitCertifications,
    education: emitEducation,
  };

  // Summary is pinned at the top; everything below follows the chosen order.
  emitSummary();

  const bodyOrder = order && order.length
    ? order
    : ["skills", "experience", "projects", "certifications",
       ...(resume.additional_sections || []).map((_, i) => `additional-${i}`), "education"];

  for (const key of bodyOrder) {
    if (key.startsWith("additional-")) emitAdditional(parseInt(key.split("-")[1], 10));
    else emitters[key]?.();
  }

  return out;
}

// Each entry becomes lines: [head + first bullet] then remaining bullets — so an
// entry header is never stranded alone at the bottom of a page.
function entriesToLines(entries: { head: ReactNode; bullets: ReactNode[] }[]): ReactNode[] {
  const lines: ReactNode[] = [];
  entries.forEach((e, ei) => {
    if (e.bullets.length === 0) {
      lines.push(<div key={`e${ei}`} style={{ marginBottom: "4px" }}>{e.head}</div>);
    } else {
      lines.push(
        <div key={`e${ei}`}>
          {e.head}
          <Bullet>{e.bullets[0]}</Bullet>
        </div>
      );
      for (let b = 1; b < e.bullets.length; b++) lines.push(<Bullet key={`e${ei}b${b}`}>{e.bullets[b]}</Bullet>);
    }
  });
  return lines;
}

/* ── presentational ─────────────────────────────────────────────────────── */
function Identity({ resume }: { resume: Resume }) {
  return (
    <div style={{ fontFamily: doc.font, color: "#111" }}>
      <div style={{ textAlign: "center", fontSize: doc.nameSize, fontWeight: 700, color: doc.cobalt, textTransform: "uppercase", letterSpacing: "0.02em" }}>{resume.name}</div>
      {resume.headline && <div style={{ textAlign: "center", fontSize: doc.titleSize, color: doc.gray, marginTop: "2px" }}>{resume.headline}</div>}
      <ContactLine resume={resume} />
    </div>
  );
}
function SectionHeader({ title }: { title: string }) {
  return (
    <div style={{ marginTop: "8px", fontSize: doc.headerSize, fontWeight: 700, color: doc.cobalt, textTransform: "uppercase", borderBottom: "1px solid #111", paddingBottom: "1px", marginBottom: "3px" }}>
      {title}
    </div>
  );
}
function ContactLine({ resume }: { resume: Resume }) {
  const c = resume.contact;
  const segs: { text: string; href?: string }[] = [];
  if (c.phone) segs.push({ text: c.phone });
  if (c.email) {
    const addr = c.email.replace(/^mailto:/, "");
    segs.push({ text: c.email_label || addr, href: `mailto:${addr}` });
  }
  if (c.linkedin || c.linkedin_label) segs.push({ text: c.linkedin_label || "LinkedIn", href: c.linkedin ? ensureUrl(c.linkedin) : undefined });
  if (c.github || c.github_label) segs.push({ text: c.github_label || "GitHub", href: c.github ? ensureUrl(c.github) : undefined });
  (c.links || []).forEach((l) => l.url && segs.push({ text: l.label || l.url, href: ensureUrl(l.url) }));
  if (c.location) segs.push({ text: c.location });
  return (
    <div style={{ textAlign: "center", fontFamily: doc.font, fontSize: doc.bodySize, color: "#111", margin: "3px 0 0" }}>
      {segs.map((s, i) => (
        <span key={i}>
          {i > 0 ? "  |  " : ""}
          {s.href ? <a href={s.href} target="_blank" rel="noreferrer" style={{ color: doc.cobalt, textDecoration: "none" }}>{s.text}</a> : s.text}
        </span>
      ))}
    </div>
  );
}
function ensureUrl(u: string): string {
  const s = (u || "").trim();
  if (/^(https?:\/\/|mailto:)/i.test(s)) return s;
  return "https://" + s.replace(/^\/+/, "");
}
function Bullet({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", gap: "7px", ...bodyText, margin: "0 0 2px" }}>
      <span style={{ flexShrink: 0 }}>•</span>
      <span style={{ textAlign: "justify" }}>{children}</span>
    </div>
  );
}

const bodyText: CSSProperties = { fontFamily: doc.font, fontSize: doc.bodySize, lineHeight: 1.4, color: "#111" };
const bodyJustify: CSSProperties = { ...bodyText, textAlign: "justify", margin: "0 0 2px" };
const pageStyle: CSSProperties = {
  width: `${PAGE_W}px`,
  height: `${PAGE_H}px`,
  background: "#fff",
  boxShadow: "rgba(20,20,19,0.13) 0px 6px 30px, rgba(20,20,19,0.06) 0px 1px 4px",
  borderRadius: "2px",
  padding: `${PAD}px`,
  position: "relative",
  flexShrink: 0,
  overflow: "hidden",
};
const pageNum: CSSProperties = { position: "absolute", bottom: "8px", right: "12px", fontFamily: tk.sans, fontSize: "10px", color: tk.onSurfaceGhost };
