from typing import Any, Dict, Iterable, Optional


TECHNICAL_ANCHOR_TYPES = {"skill", "gap", "project", "experience"}


def _score(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    return max(0.0, min(10.0, numeric))


def _average(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def level_for_score(score: float) -> str:
    if score >= 7.5:
        return "strong"
    if score >= 5.0:
        return "medium"
    return "weak"


def clean_category_name(category: str) -> str:
    return category.replace("_", " ").strip().title()


def category_scores_for_exchange(exchange: Dict[str, Any]) -> Dict[str, float]:
    """Map one evaluated exchange to dashboard competency categories.

    The categories are derived only from persisted evaluation metrics. No category
    is emitted unless at least one underlying score exists for that exchange.
    """
    evaluation = exchange.get("evaluation") or {}
    anchor_type = (exchange.get("anchor_type") or "skill").lower()
    interview_type = (exchange.get("interview_type") or "").lower()

    accuracy = _score(evaluation.get("score_accuracy"))
    depth = _score(evaluation.get("score_depth"))
    clarity = _score(evaluation.get("score_clarity"))
    star = _score(evaluation.get("score_star"))

    categories: Dict[str, float] = {}

    if anchor_type in TECHNICAL_ANCHOR_TYPES:
        if accuracy is not None:
            categories["Technical Skills"] = accuracy
        if depth is not None:
            categories["Problem Solving"] = depth

    if clarity is not None:
        categories["Clarity"] = clarity

    if anchor_type in {"project", "experience"}:
        experience_score = _average([accuracy, depth])
        if experience_score is not None:
            categories["Experience Relevance"] = experience_score

    if anchor_type == "soft_skill":
        soft_score = _average([depth, clarity, star])
        if soft_score is not None:
            categories["Soft Skills"] = soft_score

    if anchor_type == "soft_skill" or interview_type == "behavioral":
        behavioral_score = _average([star, clarity if anchor_type == "soft_skill" else None])
        if behavioral_score is not None:
            categories["Behavioral Skills"] = behavioral_score

    return categories


def aggregate_competency_breakdown(exchanges: list[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    totals: Dict[str, Dict[str, Any]] = {}

    for exchange in exchanges:
        category_scores = category_scores_for_exchange(exchange)
        feedback = (exchange.get("evaluation") or {}).get("feedback")

        for category, score in category_scores.items():
            if category not in totals:
                totals[category] = {"total": 0.0, "count": 0, "feedbacks": []}
            totals[category]["total"] += score
            totals[category]["count"] += 1
            if feedback:
                totals[category]["feedbacks"].append(feedback)

    breakdown: Dict[str, Dict[str, Any]] = {}
    for category, data in totals.items():
        count = max(data["count"], 1)
        breakdown[category] = {
            "score": round(data["total"] / count, 1),
            "nb_questions": data["count"],
            "feedback": data["feedbacks"][0] if data["feedbacks"] else "No specific feedback.",
        }

    return breakdown
