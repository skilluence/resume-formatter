"use client";

import Link from "next/link";
import { CSSProperties } from "react";
import { tk } from "@/lib/tokens";

/* ════════════════════════════════════════════════════════════════════════
   Landing — a simple home page that explains what the tool does and how to
   use it, with a clear path into the formatter at /format.
═══════════════════════════════════════════════════════════════════════ */
export default function Landing() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: tk.surface, fontFamily: tk.sans }}>
      {/* ─── header ─── */}
      <header style={headerStyle}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: "10px", textDecoration: "none" }}>
          <Asterisk />
          <span style={{ fontFamily: tk.serif, fontSize: "17px", fontWeight: 500, color: tk.onSurface, letterSpacing: "-0.01em" }}>Resume Formatter</span>
        </Link>
        <nav style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "clamp(12px,3vw,20px)" }}>
          <a href="#how" style={navLink} className="lp-hide-sm">How it works</a>
          <Link href="/tailor" style={navLink} className="lp-hide-xs">Tailor to a job <sup style={{ fontSize: "9px", color: tk.clay, fontWeight: 700 }}>BETA</sup></Link>
          <Link href="/format" style={ctaSmall}>Format a resume →</Link>
        </nav>
      </header>

      <main style={{ flex: 1 }}>
        {/* ─── hero ─── */}
        <section style={{ padding: "clamp(56px,9vw,110px) 24px clamp(40px,5vw,64px)", textAlign: "center" }}>
          <div style={{ maxWidth: "720px", margin: "0 auto" }}>
            <span style={eyebrow}>Rule-based · No AI · Nothing lost</span>
            <h1 style={{ fontFamily: tk.serif, fontSize: "clamp(34px,6vw,60px)", fontWeight: 500, color: tk.onSurface, lineHeight: 1.08, letterSpacing: "-0.02em", margin: "16px 0 18px" }}>
              Format any resume,<br />
              <span style={{ color: tk.clay }}>keep every word</span>
            </h1>
            <p style={{ fontFamily: tk.sans, fontSize: "clamp(16px,2.2vw,19px)", color: tk.onSurfaceTertiary, lineHeight: 1.6, maxWidth: "560px", margin: "0 auto 30px" }}>
              Upload a messy PDF or Word resume and get back a clean, ATS-ready document. You review it as a real
              page — keep, skip, or edit each section — before you download. Nothing is invented, nothing is dropped.
            </p>
            <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
              <Link href="/format" style={ctaBig}>Format your resume →</Link>
              <a href="#how" style={ctaGhost}>See how it works</a>
            </div>
            <p style={{ fontFamily: tk.sans, fontSize: "12.5px", color: tk.onSurfaceGhost, marginTop: "16px" }}>PDF or DOCX · No sign-up · Your data stays on the page</p>
          </div>
        </section>

        {/* ─── how it works ─── */}
        <section id="how" style={{ background: tk.surfaceSecondary, borderTop: `1px solid ${tk.borderTertiary}`, borderBottom: `1px solid ${tk.borderTertiary}`, padding: "clamp(48px,7vw,84px) 24px" }}>
          <div style={{ maxWidth: "960px", margin: "0 auto" }}>
            <h2 style={sectionH2}>How it works</h2>
            <p style={sectionSub}>Three steps, about a minute.</p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "18px", marginTop: "36px" }}>
              <Step n="1" title="Upload" body="Drop in your resume as a PDF or Word file. The tool reads it with deterministic rules — no AI, so it can never make things up." icon={<UploadGlyph />} />
              <Step n="2" title="Review it live" body="Your resume appears as a real, multi-page document. Keep, skip, or edit any section right there, and toggle GPA on or off." icon={<EyeGlyph />} />
              <Step n="3" title="Download" body="Once every section is reviewed, download a clean DOCX or PDF — formatted consistently, with every word intact." icon={<DownloadGlyph />} />
            </div>
          </div>
        </section>

        {/* ─── why ─── */}
        <section style={{ padding: "clamp(48px,7vw,84px) 24px" }}>
          <div style={{ maxWidth: "960px", margin: "0 auto" }}>
            <h2 style={sectionH2}>Why it&rsquo;s different</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: "16px", marginTop: "32px" }}>
              <Feature title="Never loses a word" body="Every line, date, and bullet from your resume is preserved verbatim — tested across hundreds of real resumes." />
              <Feature title="No AI guesswork" body="Deterministic rules, not a language model. Same input, same clean output, every single time." />
              <Feature title="A real Word preview" body="See exactly what you&rsquo;ll get: a paginated A4 document you can edit before downloading." />
              <Feature title="You decide what shows" body="Keep or skip any section, and hide GPA/CGPA with one tap — your résumé, your call." />
            </div>
          </div>
        </section>

        {/* ─── final CTA ─── */}
        <section style={{ padding: "0 24px clamp(56px,8vw,90px)" }}>
          <div style={{ maxWidth: "720px", margin: "0 auto", background: tk.surfaceTertiary, borderRadius: "24px", padding: "clamp(32px,5vw,52px)", textAlign: "center" }}>
            <h2 style={{ fontFamily: tk.serif, fontSize: "clamp(22px,3vw,30px)", fontWeight: 500, color: tk.onSurface, margin: "0 0 10px", lineHeight: 1.2 }}>Ready to clean up your resume?</h2>
            <p style={{ fontFamily: tk.sans, fontSize: "15px", color: tk.onSurfaceTertiary, margin: "0 0 22px" }}>It takes about a minute, and you review everything before you download.</p>
            <Link href="/format" style={ctaBig}>Format your resume →</Link>
          </div>
        </section>
      </main>

      {/* ─── footer ─── */}
      <footer style={{ borderTop: `1px solid ${tk.borderTertiary}`, background: tk.surfaceSecondary, padding: "20px clamp(16px,4vw,40px)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", maxWidth: "1100px", margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Asterisk size={15} />
            <span style={{ fontFamily: tk.serif, fontSize: "13.5px", color: tk.onSurfaceSecondary }}>Resume Formatter</span>
          </div>
          <span style={{ fontFamily: tk.sans, fontSize: "12px", color: tk.onSurfaceTertiary }}>The cleanest way to format a resume — every word preserved.</span>
        </div>
      </footer>
    </div>
  );
}

/* ── pieces ─────────────────────────────────────────────────────────────── */
function Step({ n, title, body, icon }: { n: string; title: string; body: string; icon: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", border: `1px solid ${tk.borderTertiary}`, borderRadius: "16px", padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
        <span style={{ width: "30px", height: "30px", borderRadius: "8px", background: "color-mix(in srgb, #c96442 12%, white)", color: tk.clayInteractive, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>{icon}</span>
        <span style={{ fontFamily: tk.serif, fontSize: "11px", fontWeight: 600, color: tk.clay, letterSpacing: "0.1em" }}>STEP {n}</span>
      </div>
      <h3 style={{ fontFamily: tk.serif, fontSize: "19px", fontWeight: 500, color: tk.onSurface, margin: "0 0 6px" }}>{title}</h3>
      <p style={{ fontFamily: tk.sans, fontSize: "14px", color: tk.onSurfaceTertiary, lineHeight: 1.6, margin: 0 }}>{body}</p>
    </div>
  );
}
function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div style={{ padding: "20px", borderLeft: `2px solid ${tk.clay}`, background: tk.surfaceSecondary, borderRadius: "0 12px 12px 0" }}>
      <h3 style={{ fontFamily: tk.serif, fontSize: "16px", fontWeight: 500, color: tk.onSurface, margin: "0 0 6px" }}>{title}</h3>
      <p style={{ fontFamily: tk.sans, fontSize: "13.5px", color: tk.onSurfaceTertiary, lineHeight: 1.55, margin: 0 }}>{body}</p>
    </div>
  );
}

function Asterisk({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={tk.clay} strokeWidth="2" strokeLinecap="round" aria-hidden>
      <line x1="12" y1="2" x2="12" y2="22" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /><line x1="19.07" y1="4.93" x2="4.93" y2="19.07" />
    </svg>
  );
}
function UploadGlyph() {
  return <svg width={17} height={17} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>;
}
function EyeGlyph() {
  return <svg width={17} height={17} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>;
}
function DownloadGlyph() {
  return <svg width={17} height={17} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>;
}

/* ── styles ─────────────────────────────────────────────────────────────── */
const headerStyle: CSSProperties = {
  height: "62px",
  display: "flex",
  alignItems: "center",
  padding: "0 clamp(16px,4vw,40px)",
  borderBottom: `1px solid ${tk.borderTertiary}`,
  background: "color-mix(in srgb, #faf9f5 88%, transparent)",
  backdropFilter: "saturate(180%) blur(10px)",
  WebkitBackdropFilter: "saturate(180%) blur(10px)",
  position: "sticky",
  top: 0,
  zIndex: 40,
};
const navLink: CSSProperties = { fontFamily: tk.sans, fontSize: "13.5px", fontWeight: 500, color: tk.onSurfaceTertiary, textDecoration: "none" };
const eyebrow: CSSProperties = { fontFamily: tk.sans, fontSize: "11px", fontWeight: 600, letterSpacing: "0.14em", color: tk.clay, textTransform: "uppercase" };
const sectionH2: CSSProperties = { fontFamily: tk.serif, fontSize: "clamp(24px,3.4vw,34px)", fontWeight: 500, color: tk.onSurface, textAlign: "center", margin: 0, lineHeight: 1.15 };
const sectionSub: CSSProperties = { fontFamily: tk.sans, fontSize: "15px", color: tk.onSurfaceTertiary, textAlign: "center", margin: "8px 0 0" };
const ctaBig: CSSProperties = {
  display: "inline-block",
  fontFamily: tk.sans,
  fontSize: "15px",
  fontWeight: 600,
  color: "#faf9f5",
  background: tk.clayInteractive,
  border: `1px solid ${tk.clayInteractive}`,
  borderRadius: "11px",
  padding: "13px 22px",
  textDecoration: "none",
  boxShadow: "0 2px 12px color-mix(in srgb, #c96442 28%, transparent)",
};
const ctaGhost: CSSProperties = { display: "inline-block", fontFamily: tk.sans, fontSize: "15px", fontWeight: 500, color: tk.onSurfaceSecondary, background: "#fff", border: `1px solid ${tk.borderSecondary}`, borderRadius: "11px", padding: "13px 20px", textDecoration: "none" };
const ctaSmall: CSSProperties = { display: "inline-block", fontFamily: tk.sans, fontSize: "13px", fontWeight: 600, color: "#faf9f5", background: tk.clayInteractive, borderRadius: "8px", padding: "8px 14px", textDecoration: "none" };
