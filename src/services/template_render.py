"""Mustache-lite template renderer (stdlib only).

Supports:
  - {{var}}                — substitution; empty string + recorded in missing_variables
                              if context value is None/""
  - {{#var}}block{{/var}}  — emit block only if context[var] is non-empty
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..models import FirmRecord, PartnerRecord, ValueCalendarRecord


_BLOCK_RE = re.compile(r"\{\{#([\w.]+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
_VAR_RE = re.compile(r"\{\{([\w.]+)\}\}")
_TRIPLE_NEWLINE_RE = re.compile(r"\n{3,}")


def build_context(
    *,
    partner: PartnerRecord | None = None,
    firm: FirmRecord | None = None,
    quarter: ValueCalendarRecord | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, str | None]:
    ctx: dict[str, Any] = {"today": date.today().isoformat()}

    if partner is not None:
        for k, v in partner.model_dump(mode="json").items():
            ctx[f"partner.{k}"] = v
    if firm is not None:
        for k, v in firm.model_dump(mode="json").items():
            ctx[f"firm.{k}"] = v
    if quarter is not None:
        ctx["this_quarter.topic"] = quarter.topic
        ctx["this_quarter.label"] = f"Q{quarter.quarter} {quarter.year}"
    else:
        ctx.setdefault("this_quarter.topic", None)
        ctx.setdefault("this_quarter.label", None)

    if overrides:
        ctx.update(overrides)

    # Normalise to str | None so callers don't see integers / dates.
    return {k: (None if v is None else str(v)) for k, v in ctx.items()}


def _has_value(v: str | None) -> bool:
    return v is not None and v.strip() != ""


def render(
    template: str,
    context: dict[str, str | None],
) -> tuple[str, list[str], dict[str, str]]:
    """Returns (rendered, missing_variables, used_variables)."""
    missing: list[str] = []
    used: dict[str, str] = {}

    # Pass 1: conditional blocks. Recursive removal so nested blocks work.
    def _block_sub(match: re.Match[str]) -> str:
        var = match.group(1)
        body = match.group(2)
        return body if _has_value(context.get(var)) else ""

    prev = None
    out = template
    while prev != out:
        prev = out
        out = _BLOCK_RE.sub(_block_sub, out)

    # Pass 2: simple substitutions.
    def _var_sub(match: re.Match[str]) -> str:
        var = match.group(1)
        val = context.get(var)
        if not _has_value(val):
            if var not in missing:
                missing.append(var)
            return ""
        used[var] = val  # type: ignore[assignment]
        return val  # type: ignore[return-value]

    out = _VAR_RE.sub(_var_sub, out)
    out = _TRIPLE_NEWLINE_RE.sub("\n\n", out)
    return out, missing, used
