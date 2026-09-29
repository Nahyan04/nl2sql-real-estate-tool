"""Verified plans for narrowly scoped source sales questions."""

import re
from decimal import Decimal

from app.core.language import Language

_DISTRICT = re.compile(r"(?:\b(?:district|area)\s+(?:of\s+)?Al[ -]?Bateen\b|\bAl[ -]?Bateen\s+(?:source\s+)?(?:district|area)\b|(?:منطق[هة]|حي)\s+البطين)", re.IGNORECASE)
_SALES = re.compile(r"\bsales?\b|مبيعات|بيع", re.IGNORECASE)
_VALUE = re.compile(r"\b(?:value|worth)\b|قيم[هة]", re.IGNORECASE)
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_COMPARISON = re.compile(r"\b(?:compare|versus|vs|by sale type|off-plan|ready)\b|قارن|مقارن[هة]|على حسب نوع البيع", re.IGNORECASE)
_EXTRA_SCOPE = re.compile(r"\b(?:residential|commercial|apartments?|villas?|studios?|off-plan|ready|share|project|community|Abu Dhabi City|Al Ain City|Al Dhafra)\b|سكني|سكنية|تجاري|شقق|فلل|حصة|مشروع|مدينة أبوظبي|مدينة العين|الظفرة", re.IGNORECASE)


def sales_analysis_plan(question: str) -> tuple[str, str] | None:
    district = sales_district_value_plan(question)
    if district:
        return district[0], "district_value"
    years = _YEAR.findall(question)
    if len(years) != 1 or not _SALES.search(question):
        return None
    year = int(years[0])
    period = (f"transaction_date >= DATE '{year}-01-01' "
              f"AND transaction_date < DATE '{year + 1}-01-01'")
    plain = question.strip().rstrip("?؟. ")
    if re.fullmatch(r"which (?:five|5) source districts had the highest (?:exported )?sales value in (?:19|20)\d{2}|"
                    r"ما المناطق المصدرية الخمس الأعلى من حيث قيمة المبيعات الواردة في بيانات عام (?:19|20)\d{2}", plain, re.IGNORECASE):
        return ("SELECT district, SUM(price_aed) AS sales_value_aed "
                f"FROM transactions WHERE {period} GROUP BY district "
                "ORDER BY sales_value_aed DESC, district ASC LIMIT 5", "top_districts")
    all_three = bool(re.fullmatch(r"compare off-plan, ready and court-mandated sales value in (?:19|20)\d{2}", plain, re.IGNORECASE))
    if (all_three or re.fullmatch(r"compare exported sales value by source sale type in (?:19|20)\d{2}", plain, re.IGNORECASE)):
        sale_filter = "sale_type IN ('off-plan', 'ready', 'court-mandated') AND " if all_three else ""
        return ("SELECT sale_type, SUM(price_aed) AS sales_value_aed "
                f"FROM transactions WHERE {sale_filter}{period} GROUP BY sale_type "
                "ORDER BY sales_value_aed DESC", "sale_type_value")
    if re.fullmatch(r"قارن عدد سجلات البيع على الخارطة والجاهز في عام (?:19|20)\d{2}", plain):
        return ("SELECT sale_type, COUNT(*) AS sales_observation_count "
                "FROM transactions WHERE sale_type IN ('off-plan', 'ready') "
                f"AND {period} GROUP BY sale_type "
                "ORDER BY sales_observation_count DESC", "sale_type_count")
    if re.fullmatch(r"how many (?:exported )?sales observations(?: are in the export)? (?:for|in) (?:19|20)\d{2}|"
                    r"كم عدد سجلات المبيعات الواردة في البيانات لعام (?:19|20)\d{2}", plain, re.IGNORECASE):
        return ("SELECT COUNT(*) AS sales_observation_count "
                f"FROM transactions WHERE {period}", "year_count")
    if re.fullmatch(r"what was the (?:total )?(?:exported )?sales value(?: in aed)? in (?:19|20)\d{2}|"
                    r"ما قيمة المبيعات لعام (?:19|20)\d{2}", plain, re.IGNORECASE):
        return ("SELECT SUM(price_aed) AS sales_value_aed "
                f"FROM transactions WHERE {period}", "year_value")
    return None


def sales_district_value_plan(question: str) -> tuple[str, str] | None:
    years = _YEAR.findall(question)
    if not (_DISTRICT.search(question) and _SALES.search(question) and _VALUE.search(question)
            and len(years) == 1 and not _COMPARISON.search(question)
            and not _EXTRA_SCOPE.search(question)):
        return None
    year = int(years[0])
    sql = (
        "SELECT SUM(price_aed) AS sales_value_aed, COUNT(*) AS sales_observation_count "
        "FROM transactions WHERE district = 'Al Bateen' "
        f"AND transaction_date >= DATE '{year}-01-01' "
        f"AND transaction_date < DATE '{year + 1}-01-01'"
    )
    return sql, years[0]


def render_sales_district_value(rows: list[list[object]], year: str, language: Language) -> str:
    value, count = rows[0]
    amount = f"{Decimal(str(value)):,.2f}"
    if language == "ar":
        return (f"بلغت قيمة سجلات المبيعات المصدّرة في منطقة البطين (Al Bateen) عام {year} "
                f"{amount} درهم، عبر {count:,} سجل. لا يحدد مصدر المبيعات البلدية لهذه السجلات.")
    return (f"Exported sales observations in the Al Bateen source district totaled AED {amount} "
            f"across {count:,} records in {year}. The sales source does not identify their municipality.")


def render_sales_analysis(question: str, kind: str, rows: list[list[object]], language: Language) -> str:
    if kind == "district_value":
        return render_sales_district_value(rows, _YEAR.search(question).group(), language)
    year = _YEAR.search(question).group()
    if kind == "year_count":
        count = rows[0][0]
        if language == "ar":
            return f"تتضمن بيانات المصدر {count:,} سجل مبيعات مُصدّر في عام {year}."
        return f"The source export contains {count:,} sales observations in {year}."
    if kind == "year_value":
        from app.services.answer_synthesizer import _format_aed
        amount = _format_aed(rows[0][0], language == "ar")
        if language == "ar":
            return f"بلغت قيمة سجلات المبيعات المصدّرة في عام {year} {amount}."
        return f"Exported sales observations in {year} totaled {amount}."
    if kind == "top_districts":
        from app.services.answer_synthesizer import _format_aed
        entries = ", ".join(f"{district}: {_format_aed(value, language == 'ar')}" for district, value in rows)
        if language == "ar":
            return f"المناطق المصدرية الخمس الأعلى بقيمة المبيعات المصدّرة في {year}: {entries}."
        return f"The five source districts with the highest exported sales value in {year} were {entries}."
    if kind == "sale_type_value":
        from app.services.answer_synthesizer import _format_aed
        entries = ", ".join(f"{_sale_type_label(sale_type, language)}: {_format_aed(value, language == 'ar')}" for sale_type, value in rows)
        if language == "ar":
            return f"قيمة سجلات البيع المصدّرة حسب نوع البيع في {year}: {entries}."
        return f"Exported sales value by source sale type in {year}: {entries}."
    entries = ", ".join(f"{_sale_type_label(sale_type, language)}: {count:,}" for sale_type, count in rows)
    if language == "ar":
        return f"عدد سجلات البيع المصدّرة حسب نوع البيع في {year}: {entries}."
    return f"Exported sales observation counts by source sale type in {year}: {entries}."


def _sale_type_label(value: str, language: Language) -> str:
    if language == "ar":
        return {"off-plan": "على الخارطة (off-plan)", "ready": "جاهز (ready)",
                "court-mandated": "بحكم قضائي (court-mandated)"}.get(value, value)
    return value
