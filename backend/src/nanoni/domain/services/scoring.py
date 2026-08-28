from dataclasses import dataclass


@dataclass(frozen=True)
class EngagementWeights:
    reaction: float = 0.25
    reply: float = 1.0
    unique_replier: float = 1.5
    click: float = 2.0
    conversion: float = 10.0


def content_score(
    *,
    reactions: int,
    replies: int,
    unique_repliers: int,
    clicks: int = 0,
    conversions: int = 0,
    weights: EngagementWeights | None = None,
) -> float:
    w = weights or EngagementWeights()
    return round(
        reactions * w.reaction
        + replies * w.reply
        + unique_repliers * w.unique_replier
        + clicks * w.click
        + conversions * w.conversion,
        4,
    )


def source_approval_rate(*, approved: int, presented: int) -> float:
    return 0.0 if presented <= 0 else round(approved / presented, 4)


def source_score(
    *, approved: int, presented: int, engagement_score: float, approval_weight: float = 0.7
) -> float:
    rate = source_approval_rate(approved=approved, presented=presented)
    engagement_normalized = max(0.0, min(1.0, engagement_score / 100.0))
    return round(rate * approval_weight + engagement_normalized * (1 - approval_weight), 4)
