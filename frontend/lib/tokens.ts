/* Shared design tokens (Claude-brand) + DOCX-mirror constants.
   The `doc` values mirror backend/formatters/compact_ats.py so the live preview
   looks like the downloaded .docx (Calibri, cobalt headers, 9pt body, A4). */

export const tk = {
  surface: "#faf9f5",
  surfaceSecondary: "#f5f4ed",
  surfaceTertiary: "#f0eee6",
  surfaceDark: "#1a1918",
  clay: "#d97757",
  clayInteractive: "#c96442",
  onSurface: "#141413",
  onSurfaceSecondary: "#30302e",
  onSurfaceTertiary: "#5e5d59",
  onSurfaceGhost: "#9c9a92",
  borderTertiary: "#e8e6dc",
  borderSecondary: "#d1cfc5",
  green: "#5a9a5f",
  greenInteractive: "#4a7a4e",
  greenSurface: "#f0f7f0",
  red: "#b53333",
  serif: "var(--font-lora, Georgia, serif)",
  sans: "var(--font-inter, Inter, system-ui, sans-serif)",
} as const;

/* Mirrors compact_ats.py: FONT_NAME=Calibri, COBALT_BLUE=#0047AB,
   HEADLINE_GRAY=#404040, NAME 16pt, TITLE 10.5pt, HEADER 9.5pt, BODY 9pt. */
export const doc = {
  font: "Calibri, 'Segoe UI', system-ui, sans-serif",
  cobalt: "#0047AB",
  gray: "#404040",
  nameSize: "16pt",
  titleSize: "10.5pt",
  headerSize: "9.5pt",
  bodySize: "9pt",
} as const;

/* The single "sheet of paper" definition — shared by the empty, skeleton and
   live-preview states so the document never visibly swaps between them. */
export const paper = {
  background: "#ffffff",
  width: "100%",
  maxWidth: "850px",
  margin: "0 auto",
  borderRadius: "4px",
  boxShadow: "rgba(20,20,19,0.10) 0px 10px 40px, rgba(20,20,19,0.04) 0px 2px 8px",
  padding: "44px 52px 56px",
} as const;
