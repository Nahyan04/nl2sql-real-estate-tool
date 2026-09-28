"""A narrow source-backed plan for a verified bilingual district question."""

import re
from decimal import Decimal

from app.core.language import Language

_DISTRICT = re.compile(r"(?:\b(?:district|area)\s+(?:of\s+)?Al[ -]?Bateen\b|\bAl[ -]?Bateen\s+(?:district|area)\b|(?:منطق[هة]|حي)\s+البطين)", re.IGNORECASE)
_SALES = re.compile(r"\bsales?\b|مبيعات|بيع", re.IGNORECASE)
_VALUE = re.compile(r"\b(?:value|worth)\b|قيم[هة]", re.IGNORECASE)
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_COMPARISON = re.compile(r"\b(?:compare|versus|vs|by sale type|off-plan|ready)\b|قارن|مقارن[هة]|على حسب نوع البيع", re.IGNORECASE)


def sales_district_value_plan(question: str) -> tuple[str, str] | None:
    years = _YEAR.findall(question)
    if not (_DISTRICT.search(question) and _SALES.search(question) and _VALUE.search(question)
            and len(years) == 1 and not _COMPARISON.search(question)):
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
