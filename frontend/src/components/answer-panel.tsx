import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** The synthesizer answers in markdown and bolds the figure it was asked for. */
const MARKDOWN = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mt-4 first:mt-0">{children}</p>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-medium text-sage">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => <em className="italic">{children}</em>,
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="mt-4 space-y-1.5 ps-5 marker:text-sage-dim">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="mt-4 list-decimal space-y-1.5 ps-5 marker:text-sage-dim">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="list-disc">{children}</li>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code className="font-mono text-[0.9em] text-sand">{children}</code>
  ),
};

export function AnswerPanel({ answer }: { answer: string }) {
  if (!answer) return null;

  return (
    <section className="mt-12">
      <h2 className="label-mono">Answer</h2>
      {/* an Arabic answer reads from the column's right edge, not from a
          left-anchored measure */}
      <div
        dir="auto"
        className="mt-4 max-w-[44rem] text-[1.1875rem] leading-[1.6] font-medium text-ink [&:dir(rtl)]:ml-auto"
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN}>
          {answer}
        </ReactMarkdown>
      </div>
    </section>
  );
}
