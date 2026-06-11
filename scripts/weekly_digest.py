"""Weekly Artemide digest → Telegram.

Pulls the week's actionables from the REST API (loopback) and pushes a
summary to Telegram. Designed for host cron — stdlib only, no venv needed.

Config (env vars, with fallback to the listed files):
    ARTEMIDE_URL        default http://127.0.0.1:47600
    ARTEMIDE_API_TOKEN  fallback: /root/artemide/.env
    TELEGRAM_BOT_TOKEN  fallback: /root/artemide/.digest.env
    TELEGRAM_CHAT_ID    fallback: /root/artemide/.digest.env

Usage:
    python3 scripts/weekly_digest.py            # send digest
    python3 scripts/weekly_digest.py --dry-run  # print, don't send
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ARTEMIDE_URL = os.environ.get("ARTEMIDE_URL", "http://127.0.0.1:47600")
ENV_FILES = (Path("/root/artemide/.env"), Path("/root/artemide/.digest.env"))


def _load_env_fallbacks() -> None:
    for env_file in ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _get(path: str) -> object:
    req = urllib.request.Request(
        f"{ARTEMIDE_URL}{path}",
        headers={
            "Authorization": f"Bearer {os.environ['ARTEMIDE_API_TOKEN']}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_digest() -> str:
    today = date.today()
    lines: list[str] = [f"<b>Artemide — week of {today:%d %b %Y}</b>"]

    # Relationship cadence: who is overdue / due in the next 14 days.
    touches = _get("/api/v1/planning/due-touches?window_days=14")
    overdue = [t for t in touches if t["status"] == "overdue"]
    due_soon = [t for t in touches if t["status"] == "due_soon"]
    if overdue:
        lines.append(f"\n<b>Overdue touches ({len(overdue)})</b>")
        for t in overdue[:8]:
            days = t.get("days_since_last_contact")
            since = f", {days}d since last contact" if days is not None else ""
            lines.append(f"• {_esc(t['partner_name'])} ({_esc(t['firm_name'])}{since})")
        if len(overdue) > 8:
            lines.append(f"  …and {len(overdue) - 8} more")
    if due_soon:
        lines.append(f"\n<b>Due in 14 days ({len(due_soon)})</b>")
        for t in due_soon[:5]:
            lines.append(f"• {_esc(t['partner_name'])} ({_esc(t['firm_name'])})")
        if len(due_soon) > 5:
            lines.append(f"  …and {len(due_soon) - 5} more")
    if not overdue and not due_soon:
        lines.append("\nNo touches due in the next 14 days.")

    # 12-month plan: rows past due / due this week.
    past_due = _get("/api/v1/engagement-calendar?due_window=past_due")
    past_due = [r for r in past_due if r["status"] != "complete"]
    this_week = _get("/api/v1/engagement-calendar?due_window=this_week")
    this_week = [r for r in this_week if r["status"] != "complete"]
    if past_due:
        lines.append(f"\n<b>Plan rows past due ({len(past_due)})</b>")
        for r in past_due[:6]:
            track = f" [{r['track']}]" if r.get("track") else ""
            lines.append(f"• {_esc(r['title'])}{track} — was due {r['due_date']}")
        if len(past_due) > 6:
            lines.append(f"  …and {len(past_due) - 6} more")
    if this_week:
        lines.append(f"\n<b>Plan rows this week ({len(this_week)})</b>")
        for r in this_week[:6]:
            lines.append(f"• {_esc(r['title'])} — due {r['due_date']}")

    # Mandate pipeline: open roles by stage + next steps with dates.
    engagements = _get("/api/v1/engagements")
    open_eng = [e for e in engagements if e["stage"] != "closed"]
    if open_eng:
        by_stage: dict[str, int] = {}
        for e in open_eng:
            by_stage[e["stage"]] = by_stage.get(e["stage"], 0) + 1
        stages = ", ".join(f"{k} {v}" for k, v in by_stage.items())
        lines.append(f"\n<b>Pipeline</b>: {len(open_eng)} open ({stages})")
        steps = [
            e for e in open_eng
            if e.get("next_step") and e.get("next_step_date")
            and e["next_step_date"] <= f"{today:%Y-%m-%d}"
        ]
        for e in steps[:5]:
            org = f"{e['org_name']} — " if e.get("org_name") else ""
            lines.append(f"• {_esc(org)}{_esc(e['role_title'])}: {_esc(e['next_step'])}")

    # Approval queue.
    proposed = _get("/api/v1/messages?status=proposed")
    if proposed:
        lines.append(f"\n<b>Awaiting approval</b>: {len(proposed)} message(s)")

    # Programme heartbeat.
    try:
        prog = _get("/api/v1/programme/status")
        rag = {"green": "🟢", "amber": "🟠", "red": "🔴"}.get(prog["overall_rag"], "")
        lines.append(
            f"\n<b>Programme</b> {rag} — {prog['days_to_target']} days to target"
            + (" ⚠ at risk" if prog.get("target_at_risk") else "")
        )
    except Exception:
        pass  # programme status is a heartbeat, never block the digest

    return "\n".join(lines)


def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    data = urllib.parse.urlencode({
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
        if not body.get("ok"):
            raise RuntimeError(f"telegram send failed: {body}")


def main() -> int:
    _load_env_fallbacks()
    digest = build_digest()
    if "--dry-run" in sys.argv:
        print(digest)
        return 0
    send_telegram(digest)
    print(f"digest sent ({len(digest)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
