import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** The synthesizer answers in markdown and bolds the figure it was asked for. */
const MARKDOWN = {
  h1: ({ children }: { children?: React.ReactNode }) => <h3 className="mt-5 text-lg font-semibold">{children}</h3>,
  h2: ({ children }: { children?: React.ReactNode }) => <h3 className="mt-5 text-lg font-semibold">{children}</h3>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 className="mt-5 text-base font-semibold">{children}</h3>,
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mt-6 first:mt-0">{children}</p>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-sage">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => <em className="italic">{children}</em>,
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="mt-5 list-disc space-y-3 ps-5 marker:text-sage-dim">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="mt-4 list-decimal space-y-1.5 ps-5 marker:text-sage-dim">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li>{children}</li>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="font-mono text-sm text-sand">{children}</code>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <div className="my-6 max-w-full overflow-x-auto rounded-lg border border-rule" tabIndex={0} role="region" aria-label="Answer table">
      <table className="w-full border-collapse text-base leading-relaxed">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: React.ReactNode }) => <thead className="bg-paper-flat">{children}</thead>,
  tr: ({ children }: { children?: React.ReactNode }) => <tr className="border-b border-rule last:border-b-0">{children}</tr>,
  th: ({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) => (
    <th scope="col" style={style} className="min-w-[8rem] px-5 py-3 text-start align-top font-semibold">{children}</th>
  ),
  td: ({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) => (
    <td style={style} className="min-w-[8rem] px-5 py-3 text-start align-top tabular-nums">{children}</td>
  ),
};

export function AnswerPanel({ answer, title = "Answer", arabic = false }: { answer: string; title?: string; arabic?: boolean }) {
  if (!answer) return null;

  return (
    <section dir={arabic ? "rtl" : "ltr"}>
      <h2 className="section-heading">{title}</h2>
      {/* an Arabic answer reads from the column's right edge, not from a
          left-anchored measure */}
      <div
        className="answer-copy mt-5 max-w-[65ch] text-lg leading-[1.75] text-ink"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN}>
          {answer}
        </ReactMarkdown>
      </div>
    </section>
  );
}
