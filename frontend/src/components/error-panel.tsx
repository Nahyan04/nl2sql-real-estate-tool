import type { ApiError } from "@/lib/api";
import type { ApiErrorCode } from "@/lib/types";

const EXPLANATIONS: Record<ApiErrorCode, { title: string; guidance: string }> = {
  PARSE_ERROR: {
    title: "No query produced",
    guidance: "The model did not return usable SQL. Name the measure and the time range you want.",
  },
  EMPTY_RESPONSE: {
    title: "No query produced",
    guidance: "The model returned nothing. Ask again, or rephrase the question more directly.",
  },
  VALIDATION_ERROR: {
    title: "Query rejected",
    guidance: "The generated SQL did not parse. Try a narrower question over one subject.",
  },
  SCOPE_ERROR: {
    title: "Query scope incomplete",
    guidance: "The generated SQL omitted a filter from your question. Try stating the filters more directly.",
  },
  UNSAFE_SQL: {
    title: "Query rejected",
    guidance: "The generated SQL was not read-only, so it was never run. Rephrase as a question about the data.",
  },
  UNSUPPORTED: {
    title: "That calculation is not supported",
    guidance: "The verified exports do not support that question. Try a source-backed sales, rent, index, or indicative gross segment yield question.",
  },
  CLARIFICATION: {
    title: "Please clarify the question",
    guidance: "Give exact dates or a named reporting period, and specify any ambiguous source place name.",
  },
  EXECUTION_ERROR: {
    title: "Query failed to run",
    guidance: "The database rejected the query. A shorter time range or fewer joins usually fixes it.",
  },
  DATABASE_BUSY: {
    title: "Database is busy",
    guidance: "Too many queries are running. Try again in a moment or narrow the question.",
  },
  QUERY_TIMEOUT: {
    title: "Query took too long",
    guidance: "Use a shorter time range or a more specific subject so the database can finish the query.",
  },
  RESULT_TOO_LARGE: {
    title: "Result is too large",
    guidance: "Add a filter, time range, or grouping so the response contains less data.",
  },
  MODEL_BUSY: {
    title: "Model is busy",
    guidance: "The inference queue is full. Try again in a moment.",
  },
  SERVER_BUSY: {
    title: "Too many analyses at once",
    guidance: "The demo is busy. Wait a moment and try your question again.",
  },
  SESSION_RATE_LIMIT: {
    title: "Brief pause",
    guidance: "This browser has sent many questions in a short time. Try again after the pause.",
  },
  SESSION_DAILY_LIMIT: {
    title: "Browser allowance reached",
    guidance: "This browser has reached its daily demo allowance.",
  },
  IP_RATE_LIMIT: {
    title: "Brief pause",
    guidance: "Many questions are coming from this network. Try again after the pause.",
  },
  IP_DAILY_LIMIT: {
    title: "Network allowance reached",
    guidance: "This network has reached its daily demo allowance.",
  },
  LIMITER_UNAVAILABLE: {
    title: "Demo temporarily unavailable",
    guidance: "The request guard could not be checked. Try again shortly.",
  },
  REQUEST_TIMEOUT: {
    title: "Request timed out",
    guidance: "The full analysis exceeded its time limit. Try a narrower question.",
  },
  UNKNOWN_PROVIDER: {
    title: "Model not configured",
    guidance: "The server does not have that model option set up.",
  },
  PROVIDER_UNAVAILABLE: {
    title: "Model temporarily unavailable",
    guidance: "The selected provider could not complete the analysis. Keep your question and try again when that provider is online.",
  },
  LANGUAGE_MISMATCH: {
    title: "Answer language mismatch",
    guidance: "The model could not answer in the selected language. Try again.",
  },
  INVALID_REQUEST: {
    title: "Check your request",
    guidance: "Enter a question and choose one of the available providers.",
  },
  UPSTREAM_ERROR: {
    title: "Request failed upstream",
    guidance: "The model provider or the database did not respond. For Self-hosted, check that the configured Ollama server is running.",
  },
  NETWORK_ERROR: {
    title: "API unreachable",
    guidance: "Nothing answered at the API address. Check that the backend is running.",
  },
};

const ARABIC_EXPLANATIONS: Record<ApiErrorCode, { title: string; guidance: string }> = {
  PARSE_ERROR: { title: "تعذر إنشاء الاستعلام", guidance: "لم يُنتج النموذج استعلامًا صالحًا. حدد المقياس والفترة المطلوبة." },
  EMPTY_RESPONSE: { title: "تعذر إنشاء الاستعلام", guidance: "لم يُرجع النموذج استعلامًا. أعد صياغة السؤال." },
  VALIDATION_ERROR: { title: "رُفض الاستعلام", guidance: "تعذر التحقق من الاستعلام. جرّب سؤالًا أكثر تحديدًا." },
  SCOPE_ERROR: { title: "نطاق الاستعلام غير مكتمل", guidance: "لم يتضمن الاستعلام أحد شروط السؤال. حاول تحديد الشروط بوضوح أكبر." },
  UNSAFE_SQL: { title: "رُفض الاستعلام", guidance: "لم يجتز الاستعلام ضوابط القراءة فقط، لذلك لم يُنفذ." },
  UNSUPPORTED: { title: "هذا السؤال غير مدعوم", guidance: "البيانات الموثقة لا تدعم هذا السؤال. اسأل عن المبيعات أو الإيجارات أو المؤشرات أو العائد الإجمالي التقديري للمجموعة." },
  CLARIFICATION: { title: "يرجى توضيح السؤال", guidance: "حدد فترة صريحة. إذا كان اسم المكان ملتبسًا، حدد هل تقصد المنطقة أو المجتمع كما يرد في المصدر." },
  EXECUTION_ERROR: { title: "تعذر تنفيذ الاستعلام", guidance: "رفضت قاعدة البيانات الاستعلام. جرّب فترة أقصر أو نطاقًا أضيق." },
  DATABASE_BUSY: { title: "قاعدة البيانات مشغولة", guidance: "هناك استعلامات كثيرة قيد التنفيذ. حاول مرة أخرى بعد قليل." },
  QUERY_TIMEOUT: { title: "استغرق الاستعلام وقتًا طويلًا", guidance: "حدد فترة أقصر أو موضوعًا أدق." },
  RESULT_TOO_LARGE: { title: "النتيجة كبيرة جدًا", guidance: "أضف شرطًا أو تجميعًا لتقليل حجم النتيجة." },
  MODEL_BUSY: { title: "النموذج مشغول", guidance: "قائمة انتظار النموذج ممتلئة. حاول بعد قليل." },
  SERVER_BUSY: { title: "التحليلات مشغولة", guidance: "انتظر قليلًا ثم أعد المحاولة." },
  SESSION_RATE_LIMIT: { title: "توقف قصير", guidance: "أرسل هذا المتصفح أسئلة كثيرة خلال فترة قصيرة." },
  SESSION_DAILY_LIMIT: { title: "انتهى حد المتصفح اليومي", guidance: "بلغ هذا المتصفح حد الاستخدام اليومي للعرض." },
  IP_RATE_LIMIT: { title: "توقف قصير", guidance: "وردت أسئلة كثيرة من هذه الشبكة." },
  IP_DAILY_LIMIT: { title: "انتهى حد الشبكة اليومي", guidance: "بلغت هذه الشبكة حد الاستخدام اليومي للعرض." },
  LIMITER_UNAVAILABLE: { title: "الخدمة غير متاحة مؤقتًا", guidance: "تعذر التحقق من حد الطلبات. حاول بعد قليل." },
  REQUEST_TIMEOUT: { title: "انتهت مهلة التحليل", guidance: "استغرق التحليل وقتًا طويلًا. ضيّق نطاق السؤال." },
  UNKNOWN_PROVIDER: { title: "النموذج غير مهيأ", guidance: "خيار النموذج المحدد غير مهيأ على الخادم." },
  PROVIDER_UNAVAILABLE: { title: "النموذج غير متاح", guidance: "تعذر على مزود النموذج إكمال التحليل. حاول لاحقًا." },
  LANGUAGE_MISMATCH: { title: "تعذر الالتزام باللغة", guidance: "لم يتمكن النموذج من الإجابة باللغة المحددة. حاول مرة أخرى." },
  INVALID_REQUEST: { title: "تحقق من الطلب", guidance: "أدخل سؤالًا واختر نموذجًا متاحًا." },
  UPSTREAM_ERROR: { title: "فشل الطلب", guidance: "لم تستجب خدمة النموذج أو قاعدة البيانات." },
  NETWORK_ERROR: { title: "تعذر الاتصال بالخدمة", guidance: "تعذر الوصول إلى واجهة البرمجة. تحقق من تشغيل الخادم." },
};

export function ErrorPanel({ error, arabic, onRetry }: { error: ApiError; arabic: boolean; onRetry: () => void }) {
  const explanation = (arabic ? ARABIC_EXPLANATIONS : EXPLANATIONS)[error.code] ?? {
    title: "Request failed",
    guidance: "Something went wrong before an answer could be produced.",
  };

  return (
    <section dir={arabic ? "rtl" : "ltr"} className="mt-12 border-s-2 border-destructive ps-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="label-mono text-destructive">{explanation.title}</h2>
        <span className="label-mono text-sand">{error.code}</span>
      </div>
      <p className="mt-2 max-w-[44rem] text-[1.0625rem] leading-relaxed text-ink">
        {explanation.guidance}
        {error.retryAfter !== null ? (arabic ? ` حاول بعد ${error.retryAfter} ثانية.` : ` Retry after ${error.retryAfter} seconds.`) : ""}
      </p>
      {error.detail && !arabic ? (
        <p className="mt-3 max-w-[44rem] font-mono text-[0.9375rem] leading-relaxed break-words text-sand">
          {error.detail}
        </p>
      ) : null}
      {error.requestId ? <p className="mt-3 label-mono text-sand">{arabic ? "معرّف الطلب" : "Request ID"}: {error.requestId}</p> : null}
      <button type="button" onClick={onRetry} className="mt-5 cursor-pointer rounded-md border border-rule px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-sage hover:text-sage">
        {arabic ? "حاول مرة أخرى" : "Try again"}
      </button>
    </section>
  );
}
