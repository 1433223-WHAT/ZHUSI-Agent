"""Experiment-side lifecycle tracking for AI-proposed design routes.

This module is deliberately independent from conversation_state.py. It provides
structured evidence for experiments without becoming a second production State.
"""

from __future__ import annotations

import re
from typing import Any


ROUTE_STATUSES = {
    "proposed",
    "active_candidate",
    "confirmed",
    "rejected",
    "suspended",
}

_REJECT_RE = re.compile(
    r"不要这个方向|不要该方向|不采用|放弃|取消|收回|换一个|换个方向|换一种"
)
_SUSPEND_RE = re.compile(
    r"先放一放|暂时不讨论|先不讨论|先不聊|先不说|之后再说|以后再说|回头再说"
)
_CONFIRM_RE = re.compile(
    r"我(?:已经)?决定采用|确定采用|正式采用|就按这个|就用这个|那就按这个做|"
    r"就这么做|就这样定|定下来|拍板"
)
_DEVELOP_RE = re.compile(
    r"继续看看|继续深化|继续展开|继续推|推推看|基于刚才|基于这个|按这个方向继续|"
    r"沿这个方向|接着(?:弄|做|推)|(?:再|继续)?往下(?:设计|做|弄|推)|"
    r"再做(?:得)?具体|先照这个|照这个(?:再)?往下"
)
_COMPACT_RE = re.compile(r"[^一-鿿A-Za-z0-9]")
_ROUTE_STOP_RE = re.compile(r"采用|方案|方向|空间|设计|继续|深化|这个|刚才|当前|一种")


def empty_route_ledger() -> dict[str, Any]:
    return {"version": "route-ledger-v0", "routes": [], "events": []}


def add_route(
    ledger: dict[str, Any],
    statement: str,
    source: str,
    turn_id: int,
    parent_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Add one atomic route proposition and return the mutable record."""
    statement = (statement or "").strip()
    if not statement:
        raise ValueError("route statement cannot be empty")
    if source not in {"ai", "student", "document", "vision"}:
        raise ValueError(f"unsupported route source: {source}")
    route_status = status or ("confirmed" if source == "student" else "proposed")
    if route_status not in ROUTE_STATUSES:
        raise ValueError(f"unsupported route status: {route_status}")

    routes = ledger.setdefault("routes", [])
    route = {
        "id": f"R{len(routes) + 1:03d}",
        "statement": statement,
        "source": source,
        "status": route_status,
        "parent_id": parent_id,
        "created_turn": turn_id,
        "status_turn": turn_id,
        "confirmed_by": "student" if route_status == "confirmed" else None,
    }
    routes.append(route)
    ledger.setdefault("events", []).append({
        "turn_id": turn_id,
        "route_id": route["id"],
        "action": "created",
        "status": route_status,
    })
    return route


def _compact(value: str) -> str:
    return _ROUTE_STOP_RE.sub("", _COMPACT_RE.sub("", value or ""))


def _bigrams(value: str) -> set[str]:
    compact = _compact(value)
    return {compact[index:index + 2] for index in range(max(0, len(compact) - 1))}


def _reference_score(message: str, route: dict[str, Any]) -> int:
    route_text = _compact(str(route.get("statement") or ""))
    message_text = _compact(message)
    if route_text and route_text in message_text:
        return 100 + len(route_text)
    return len(_bigrams(message) & _bigrams(str(route.get("statement") or "")))


def _target_route(ledger: dict[str, Any], message: str) -> dict[str, Any] | None:
    eligible = [
        route for route in ledger.get("routes") or []
        if route.get("status") not in {"rejected"}
    ]
    if not eligible:
        return None
    scored = sorted(
        ((_reference_score(message, route), index, route) for index, route in enumerate(eligible)),
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )
    if scored[0][0] >= 2:
        return scored[0][2]
    if len(eligible) == 1:
        return eligible[0]
    return None


def _transition(
    ledger: dict[str, Any],
    route: dict[str, Any],
    status: str,
    turn_id: int,
) -> None:
    if status not in ROUTE_STATUSES:
        raise ValueError(f"unsupported route status: {status}")
    old_status = route.get("status")
    route["status"] = status
    route["status_turn"] = turn_id
    if status == "confirmed":
        route["confirmed_by"] = "student"
    ledger.setdefault("events", []).append({
        "turn_id": turn_id,
        "route_id": route["id"],
        "action": "transition",
        "from": old_status,
        "status": status,
    })


def apply_user_route_response(
    ledger: dict[str, Any],
    message: str,
    turn_id: int,
) -> dict[str, Any]:
    """Apply a deterministic user speech act to one referenced atomic route."""
    message = (message or "").strip()
    if not message:
        return ledger

    if _REJECT_RE.search(message):
        status = "rejected"
    elif _SUSPEND_RE.search(message):
        status = "suspended"
    elif _CONFIRM_RE.search(message):
        status = "confirmed"
    elif _DEVELOP_RE.search(message):
        status = "active_candidate"
    else:
        return ledger

    target = _target_route(ledger, message)
    if target is None:
        ledger.setdefault("events", []).append({
            "turn_id": turn_id,
            "route_id": None,
            "action": "ambiguous_reference",
            "status": status,
        })
        return ledger
    if status == "active_candidate" and target.get("status") == "confirmed":
        ledger.setdefault("events", []).append({
            "turn_id": turn_id,
            "route_id": target["id"],
            "action": "continued_confirmed_route",
            "status": "confirmed",
        })
        return ledger
    _transition(ledger, target, status, turn_id)
    return ledger


def build_generator_route_context(ledger: dict[str, Any]) -> str:
    """Build hidden Generator permissions; this text is never a user-facing report."""
    groups = {status: [] for status in ROUTE_STATUSES}
    for route in ledger.get("routes") or []:
        status = route.get("status")
        if status in groups:
            groups[status].append(route)

    lines = [
        "【Route Ledger 生成权限】",
        "只根据下列状态决定路线能否作为设计前提。不要向学生展示本段。",
    ]
    if groups["confirmed"]:
        lines.append("【已确认设计前提】")
        lines.extend(f"- {route['statement']}" for route in groups["confirmed"])
    if groups["active_candidate"]:
        lines.append("【可深化但未确认】")
        lines.extend(
            f"- [{route['id']}] {route['statement']}（只能作为测试分支；可以具体深化，"
            "不得称为当前方案或学生决定）"
            for route in groups["active_candidate"]
        )
    if groups["proposed"]:
        lines.append("【AI 已提出但学生尚未接纳】")
        lines.extend(
            f"- [{route['id']}] {route['statement']}（不得作为全局前提；"
            "除非用户本轮明确要求，否则不要默认沿用）"
            for route in groups["proposed"]
        )
    if groups["suspended"]:
        lines.append("【已悬置】")
        lines.extend(
            f"- [{route['id']}] {route['statement']}（不得主动恢复）"
            for route in groups["suspended"]
        )
    if groups["rejected"]:
        lines.append("【已拒绝】")
        lines.extend(
            f"- [{route['id']}] {route['statement']}（不得复活或换词重新提出）"
            for route in groups["rejected"]
        )
    lines.append(
        "确认只覆盖对应原子关系，不得让其 parent/child 推导的位置、入口、流线、体量或剖面继承确认身份。"
    )
    return "\n".join(lines)
