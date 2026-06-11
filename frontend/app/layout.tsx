import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Lora, Inter } from "next/font/google";
import { cn } from "@/lib/utils";

const lora = Lora({
  subsets: ["latin"],
  variable: "--font-lora",
  weight: ["400", "500"],
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Resume Formatter",
  description: "Transform unformatted resumes into ATS-ready, recruiter-friendly documents",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Let users pinch-zoom the resume preview on small screens.
  maximumScale: 5,
  themeColor: "#faf9f5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn(lora.variable, inter.variable)}>
      <body className="min-h-screen" style={{ fontFamily: "var(--font-inter, Inter, system-ui, sans-serif)" }}>
        {children}
      </body>
    </html>
  );
}
