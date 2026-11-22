"""Tests for the AI usage models."""

from datetime import datetime

from shared.usage import AIUsage, UsageSummary, utcnow


def test_usage_row_defaults():
    row = AIUsage(user_id=1, feature="agent", model="m")
    assert (row.input_tokens, row.output_tokens, row.requests, row.cost) == (0, 0, 0, 0)
    assert row.created_at.tzinfo is None
    assert abs((utcnow() - row.created_at).total_seconds()) < 5


def test_usage_summary():
    summary = UsageSummary(
        plan="free",
        ai_used=1,
        ai_allowance=2,
        ai_resets_at=datetime(2026, 12, 1),
        storage_used=3,
        storage_limit=4,
    )
    assert summary.model_dump()["ai_resets_at"] == datetime(2026, 12, 1)
