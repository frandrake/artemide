"""Run the audit-ledger report."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

from ...services.audit_service import AuditService
from .._common import error_response, tool_session
from ..registry import mcp


def _dc(obj):
    if is_dataclass(obj):
        return {k: _dc(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc(i) for i in obj]
    return obj


@mcp.tool
def audit_ledger() -> dict:
    """Generate the full audit report (coverage, dormancy, follow-ups, etc.)."""
    with tool_session("audit_ledger") as (_, ctx):
        try:
            report = AuditService.generate_report(ctx)
            return {"ok": True, "report": _dc(report)}
        except Exception as e:
            return error_response(e)
