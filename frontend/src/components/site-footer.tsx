export function SiteFooter({ arabic }: { arabic: boolean }) {
  return <footer dir={arabic ? "rtl" : "ltr"} className="mt-auto border-t border-rule">
    <div className="mx-auto max-w-[88rem] px-5 py-6 sm:px-8 lg:px-12">
      <p className="max-w-[65ch] text-sm leading-relaxed text-sand">{arabic ? "نسخة بيانات مصدّرة من ADREC. نموذج مستقل؛ ليس خدمة رسمية من ADREC." : "Source-backed ADREC export snapshot. Independent prototype; not an official ADREC service."}</p>
    </div>
  </footer>;
}
