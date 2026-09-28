export function Wordmark() {
  return (
    <span className="relative inline-flex shrink-0 flex-col items-center px-5 py-2 leading-none select-none">
      <svg
        aria-hidden
        className="absolute inset-0 h-full w-full text-sage"
        viewBox="0 0 100 44"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M14 1 H1 V43 H14 M86 1 H99 V43 H86"
          stroke="currentColor"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span className="text-[1.375rem] font-semibold text-sage" lang="ar" dir="rtl">
        بيان
      </span>
      <span className="mt-1 text-[1rem] font-semibold tracking-[0.18em] text-ink">
        BAYAN
      </span>
    </span>
  );
}
