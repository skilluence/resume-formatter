"use client";

import { type CSSProperties, type ReactNode } from "react";
import { Phone, Mail, MapPin } from "lucide-react";

/* lucide dropped brand icons, so the LinkedIn mark is a small inline SVG
   (currentColor inherits the cobalt accent from its wrapper). */
function LinkedinMark({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z" />
    </svg>
  );
}
import { doc } from "@/lib/tokens";
import { renderRich } from "@/lib/rich";
import type { Resume } from "@/lib/resume";
import type { TailorDrafts } from "@/lib/tailor";

/* Live preview of the cobalt cover-letter template — mirrors formatters/letter.py:
   left bold name, cobalt role line, a 2-column icon contact block, a "COVER LETTER"
   heading with a cobalt rule, then the body. What you see is what downloads. */

interface Props {
  name: string;
  headline: string | null;
  contact: Resume["contact"];
  letter: TailorDrafts["cover_letter"];
}

function ensureUrl(u: string): string {
  const s = (u || "").trim();
  if (/^(https?:\/\/|mailto:)/i.test(s)) return s;
  return "https://" + s.replace(/^\/+/, "");
}

type Item = { icon: ReactNode; text: string; href?: string };

export default function LetterPreview({ name, headline, contact, letter }: Props) {
  const c = contact;
  const items: Item[] = [];
  if (c.phone) items.push({ icon: <Phone size={13} />, text: c.phone });
  if (c.email) {
    const addr = c.email.replace(/^mailto:/, "");
    items.push({ icon: <Mail size={13} />, text: c.email_label || addr, href: `mailto:${addr}` });
  }
  if (c.linkedin || c.linkedin_label) {
    items.push({ icon: <LinkedinMark size={13} />, text: c.linkedin_label || "LinkedIn", href: c.linkedin ? ensureUrl(c.linkedin) : undefined });
  }
  if (c.location) items.push({ icon: <MapPin size={13} />, text: c.location });

  const paras = (letter.body_paragraphs || []).filter((p) => p.trim());

  return (
    <div style={wrap}>
      <div style={sheet}>
        <div style={nameStyle}>{name || "Your Name"}</div>
        {headline && <div style={roleStyle}>{headline}</div>}

        {items.length > 0 && (
          <div style={grid}>
            {items.map((it, i) => (
              <div key={i} style={cell}>
                <span style={iconWrap}>{it.icon}</span>
                {it.href ? (
                  <a href={it.href} target="_blank" rel="noreferrer" style={link}>{it.text}</a>
                ) : (
                  <span>{it.text}</span>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={heading}>COVER LETTER</div>

        {letter.greeting && <p style={bodyP}>{renderRich(letter.greeting)}</p>}
        {paras.map((p, i) => (
          <p key={i} style={bodyP}>{renderRich(p)}</p>
        ))}
        {letter.closing && <p style={{ ...bodyP, marginBottom: "3px" }}>{renderRich(letter.closing)}</p>}
        {letter.signature && <p style={sig}>{letter.signature}</p>}
      </div>
    </div>
  );
}

const wrap: CSSProperties = { width: "100%", display: "flex", justifyContent: "center" };
const sheet: CSSProperties = {
  width: "100%",
  maxWidth: "820px",
  background: "#fff",
  borderRadius: "3px",
  boxShadow: "rgba(20,20,19,0.13) 0px 6px 30px, rgba(20,20,19,0.06) 0px 1px 4px",
  padding: "clamp(28px, 6%, 64px)",
  fontFamily: doc.font,
  color: "#111",
  boxSizing: "border-box",
};
const nameStyle: CSSProperties = { fontSize: "22px", fontWeight: 700, color: "#222", letterSpacing: "0.01em" };
const roleStyle: CSSProperties = { fontSize: "13px", color: doc.cobalt, marginTop: "3px", fontWeight: 500 };
const grid: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "5px 28px",
  margin: "14px 0 4px",
};
const cell: CSSProperties = { display: "flex", alignItems: "center", gap: "7px", fontSize: "12px", color: "#333", minWidth: 0 };
const iconWrap: CSSProperties = { color: doc.cobalt, display: "inline-flex", flexShrink: 0 };
const link: CSSProperties = { color: doc.cobalt, textDecoration: "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };
const heading: CSSProperties = {
  fontSize: "13px",
  fontWeight: 700,
  color: doc.cobalt,
  letterSpacing: "0.04em",
  borderBottom: `2px solid ${doc.cobalt}`,
  paddingBottom: "4px",
  margin: "16px 0 12px",
};
const bodyP: CSSProperties = { fontSize: "12.5px", lineHeight: 1.55, color: "#111", textAlign: "justify", margin: "0 0 9px" };
const sig: CSSProperties = { fontSize: "12.5px", fontWeight: 700, color: "#111", margin: "2px 0 0" };
