from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

from app.models.contracts import ExamplesResponse

router = APIRouter()

EXAMPLES_PATH = Path(__file__).resolve().parents[2] / "resources" / "examples.json"


@lru_cache
def load_examples() -> ExamplesResponse:
    return ExamplesResponse(**json.loads(EXAMPLES_PATH.read_text(encoding="utf-8")))


@router.get("/examples", response_model=ExamplesResponse)
def examples() -> ExamplesResponse:
    return load_examples()
