import re
from dataclasses import dataclass

from nanoni.domain.enums import ModerationSeverity


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    severity: str = ModerationSeverity.REVIEW
    whole_word: bool = False


@dataclass(frozen=True)
class ModerationResult:
    severity: str
    matched_rule_ids: tuple[str, ...]


_SEVERITY_ORDER = {
    ModerationSeverity.ALLOW: 0,
    ModerationSeverity.REVIEW: 1,
    ModerationSeverity.REMOVE: 2,
    ModerationSeverity.BAN_REVIEW: 3,
}


def classify_public_message(text: str, rules: list[Rule]) -> ModerationResult:
    """Rule engine for community messages.

    This engine is deliberately separate from admin-library search; it never blocks
    an administrator from searching their own metadata. Rules should target illegal
    or operationally forbidden community behavior, not arbitrary words.
    """
    matched: list[Rule] = []
    for rule in rules:
        pattern = rf"\b(?:{rule.pattern})\b" if rule.whole_word else rule.pattern
        if re.search(pattern, text, flags=re.IGNORECASE):
            matched.append(rule)
    if not matched:
        return ModerationResult(ModerationSeverity.ALLOW, ())
    strongest = max(matched, key=lambda r: _SEVERITY_ORDER.get(r.severity, 1))
    return ModerationResult(strongest.severity, tuple(r.id for r in matched))
