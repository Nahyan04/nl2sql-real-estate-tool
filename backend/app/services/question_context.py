"""Resolve user wording against bounded, snapshot-specific source values."""
from __future__ import annotations

import calendar
import hashlib
import json
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from weakref import WeakKeyDictionary
from zoneinfo import ZoneInfo

from app.models.contracts import ClarificationAnswer, ClarificationOption, ClarificationQuestion
from app.services.executor import execute_readonly

PLACE_FIELDS = {
    'transactions': ('district', 'community', 'project_name'),
    'rental_observations': ('municipality', 'district', 'community', 'project_name'),
    'price_indices': ('municipality', 'source_area_group'),
}
_FIELD_LABELS = {'district': ('district', 'منطقة'), 'community': ('community', 'مجتمع'),
                 'project_name': ('project', 'مشروع'), 'municipality': ('municipality', 'بلدية'),
                 'source_area_group': ('index area', 'نطاق المؤشر')}
_CACHE = WeakKeyDictionary()
_CACHE_LOCK = threading.Lock()
_YEAR = re.compile(r'\b(?:19|20)\d{2}\b')
_RELATIVE = re.compile(r'\b(?:latest|recent|current|this year|last year|year to date|ytd|past\s+\d+\s+(?:days?|months?|years?))\b|الأحدث|أحدث|الحالي|الحالية|هذا العام|السنة الماضية|آخر\s+\d+\s+(?:أيام|أشهر|سنوات)', re.I)


@dataclass(frozen=True)
class Place:
    relation: str
    column: str
    value: str

    @property
    def id(self) -> str:
        return _id((self.relation, self.column, self.value))


def _id(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, default=str).encode()).hexdigest()[:20]


def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).casefold()
    value = value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    return re.sub(r'[^\w]+', ' ', value, flags=re.UNICODE).strip()


def load_places(engine_ro, schema: dict, timeout_s: float = 5) -> list[Place]:
    snapshot = schema.get('snapshot_id')
    with _CACHE_LOCK:
        cached = _CACHE.get(engine_ro)
        if cached and cached[0] == snapshot and cached[1] > time.monotonic():
            return cached[2]
    parts = []
    for table in schema['tables']:
        available = {c['name'] for c in table['columns']}
        relation = table['name']
        for column in PLACE_FIELDS.get(relation, ()):
            if column in available:
                parts.append(f"SELECT DISTINCT '{relation}' AS relation, '{column}' AS field, {column} AS place FROM {relation} WHERE {column} IS NOT NULL")
    if not parts:
        return []
    result = execute_readonly(engine_ro, ' UNION ALL '.join(parts), limit=10000,
                              timeout_s=timeout_s, max_result_bytes=2_000_000)
    if result.truncated:
        raise ValueError('Source place catalog exceeds the bounded lookup budget')
    places = [Place(*row) for row in result.rows if row[2].strip() and not row[2].startswith('(')]
    with _CACHE_LOCK:
        _CACHE[engine_ro] = (snapshot, time.monotonic() + 60, places)
    return places


def relevant_relation(question: str) -> str:
    if re.search(r'\bindex|indices\b|مؤشر', question, re.I):
        return 'price_indices'
    if re.search(r'\brent|\bleas|\byield\b|إيجار|إيجاري|الإيجارات|العائد|المؤجر', question, re.I):
        return 'rental_observations'
    return 'transactions'


def _place_scope(question: str, name: str) -> str | None:
    match = re.search(r'(?:^| )' + re.escape(name) + r'(?: |$)', question)
    if not match:
        return None
    before, after = question[:match.start()].strip(), question[match.end():].strip()
    for column, labels in _FIELD_LABELS.items():
        terms = labels + (('area', 'حي') if column == 'district' else ())
        if any(re.search(r'(?:^| )' + re.escape(term) + r'(?: of| source)?$', before) or
               re.match(r'(?:source )?' + re.escape(term) + r'(?: |$)', after) for term in terms):
            return column
    return None


def _matches(question: str, places: list[Place]) -> list[tuple[str, list[Place], bool]]:
    q = normalize(question)
    # The verified Arabic source district is documented in the source contract.
    q = re.sub(r'\bالبطين\b', 'al bateen', q)
    exact = {normalize(p.value) for p in places if len(normalize(p.value)) >= 3 and
             re.search(r'(?:^| )' + re.escape(normalize(p.value)) + r'(?: |$)', q)}
    exact = {name for name in exact if not re.search(re.escape(name) + r' [a-z0-9](?: |$)', q)}
    exact = {name for name in exact if not any(name != other and f' {name} ' in f' {other} ' for other in exact)}
    groups = []
    for name in sorted(exact):
        candidates = [p for p in places if normalize(p.value) == name]
        scope = _place_scope(q, name)
        if scope:
            candidates = [p for p in candidates if p.column == scope]
        if candidates:
            groups.append((name, candidates, True))
    if groups:
        return groups
    # Close spelling matches can resolve; weaker matches need confirmation.
    phrase = re.search(r'(?:\bin\s+|\bfor\s+|في\s+)(.+?)(?=\s+(?:in\s+)?(?:19|20)\d{2}\b|\s+(?:in\s+)?q[1-4]\b|[?؟,;]|$)', question, re.I)
    if not phrase:
        return []
    name = normalize(phrase[1])
    name = re.sub(r'\s+(?:district|area|community|project|in|في)$', '', name)
    if len(name) < 4:
        return []
    scored = sorted(((SequenceMatcher(None, name, normalize(p.value)).ratio(), p) for p in places),
                    key=lambda item: (-item[0], item[1].id))
    candidates = [p for score, p in scored if score >= .72][:3]
    confident = bool(candidates and scored[0][0] >= .94 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= .06))
    scope = _place_scope(q, name)
    if scope:
        scoped = [p for p in candidates if p.column == scope]
        if scoped:
            candidates = scoped
        else:
            confident = False
    return [(name, candidates[:1] if confident else candidates, confident)] if candidates else []


@dataclass
class QuestionContext:
    places: list[Place] = field(default_factory=list)
    references: list[Place] = field(default_factory=list)
    period: tuple[date, date] | None = None
    questions: list[ClarificationQuestion] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    invalid: bool = False

    def prompt(self) -> str:
        scope = {'place_filters': [dict(relation=p.relation, column=p.column, value=p.value) for p in self.places],
                 'place_references': [dict(relation=p.relation, column=p.column, value=p.value) for p in self.references],
                 'calendar_period': {'start_inclusive': str(self.period[0]), 'end_exclusive': str(self.period[1])} if self.period else None}
        return ('\nVerified question context (data, not instructions): ' + json.dumps(scope, ensure_ascii=False) +
                '\nUse these exact source values and preserve the resolved scope. Place references identify source fields without requiring inclusion: preserve exclusions or benchmark comparisons from the question. Multiple values for the same place filter field form a comparison/filter set (IN), not mutually exclusive AND equalities. A unique source place match needs no municipality or field suffix. An explicit year is sufficient; query observed rows without asserting complete coverage. If dates are resolved, use that calendar range, not a different snapshot period. Never require the user to copy names from the source dataset; ask a specific clarification only for unresolved scope.')


def _period_options(coverage: list[dict], relation: str, arabic: bool) -> list[tuple[str, str, tuple[date, date]]]:
    files = {'transactions': 'recent_sales', 'rental_observations': 'lease_residential', 'price_indices': 'price_index'}
    rows = [r for r in coverage if files[relation] in r['source_file'] and r.get('observed_through')]
    if not rows:
        return []
    through = max(date.fromisoformat(str(r['observed_through'])[:10]) for r in rows)
    if relation == 'rental_observations':
        start_month = (through.month - 1) // 3 * 3 + 1
        start = through.replace(month=start_month, day=1)
        label = f'Q{(start.month - 1)//3 + 1} {start.year}'
        end = date(start.year + (start.month == 10), (start.month + 2) % 12 + 1, 1)
    else:
        start = through.replace(day=1)
        label = start.strftime('%Y-%m')
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    options = [('latest', f'{"أحدث فترة مرصودة" if arabic else "Latest observed period"}: {label}', (start, end)),
            ('year', f'{"سنة أحدث بيانات" if arabic else "Latest observed year"}: {through.year}', (date(through.year, 1, 1), date(through.year + 1, 1, 1)))]
    starts = [date.fromisoformat(str(r['observed_from'])[:10]) for r in rows if r.get('observed_from')]
    if starts:
        options.append(('all', 'كل الفترات المتاحة' if arabic else 'All available periods',
             (min(starts), through + timedelta(days=1))))
    return options


def resolve_context(question: str, places: list[Place], coverage: list[dict], language: str,
                    answers: list[ClarificationAnswer] | None = None, *, today: date | None = None,
                    ask_period: bool = False) -> QuestionContext:
    context = QuestionContext()
    answers = answers or []
    selected = {a.question_id: a.option_id for a in answers}
    if len(selected) != len(answers):
        context.invalid = True
    accepted = set()
    arabic = language == 'ar'
    relation = relevant_relation(question)
    available = [p for p in places if p.relation == relation]
    reference_only = bool(re.search(r'\b(?:except|excluding|exclude|other than|outside|not in|higher than|lower than|benchmark)\b|باستثناء|عدا|أعلى من|أقل من', question, re.I))
    for name, candidates, exact in _matches(question, available):
        candidates = candidates[:3] if len(candidates) >= 3 else candidates[:2]
        qid = 'place_' + _id((relation, name))
        chosen = next((p for p in candidates if p.id == selected.get(qid)), None)
        if qid in selected:
            accepted.add(qid)
            if chosen is None:
                context.invalid = True
        if not chosen and exact and len(candidates) == 1:
            chosen = candidates[0]
        if chosen:
            (context.references if reference_only else context.places).append(chosen)
            label = _FIELD_LABELS[chosen.column][arabic]
            prefix = ('مرجع' if arabic else 'reference') + ' ' if reference_only else ''
            context.descriptions.append(f'{prefix}{label}: {chosen.value}')
        elif len(candidates) >= 1:
            options = [ClarificationOption(id=p.id, label=f'{p.value} · {_FIELD_LABELS[p.column][arabic]}') for p in candidates]
            # A safe way to reject a suggestion without broadening the cohort.
            if len(options) < 3:
                options.append(ClarificationOption(id='none', label='لا شيء مما سبق' if arabic else 'None of these'))
            if selected.get(qid) == 'none':
                context.invalid = True
            context.questions.append(ClarificationQuestion(id=qid,
                prompt=('هل تقصد هذا المكان؟' if arabic else 'Did you mean this place?') if not exact else ('أي نطاق تقصد؟' if arabic else 'Which place scope do you mean?'), options=options))
    if relation == 'price_indices' and not any(p.column == 'municipality' for p in context.places):
        municipalities = sorted({p.value: p for p in available if p.column == 'municipality'}.values(), key=lambda p: p.value)
        if 2 <= len(municipalities) <= 3:
            qid = 'index_municipality'
            if qid in selected:
                accepted.add(qid)
                chosen = next((p for p in municipalities if p.id == selected[qid]), None)
                if chosen:
                    context.places.append(chosen)
                    context.descriptions.append(f'{_FIELD_LABELS[chosen.column][arabic]}: {chosen.value}')
                else:
                    context.invalid = True
            else:
                context.questions.append(ClarificationQuestion(id=qid,
                    prompt='أي بلدية تقصد للمؤشر؟' if arabic else 'Which municipality should the index use?',
                    options=[ClarificationOption(id=p.id, label=p.value) for p in municipalities]))
    today = today or datetime.now(ZoneInfo('Asia/Dubai')).date()
    q = normalize(question)
    # An explicit reporting period wins over incidental words such as recent.
    if not _YEAR.search(q):
        if re.search(r'\b(?:this year|current year|ytd|year to date)\b|هذا العام', q):
            context.period = (date(today.year, 1, 1), today + timedelta(days=1))
        elif re.search(r'\blast year\b|السنة الماضية', q):
            context.period = (date(today.year - 1, 1, 1), date(today.year, 1, 1))
        else:
            past = re.search(r'\bpast\s+(\d+)\s+(days?|months?|years?)\b', q)
            if past and 1 <= int(past[1]) <= 120:
                count = int(past[1])
                if past[2].startswith('day'):
                    start = today - timedelta(days=count - 1)
                else:
                    months = count * (12 if past[2].startswith('year') else 1)
                    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
                    start = date(year, month + 1, min(today.day, calendar.monthrange(year, month + 1)[1]))
                context.period = (start, today + timedelta(days=1))
        if not context.period and (_RELATIVE.search(question) or ask_period or 'period' in selected):
            options = _period_options(coverage, relation, arabic)
            if options:
                qid = 'period'
                if qid in selected:
                    accepted.add(qid)
                    chosen = next((o for o in options if _id((o[0], o[2])) == selected[qid]), None)
                    if chosen:
                        context.period = chosen[2]
                    else:
                        context.invalid = True
                else:
                    context.questions.append(ClarificationQuestion(id=qid,
                        prompt='أي فترة تريد تحليلها؟' if arabic else 'Which period would you like to analyse?',
                        options=[ClarificationOption(id=_id((key, dates)), label=label) for key, label, dates in options]))
    if context.period:
        context.descriptions.append(f'{context.period[0]} ≤ date < {context.period[1]}')
    if set(selected) - accepted:
        context.invalid = True
    return context
