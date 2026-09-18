"""KidProductionz Sales OS AI Agent.

The AI interprets Sales OS data. It does not replace deterministic
qualification, scoring, routing, queue logic, or confirmation safeguards.
"""

from __future__ import annotations

import json
import os
from typing import Any
from pathlib import Path

from dotenv import load_dotenv
from google import genai


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / '.env')

SYSTEM_PROMPT = """
You are the KidProductionz Sales OS AI Sales Agent.

You help the user sell more effectively using REAL information supplied
by KidProductionz Sales OS.

CORE RULES

1. Never invent prospect facts, conversations, contact information,
   business observations, buying signals, scores, or activity.

2. Sales OS data is the source of truth.

3. Never independently change qualification scores, grades, queue
   positions, or routing decisions.

4. You may explain and interpret those decisions.

5. Clearly distinguish known facts from your recommendations.

6. If information needed to answer is unavailable, say so.

7. Be practical and sales-focused. Give the user a clear next move.

8. Never claim an external action happened unless Sales OS confirms it.

9. Sending email, creating calendar events, modifying CRM records,
   or other external writes require explicit user confirmation.

10. Drafting, analysis, recommendations, and explanations do not
    require confirmation.

11. When recommending prospects, use the supplied qualification,
    routing, queue, status, and activity evidence.

12. Do not pretend a prospect expressed interest unless that interaction
    exists in the supplied data.

13. Keep responses concise enough to be useful inside a sales dashboard.

You are a sales copilot, not the qualification engine.
"""


def classify_intent(message: str) -> str:
    text = (message or "").lower()

    if any(
        x in text
        for x in (
            "who should i call",
            "who should i contact",
            "best leads",
            "top prospects",
            "priority leads",
            "who should i reach",
        )
    ):
        return "QUEUE_ANALYSIS"

    if any(
        x in text
        for x in (
            "why did",
            "why is",
            "score",
            "qualified",
            "qualification",
            "grade",
        )
    ):
        return "QUALIFICATION_EXPLANATION"

    if any(
        x in text
        for x in (
            "draft",
            "what should i say",
            "email",
            "dm ",
            "message",
            "script",
        )
    ):
        return "OUTREACH_DRAFT"

    if any(
        x in text
        for x in (
            "follow up",
            "follow-up",
            "overdue",
            "next action",
        )
    ):
        return "FOLLOW_UP"

    if any(
        x in text
        for x in (
            "pipeline",
            "metrics",
            "performance",
            "conversion",
        )
    ):
        return "PIPELINE_ANALYSIS"

    return "GENERAL_SALES"


def build_sales_context(
    campaign: str,
    prospects: list[dict[str, Any]] | None = None,
    queue: dict[str, Any] | None = None,
    follow_ups: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    selected_prospect: dict[str, Any] | None = None,
) -> dict[str, Any]:

    return {
        "campaign": campaign,
        "selected_prospect": selected_prospect,
        "prospects": prospects or [],
        "queue": queue or {},
        "follow_ups": follow_ups or [],
        "metrics": metrics or {},
    }


def action(
    action_type: str,
    prospect_id: int | None = None,
    payload: dict[str, Any] | None = None,
    requires_confirmation: bool = True,
) -> dict[str, Any]:

    return {
        "type": action_type,
        "prospect_id": prospect_id,
        "payload": payload or {},
        "requires_confirmation": requires_confirmation,
    }


def safe_response(
    reply: str,
    intent: str,
    prospects_used: list[int] | None = None,
    suggested_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:

    actions = suggested_actions or []

    return {
        "reply": reply,
        "intent": intent,
        "prospects_used": prospects_used or [],
        "suggested_actions": actions,
        "requires_confirmation": any(
            bool(item.get("requires_confirmation"))
            for item in actions
        ),
    }


def _compact_context(context: dict[str, Any]) -> dict[str, Any]:
    """
    Keep requests inexpensive and prevent huge prospect lists from being
    sent to the model.

    Priority queue prospects are sent first, followed by a bounded
    campaign prospect sample.
    """

    queue = context.get("queue") or {}
    prospects = context.get("prospects") or []

    daily = queue.get("daily_queue") or []
    deferred = queue.get("deferred") or []
    research = queue.get("research") or []

    return {
        "campaign": context.get("campaign"),
        "selected_prospect": context.get("selected_prospect"),

        "queue_summary": queue.get("summary") or {},

        "daily_queue": daily[:15],
        "deferred": deferred[:8],
        "research": research[:8],

        "prospects": prospects[:25],

        "follow_ups": (context.get("follow_ups") or [])[:15],
        "metrics": context.get("metrics") or {},
    }


def _fallback(
    message: str,
    campaign: str,
    context: dict[str, Any],
    reason: str | None = None,
) -> dict[str, Any]:

    intent = classify_intent(message)

    selected = context.get("selected_prospect")

    if selected:
        name = (
            selected.get("name")
            or selected.get("business")
            or "this prospect"
        )

        prospect_id = (
            selected.get("id")
            or selected.get("prospect_id")
        )

        return safe_response(
            reply=(
                f"I have {name} loaded from {campaign}. "
                "The AI model is temporarily unavailable, but the "
                "Sales OS data is still available."
            ),
            intent=intent,
            prospects_used=[prospect_id] if prospect_id else [],
        )

    return safe_response(
        reply=(
            "The AI model is temporarily unavailable, but your Sales OS "
            "is still running. Try the request again in a moment."
        ),
        intent=intent,
    )


def chat(
    message: str,
    campaign: str,
    context: dict[str, Any],
    conversation: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:

    intent = classify_intent(message)

    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    if not api_key:
        return _fallback(
            message,
            campaign,
            context,
            "GEMINI_API_KEY missing",
        )

    client = genai.Client(api_key=api_key)

    compact = _compact_context(context)

    history = []

    for item in (conversation or [])[-8:]:
        role = item.get("role")

        if role not in ("user", "assistant"):
            continue

        content = str(item.get("content") or "").strip()

        if not content:
            continue

        history.append(
            {
                "role": role,
                "content": content[:3000],
            }
        )

    developer_context = (
        "CURRENT SALES OS CONTEXT\n\n"
        + json.dumps(
            compact,
            default=str,
            ensure_ascii=False,
        )
        + "\n\n"
        + f"DETERMINISTIC INTENT HINT: {intent}\n"
        + "Answer using only facts contained in this context. "
          "You may provide recommendations based on those facts."
    )

    input_messages = [
        {
            "role": "developer",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "developer",
            "content": developer_context,
        },
        *history,
        {
            "role": "user",
            "content": message,
        },
    ]

    try:
        prompt = (
            SYSTEM_PROMPT
            + "\n\n"
            + developer_context
            + "\n\nCONVERSATION HISTORY:\n"
            + json.dumps(history, default=str, ensure_ascii=False)
            + "\n\nUSER REQUEST:\n"
            + message
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        reply = (response.text or "").strip()

        if not reply:
            return _fallback(
                message,
                campaign,
                context,
                "Empty model response",
            )

        # V1 keeps external actions read-only.
        # Structured action execution comes after conversational testing.
        return safe_response(
            reply=reply,
            intent=intent,
            prospects_used=[],
            suggested_actions=[],
        )

    except Exception as e:
        print(
            "GEMINI SALES AGENT ERROR:",
            type(e).__name__,
            str(e),
            flush=True,
        )

        return _fallback(
            message,
            campaign,
            context,
            "Gemini request failed",
        )
