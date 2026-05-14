"""Response serialisation helpers — strip internal integer PKs."""
from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel


_INTERNAL_FIELDS = {"id", "firm_id", "partner_id"}


def to_response(record: BaseModel, *, extra_exclude: set[str] | None = None) -> dict[str, Any]:
    exclude = set(_INTERNAL_FIELDS)
    if extra_exclude:
        exclude |= extra_exclude
    return record.model_dump(mode="json", exclude=exclude)


def to_response_list(
    records: Iterable[BaseModel], *, extra_exclude: set[str] | None = None
) -> list[dict[str, Any]]:
    return [to_response(r, extra_exclude=extra_exclude) for r in records]
