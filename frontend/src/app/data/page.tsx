import type { Metadata } from "next";
import { DataGuide } from "@/components/data-guide";

export const metadata: Metadata = {
  title: "Explore the data — Bayan",
  description: "Explore the sales, residential leasing, and price-index data available in Bayan's ADREC export snapshot.",
};

export default async function DataPage({ searchParams }: { searchParams: Promise<{ lang?: string }> }) {
  const params = await searchParams;
  return <DataGuide initialArabic={params.lang === "ar"} />;
}
