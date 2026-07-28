import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

// Arabic answers stay in the same voice as the interface instead of falling
// through to a system face.
const plexArabic = IBM_Plex_Sans_Arabic({
  variable: "--font-plex-arabic",
  subsets: ["arabic"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Bayan — Abu Dhabi real estate analytics",
  description:
    "Ask Abu Dhabi's property market a question in English or Arabic and get an answer, the SQL behind it, and a chart.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexArabic.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <footer className="border-t border-rule">
          <div className="mx-auto flex max-w-[68rem] flex-wrap items-baseline justify-between gap-x-8 gap-y-2 px-5 sm:px-8 py-6">
            <p className="text-[0.9375rem] text-sand">
              Synthetic demonstration data, calibrated to published ADREC aggregates. Not an
              official ADREC service.
            </p>
            <p className="label-mono text-sand">Presight Innovation Challenge</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
