import { AnalystWorkspace } from "@/components/analyst-workspace";

export default async function Home({ searchParams }: { searchParams: Promise<{ question?: string; lang?: string }> }) {
  const params = await searchParams;
  return <AnalystWorkspace initialQuestion={(params.question ?? "").slice(0, 1000)} initialLanguage={params.lang === "ar" ? "ar" : "auto"} />;
}
