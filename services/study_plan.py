"""
Study plan engine for Study Buddy.

Complexity score (1-10) blends three measurable factors:
  - concept difficulty   (50%) average of Gemini's 1-3 rubric rating per concept
  - prerequisite depth   (25%) longest chain of concepts that build on each other
  - vocabulary load      (25%) key terms per concept

Time to learn = sum over concepts of (base minutes for its difficulty
+ 1 min per key term past 3, max +4), plus 20% for the review question
that opens every session. Progress is tracked in minutes, so anything
studied past the daily goal comes off the remaining total ("overtime").
"""

from __future__ import annotations

from datetime import date

BASE_MINUTES = {1: 4, 2: 7, 3: 11}
REVIEW_OVERHEAD = 1.2
TIERS = [(8.0, "Intense"), (6.0, "Challenging"), (4.0, "Moderate"), (0.0, "Light")]


def concept_minutes(concept: dict) -> int:
    extra_terms = min(max(len(concept["key_terms"]) - 3, 0), 4)
    return round((BASE_MINUTES[concept["difficulty"]] + extra_terms) * REVIEW_OVERHEAD)


def prerequisite_order(concepts: list[dict]) -> list[dict]:
    """Order concepts so each comes after its prerequisites; ties keep the original order."""
    ids = {c["id"] for c in concepts}
    placed: list[dict] = []
    placed_ids: set[str] = set()
    remaining = list(concepts)
    while remaining:
        for c in remaining:
            if all(p in placed_ids or p not in ids for p in c["prerequisites"]):
                break
        else:
            c = remaining[0]  # dependency cycle: fall back to original order
        placed.append(c)
        placed_ids.add(c["id"])
        remaining.remove(c)
    return placed


def chain_depth(concepts: list[dict]) -> int:
    """Length of the longest prerequisite chain (a concept with no prerequisites has depth 1)."""
    by_id = {c["id"]: c for c in concepts}
    depth: dict[str, int] = {}

    def visit(cid: str, seen: frozenset) -> int:
        if cid in depth:
            return depth[cid]
        if cid in seen:
            return 0
        parents = [p for p in by_id[cid]["prerequisites"] if p in by_id]
        d = 1 + max((visit(p, seen | {cid}) for p in parents), default=0)
        depth[cid] = d
        return d

    return max((visit(c["id"], frozenset()) for c in concepts), default=0)


def analyze(concepts: list[dict]) -> dict:
    n = len(concepts)
    avg_difficulty = sum(c["difficulty"] for c in concepts) / n
    depth = chain_depth(concepts)
    avg_terms = sum(len(c["key_terms"]) for c in concepts) / n

    difficulty_f = (avg_difficulty - 1) / 2
    depth_f = min(depth - 1, 4) / 4
    terms_f = min(avg_terms, 8) / 8
    score = round(1 + 9 * (0.5 * difficulty_f + 0.25 * depth_f + 0.25 * terms_f), 1)

    return {
        "score": score,
        "tier": next(label for floor, label in TIERS if score >= floor),
        "total_minutes": sum(concept_minutes(c) for c in concepts),
        "concept_count": n,
        "avg_difficulty": round(avg_difficulty, 1),
        "depth": depth,
        "avg_terms": round(avg_terms, 1),
        "factors": [
            {"label": "Concept difficulty", "value": f"{avg_difficulty:.1f} / 3", "fill": difficulty_f},
            {"label": "Longest prerequisite chain", "value": f"{depth} concept{'s' if depth != 1 else ''}", "fill": depth_f},
            {"label": "Key terms per concept", "value": f"{avg_terms:.1f}", "fill": terms_f},
        ],
    }


def day_spans(minutes: list[int], per_day: int, used_today: int) -> list[tuple[int, int]]:
    """Day offsets (0 = today) each upcoming concept spans, studying exactly per_day minutes a day."""
    cursor = min(used_today, per_day)
    spans = []
    for m in minutes:
        start = cursor // per_day
        cursor += m
        spans.append((start, (cursor - 1) // per_day))
    return spans


def sessions_left(remaining: int, per_day: int, used_today: int) -> int:
    if remaining <= 0:
        return 0
    cursor = min(used_today, per_day)
    return (cursor + remaining - 1) // per_day - cursor // per_day + 1


def exam_check(remaining: int, per_day: int, days_left: int | None, used_today: int) -> dict | None:
    """Does the plan finish before the exam? days_left counts today as a study day."""
    if days_left is None:
        return None
    sessions = sessions_left(remaining, per_day, used_today)
    if days_left <= 0:
        return {"fits": False, "days_left": days_left, "sessions": sessions, "needed_per_day": None, "late_by": sessions}

    def last_day(per: int) -> int:
        return (min(used_today, per) + remaining - 1) // per

    fits = remaining <= 0 or last_day(per_day) < days_left
    needed = next((m for m in range(1, 241) if last_day(m) < days_left), 240)
    return {
        "fits": fits,
        "days_left": days_left,
        "sessions": sessions,
        "needed_per_day": needed,
        "late_by": 0 if fits else last_day(per_day) - days_left + 1,
    }


def days_until(exam: date | None, today: date) -> int | None:
    return None if exam is None else (exam - today).days
