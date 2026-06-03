/* The structured resume contract (mirrors the backend schema) plus the
   review-state model and pure helpers shared by the review components. */

export interface ResumeLink {
  label: string;
  url: string;
}
export interface Contact {
  phone: string | null;
  email: string | null;
  linkedin: string | null;
  github: string | null;
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

/* The resume to actually build: skipped sections removed, GPA stripped when the
   user hid it. Name/headline/contact always survive. Pure (deep-clones input). */
export function buildPayload(resume: Resume, status: StatusMap, showGpa: boolean): Resume {
  const r: Resume = JSON.parse(JSON.stringify(resume));
  const skipped = (id: string) => status[id] === "skipped";

  if (skipped("summary")) r.summary = null;
  if (skipped("skills")) r.skills = {};
  if (skipped("experience")) r.experience = [];
  if (skipped("projects")) r.projects = [];
  if (skipped("certifications")) r.certifications = [];
  if (skipped("education")) r.education = [];
  r.additional_sections = (r.additional_sections || []).filter((_, i) => !skipped(`additional-${i}`));

  if (!showGpa) r.education = r.education.map((e) => ({ ...e, gpa: null }));
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
