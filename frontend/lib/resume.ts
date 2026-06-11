/* The structured resume contract (mirrors the backend schema) plus the
   review-state model and pure helpers shared by the review components. */

export interface ResumeLink {
  label: string;
  url: string;
}
export interface Contact {
  phone: string | null;
  email: string | null;
  /* Optional custom display text for the named links. The URL/handle lives in
     email/linkedin/github; the *_label is what's shown (defaults: the address,
     "LinkedIn", "GitHub"). Lets the user edit display text and link separately. */
  email_label?: string | null;
  linkedin: string | null;
  linkedin_label?: string | null;
  github: string | null;
  github_label?: string | null;
  location: string | null;
  links: ResumeLink[];
}
export interface Experience {
  title: string;
  company: string;
  location: string | null;
  start_date: string;
  end_date: string;
  bullets: string[];
}
export interface Project {
  name: string;
  tech_stack: string | null;
  bullets: string[];
  /* AI Tailor only: the full ranked set of authored bullets (up to 6). `bullets`
     starts equal to this; the page-fill engine shows the top 2-6 to fit the page. */
  candidate_bullets?: string[];
}
export interface Education {
  degree: string;
  institution: string;
  location: string | null;
  graduation_date: string | null;
  gpa: string | null;
  details: string[];
}
export interface Certification {
  name: string;
  issuer: string | null;
  date: string | null;
  bullets: string[];
}
export interface AdditionalSection {
  heading: string;
  style: string;
  items: string[];
  text: string | null;
}
export interface Resume {
  name: string;
  headline: string | null;
  contact: Contact;
  summary: string | null;
  skills: Record<string, string[]>;
  experience: Experience[];
  projects: Project[];
  education: Education[];
  certifications: Certification[];
  additional_sections: AdditionalSection[];
  /* Optional render order for the body sections after the summary. Set by the
     build payload so the DOCX matches the drag-and-drop order on screen. */
  section_order?: string[];
}

export type SectionStatus = "pending" | "kept" | "skipped";
export type StatusMap = Record<string, SectionStatus>;

export interface SectionMeta {
  id: string;
  label: string;
}

/* Body sections that get a review card + preview block, IN THE ORDER the DOCX
   renders them (education last, like compact_ats.py). Only present sections
   appear. Name / headline / contact are always kept and aren't cards. */
export function getSections(resume: Resume): SectionMeta[] {
  const out: SectionMeta[] = [];
  if (resume.summary) out.push({ id: "summary", label: "Professional Summary" });
  if (resume.skills && Object.keys(resume.skills).length) out.push({ id: "skills", label: "Technical Skills" });
  if (resume.experience?.length) out.push({ id: "experience", label: "Professional Experience" });
  if (resume.projects?.length) out.push({ id: "projects", label: "Projects" });
  if (resume.certifications?.length) out.push({ id: "certifications", label: "Certifications" });
  (resume.additional_sections || []).forEach((sec, i) =>
    out.push({ id: `additional-${i}`, label: titleCaseHeading(sec.heading) })
  );
  if (resume.education?.length) out.push({ id: "education", label: "Education" });
  return out;
}

export function reviewedCount(sections: SectionMeta[], status: StatusMap): number {
  return sections.filter((s) => status[s.id] && status[s.id] !== "pending").length;
}

export function allReviewed(sections: SectionMeta[], status: StatusMap): boolean {
  return sections.length > 0 && sections.every((s) => status[s.id] && status[s.id] !== "pending");
}

/* The body section ids that can be reordered (everything after the summary),
   in the default render order — only those present in this resume. */
export function bodySectionIds(resume: Resume): string[] {
  return getSections(resume).filter((s) => s.id !== "summary").map((s) => s.id);
}

/* The resume to actually build: skipped sections removed, GPA stripped when the
   user hid it, body sections ordered per `sectionOrder`. Name/headline/contact
   always survive. Pure (deep-clones input). */
/* Education coursework details are tagged "Relevant Coursework: …". */
export const isCoursework = (d: string) => /^\s*(relevant\s+)?coursework\b/i.test(d || "");

export function buildPayload(resume: Resume, status: StatusMap, showGpa: boolean, sectionOrder?: string[], showCoursework = false): Resume {
  const r: Resume = JSON.parse(JSON.stringify(resume));
  const skipped = (id: string) => status[id] === "skipped";

  if (skipped("summary")) r.summary = null;
  if (skipped("skills")) r.skills = {};
  if (skipped("experience")) r.experience = [];
  if (skipped("projects")) r.projects = [];
  if (skipped("certifications")) r.certifications = [];
  if (skipped("education")) r.education = [];

  // Drop skipped additional sections, remembering how each original index maps
  // to its new (compacted) index so section_order keys stay valid.
  const addlMap = new Map<number, number>();
  const keptAddl: AdditionalSection[] = [];
  (r.additional_sections || []).forEach((sec, i) => {
    if (!skipped(`additional-${i}`)) {
      addlMap.set(i, keptAddl.length);
      keptAddl.push(sec);
    }
  });
  r.additional_sections = keptAddl;

  if (!showGpa) r.education = r.education.map((e) => ({ ...e, gpa: null }));
  if (!showCoursework) r.education = r.education.map((e) => ({ ...e, details: e.details.filter((d) => !isCoursework(d)) }));

  if (sectionOrder && sectionOrder.length) {
    const remapped: string[] = [];
    for (const key of sectionOrder) {
      if (key.startsWith("additional-")) {
        const orig = parseInt(key.split("-")[1], 10);
        if (addlMap.has(orig)) remapped.push(`additional-${addlMap.get(orig)}`);
      } else {
        remapped.push(key);
      }
    }
    r.section_order = remapped;
  }
  return r;
}

/* "PROFESSIONAL SUMMARY" -> "Professional Summary" for nicer card labels,
   while leaving acronym-ish all-caps short headings (e.g. "AWS") alone-ish. */
export function titleCaseHeading(s: string): string {
  return (s || "")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim() || "Section";
}
