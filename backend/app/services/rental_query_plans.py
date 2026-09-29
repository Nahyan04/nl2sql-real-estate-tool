"""Verified query plans for explicit source-backed rental questions."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RentalPlan:
    kind: str
    sql: str


_QUARTER = re.compile(r"\bQ([1-4])\s*(20\d{2})\b", re.IGNORECASE)
_AR_QUARTER = re.compile(r"الربع\s+(الأول|الثاني|الثالث|الرابع)\s+(?:من\s+)?(20\d{2})")
_AR_TWO_QUARTERS = re.compile(r"(?:ال|لل)ربعين\s+(الأول|الثاني|الثالث|الرابع)\s+و(الأول|الثاني|الثالث|الرابع)\s+(?:من\s+)?(20\d{2})")
_AR_QUARTER_NUMBERS = {"الأول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4}
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
_MONTH_DATES = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b", re.IGNORECASE)


def _quarter_end(question: str) -> date | None:
    match = _QUARTER.search(question)
    if match:
        quarter, year = int(match[1]), int(match[2])
    else:
        match = _AR_QUARTER.search(question)
        if not match:
            return None
        quarter = _AR_QUARTER_NUMBERS[match[1]]
        year = int(match[2])
    month = quarter * 3
    return date(year, month, calendar.monthrange(year, month)[1])


def _lease_value_periods(question: str) -> list[date]:
    matches = [(int(quarter), int(year)) for quarter, year in _QUARTER.findall(question)]
    quarter_tokens = re.findall(r"\bQ([1-4])\b", question, re.IGNORECASE)
    years = re.findall(r"\b20\d{2}\b", question)
    if len(years) == 1 and 1 <= len(quarter_tokens) <= 2:
        matches = [(int(quarter), int(years[0])) for quarter in quarter_tokens]
    pair = _AR_TWO_QUARTERS.search(question)
    if pair:
        matches = [(_AR_QUARTER_NUMBERS[pair[1]], int(pair[3])),
                   (_AR_QUARTER_NUMBERS[pair[2]], int(pair[3]))]
    elif not matches:
        match = _AR_QUARTER.search(question)
        if match:
            matches = [(_AR_QUARTER_NUMBERS[match[1]], int(match[2]))]
    if not 1 <= len(matches) <= 2 or len(set(matches)) != len(matches):
        return []
    return [date(year, quarter * 3, calendar.monthrange(year, quarter * 3)[1])
            for quarter, year in matches]


def lease_period_scope(question: str, arabic: bool) -> str:
    periods = _lease_value_periods(question)
    if not periods:
        return "الفترة المطلوبة" if arabic else "the requested period"
    if arabic:
        names = {1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع"}
        parts = [f"الربع {names[period.month // 3]} من {period.year}" for period in periods]
        return " و".join(parts)
    return " and ".join(f"Q{period.month // 3} {period.year}" for period in periods)


def _lease_value_plan(question: str) -> RentalPlan | None:
    plain = question.strip().rstrip("?؟. ")
    english = re.fullmatch(
        r"what was the (?:sum of )?source-labelled residential lease value for "
        r"Q[1-4](?: and Q[1-4])? 20\d{2}(?:,? in AED)?", plain, re.IGNORECASE,
    )
    arabic = re.fullmatch(
        r"ما (?:مجموع )?قيمة الإيجارات السكنية الواردة في المصدر "
        r"للربعين (?:الأول|الثاني|الثالث|الرابع) "
        r"و(?:الأول|الثاني|الثالث|الرابع) من 20\d{2} بالدرهم", plain,
    )
    if not (english or arabic):
        return None
    periods = _lease_value_periods(question)
    if not periods:
        return None
    dates = ", ".join(f"DATE '{period}'" for period in periods)
    predicate = f"period_end = {dates}" if len(periods) == 1 else f"period_end IN ({dates})"
    return RentalPlan(
        "residential_lease_value",
        "SELECT SUM(active_value_aed) AS residential_lease_value_aed "
        "FROM rental_observations "
        "WHERE source_file = 'Residential Leases/lease_price_by_period.xlsx' "
        f"AND {predicate}",
    )


def _index_dates(question: str) -> list[date]:
    return [
        date(int(year), _MONTHS[month.lower()], calendar.monthrange(int(year), _MONTHS[month.lower()])[1])
        for month, year in _MONTH_DATES.findall(question)
    ]


def _requested_layout(question: str) -> str | None:
    lowered = question.lower()
    layout_match = re.search(
        r"\b(studio|[1-5]\+?\s*(?:beds?|bedrooms?)|"
        r"one[- ]bedroom|two[- ]bedroom|three[- ]bedroom|"
        r"four[- ]bedroom|five[- ]bedroom)\b",
        lowered,
    )
    if layout_match:
        requested = layout_match[1]
        if requested == "studio":
            return "studio"
        else:
            word_digits = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
            digit = word_digits.get(requested.split("-")[0].split(" ")[0])
            digit = digit or re.match(r"[1-5]\+?", requested)[0]
            return f"{digit} bed" if digit == "1" else f"{digit} beds"
    return None


def _reem_apartment_plan(question: str, period: date) -> RentalPlan | None:
    lowered = question.lower()
    if "al reem island" not in lowered or not re.search(r"\bapartments?\b|شقق|شقة", lowered):
        return None
    yield_question = bool(re.search(r"\byield\b|العائد", lowered))
    rent_question = bool(re.search(r"\b(?:weighted|annual rent)\b|مرجح|المتوسط السنوي", lowered))
    if not yield_question and not rent_question:
        return None
    layout = _requested_layout(question)
    if layout is None and re.search(r"\b(?:beds?|bedrooms?)\b", lowered):
        return None
    layout_filter = f" AND c.layout = '{layout}'" if layout else ""
    price_filter = " AND c.source_average_sale_price_aed > 0" if yield_question else ""
    selected_price = ", c.source_average_sale_price_aed" if yield_question else ""
    metric = (
        "100 * SUM((source_annual_rent / source_average_sale_price_aed) * unit_count) "
        "/ NULLIF(SUM(unit_count), 0) AS gross_segment_yield_pct"
        if yield_question else
        "SUM(source_annual_rent * unit_count) / NULLIF(SUM(unit_count), 0) AS weighted_annual_rent_aed"
    )
    sql = f"""WITH units AS (
        SELECT period_end, municipality, district, property_type, layout,
               SUM(source_leased_units) AS unit_count
        FROM rental_observations
        WHERE source_file = 'Residential Leases/lease_residential.xlsx'
          AND period_end = DATE '{period}' AND source_leased_units > 0
        GROUP BY period_end, municipality, district, property_type, layout
    ), matched AS (
        SELECT c.source_annual_rent{selected_price}, u.unit_count
        FROM rental_observations c JOIN units u
          ON c.period_end = u.period_end AND c.municipality = u.municipality
         AND c.district = u.district AND c.property_type = u.property_type
         AND c.layout = u.layout
        WHERE c.source_file = 'Price Indices/average_sale_rent_prices_by_product_area.xlsx'
          AND c.period_end = DATE '{period}' AND c.municipality = 'Abu Dhabi City'
          AND c.district = 'Al Reem Island'
          AND c.property_type = 'apartment' AND c.source_annual_rent > 0
          {price_filter}{layout_filter}
    ) SELECT {metric}, SUM(unit_count) AS matched_units_count,
             COUNT(*) AS matched_layouts_count FROM matched"""
    return RentalPlan("gross_segment_yield" if yield_question else "weighted_annual_rent", sql)


def _rent_index_plan(question: str) -> RentalPlan | None:
    lowered = question.lower()
    if not (re.search(r"rent.{0,40}index|index.{0,40}rent|مؤشر.{0,25}إيجار", lowered)
            and ("abu dhabi city" in lowered or "مدينة أبوظبي" in lowered)):
        return None
    change = bool(re.search(r"\b(?:change|growth|increase|decrease)\b|نسبة\s+التغير|نمو", lowered))
    if not ("all zones" in lowered or "جميع المناطق" in lowered):
        return None
    if not ("all residential property types" in lowered or "all zones and property types" in lowered
            or "جميع أنواع العقارات السكنية" in lowered):
        return None
    dates = _index_dates(question)
    application = "new rents" if "new rents" in lowered or "الإيجارات الجديدة" in lowered else "(all rents)"
    if not change and len(dates) == 1 and re.search(r"\blevel\b|مستوى", lowered):
        sql = ("SELECT index_value AS rent_index FROM price_indices "
               "WHERE source_file = 'Price Indices/rent_price_index.xlsx' "
               "AND index_type = 'rent' AND municipality = 'Abu Dhabi City' "
               "AND source_area_group = '(all zones)' "
               "AND property_group = '(all property types)' "
               f"AND application_type = '{application}' AND period_end = DATE '{dates[0]}'")
        return RentalPlan("rent_index_level", sql)
    if not change or len(dates) != 2 or dates[0] >= dates[1]:
        return None
    sql = f"""SELECT 100 * (new.index_value - old.index_value)
        / NULLIF(old.index_value, 0) AS rent_index_change_pct
        FROM price_indices old JOIN price_indices new
          ON old.source_file = new.source_file AND old.municipality = new.municipality
         AND old.source_area_group = new.source_area_group
         AND old.property_group = new.property_group
         AND old.application_type = new.application_type
        WHERE old.source_file = 'Price Indices/rent_price_index.xlsx'
          AND old.index_type = 'rent' AND new.index_type = 'rent'
          AND old.municipality = 'Abu Dhabi City'
          AND old.source_area_group = '(all zones)'
          AND old.property_group = '(all property types)'
          AND old.application_type = '{application}'
          AND old.period_end = DATE '{dates[0]}'
          AND new.period_end = DATE '{dates[1]}'"""
    return RentalPlan("rent_index_change", sql)


def source_rental_plan(question: str) -> RentalPlan | None:
    lease_value = _lease_value_plan(question)
    if lease_value:
        return lease_value
    period = _quarter_end(question)
    if period:
        plan = _reem_apartment_plan(question, period)
        if plan:
            return plan
        lowered = question.lower()
        if (re.search(r"leased units|الوحدات المؤجرة|وحدات مؤجرة", lowered)
                and re.search(r"residential|السكنية|السكني", lowered)):
            return RentalPlan(
                "leased_units",
                "SELECT SUM(source_leased_units) AS leased_units_count "
                "FROM rental_observations "
                "WHERE source_file = 'Residential Leases/lease_residential.xlsx' "
                f"AND period_end = DATE '{period}'",
            )
    return _rent_index_plan(question)


def render_rental_plan_answer(question: str, kind: str, rows: list[list[object]], *, language: str = "auto") -> str:
    values = rows[0]
    value = float(values[0])
    from app.core.language import resolve_language
    arabic = resolve_language(question, language) == "ar"
    if kind == "residential_lease_value":
        scope = lease_period_scope(question, arabic)
        from app.services.answer_synthesizer import _format_aed
        amount = _format_aed(value, arabic)
        if arabic:
            return f"بلغت قيمة الإيجارات السكنية الواردة في المصدر للفترة {scope} {amount}."
        return f"The source-labelled residential lease value for {scope} was {amount}."
    if kind == "rent_index_level":
        month = _index_dates(question)[0]
        series = "new rents" if "new rents" in question.lower() or "الإيجارات الجديدة" in question else "all rents"
        if arabic:
            name = "الإيجارات الجديدة" if series == "new rents" else "جميع الإيجارات"
            return f"بلغ مستوى مؤشر {name} السكني في مدينة أبوظبي في {month:%Y-%m} {value:.4f}."
        return f"The Abu Dhabi City residential {series} index level in {month:%B %Y} was {value:.4f}."
    if kind == "rent_index_change":
        dates = _index_dates(question)
        series = "new rents" if "new rents" in question.lower() or "الإيجارات الجديدة" in question else "all rents"
        direction = ("ارتفع" if value >= 0 else "انخفض") if arabic else ("rose" if value >= 0 else "fell")
        if arabic:
            arabic_series = "الإيجارات الجديدة" if series == "new rents" else "جميع الإيجارات"
            return f"{direction} مؤشر {arabic_series} السكني في Abu Dhabi City بنسبة {abs(value):.2f}% من {dates[0]:%Y-%m} إلى {dates[1]:%Y-%m}."
        return f"The Abu Dhabi City residential {series} index {direction} {abs(value):.2f}% from {dates[0]:%B %Y} to {dates[1]:%B %Y}."

    period = _quarter_end(question)
    quarter = (period.month // 3) if period else 0
    if kind == "leased_units":
        units = f"{int(value):,}"
        if arabic:
            return f"سجّل المصدر {units} وحدة سكنية مؤجرة في نهاية الربع {quarter} من {period.year}."
        return f"The source recorded {units} residential leased units at the end of Q{quarter} {period.year}."
    units = f"{int(values[1]):,}"
    layouts = int(values[2])
    if kind == "weighted_annual_rent":
        if arabic:
            return f"بلغ تقدير الإيجار السنوي المرجح بالوحدات لشقق Al Reem Island في الربع {quarter} من {period.year} نحو {value:,.2f} درهم، استنادًا إلى {units} وحدة مؤجرة مطابقة عبر {layouts} تخطيطات."
        return f"The leased-unit-weighted annual rent estimate for Al Reem Island apartments in Q{quarter} {period.year} was AED {value:,.2f}, based on {units} matched leased units across {layouts} layouts."

    layout = _requested_layout(question)
    scope_en = f"{layout.split()[0]}-bedroom " if layout and layout != "studio" else "studio " if layout else ""
    scope_ar = f"بتخطيط {layout} " if layout else ""
    if arabic:
        answer = f"بلغ تقدير العائد الإيجاري الإجمالي لشقق Al Reem Island {scope_ar}في الربع {quarter} من {period.year} {value:.2f}%، استنادًا إلى {units} وحدة مؤجرة مطابقة عبر {layouts} تخطيطات."
        if "صافي" in question or "صافى" in question or "شقة" in question:
            answer += " يحتاج صافي عائد شقة محددة إلى إيجارها وسعرها وتكاليفها الفعلية."
        return answer
    answer = f"The indicative gross segment yield for {scope_en}Al Reem Island apartments in Q{quarter} {period.year} was {value:.2f}%, based on {units} matched leased units across {layouts} matched layouts."
    if re.search(r"\bnet\b|\bindividual\b", question, re.IGNORECASE):
        answer += " A net yield for one apartment needs that property's rent, price and costs."
    return answer
