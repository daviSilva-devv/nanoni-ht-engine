from nanoni.domain.services.moderation import Rule, classify_public_message
from nanoni.domain.services.scoring import content_score, source_approval_rate


def test_score_rewards_conversions_more_than_reactions():
    score = content_score(reactions=20, replies=3, unique_repliers=2, clicks=4, conversions=1)
    assert score > 20
    assert source_approval_rate(approved=61, presented=80) == 0.7625


def test_public_moderation_is_rule_driven_not_admin_search_blacklist():
    result = classify_public_message(
        "request forbidden-token here",
        [Rule(id="r1", pattern="forbidden-token", severity="REMOVE")],
    )
    assert result.severity == "REMOVE"
    assert result.matched_rule_ids == ("r1",)
