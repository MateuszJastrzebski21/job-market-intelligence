"""Unit tests for the field-comparison metrics."""
from __future__ import annotations

import pytest

from jmi.evaluation.metrics import (
    exact_match,
    jaccard_similarity,
    numeric_match_or_both_null,
    salary_match,
)


def test_exact_match_equal_values() -> None:
    assert exact_match("senior", "senior") is True


def test_exact_match_different_values() -> None:
    assert exact_match("mid", "senior") is False


def test_exact_match_both_none() -> None:
    assert exact_match(None, None) is True


def test_exact_match_one_none() -> None:
    assert exact_match(None, "remote") is False


def test_jaccard_both_empty_is_one() -> None:
    assert jaccard_similarity([], []) == 1.0


def test_jaccard_one_empty_is_zero() -> None:
    assert jaccard_similarity(["Python"], []) == 0.0
    assert jaccard_similarity([], ["Python"]) == 0.0


def test_jaccard_identical_lists() -> None:
    assert jaccard_similarity(["Python", "AWS"], ["Python", "AWS"]) == 1.0


def test_jaccard_case_insensitive_and_stripped() -> None:
    assert jaccard_similarity(["PyTorch", " AWS"], ["pytorch", "aws"]) == 1.0


def test_jaccard_partial_overlap() -> None:
    # intersection {python}, union {python, aws, gcp} -> 1/3
    assert jaccard_similarity(["Python", "AWS"], ["Python", "GCP"]) == pytest.approx(
        1 / 3
    )


def test_numeric_match_both_null() -> None:
    assert numeric_match_or_both_null(None, None) is True


def test_numeric_match_equal() -> None:
    assert numeric_match_or_both_null(3, 3) is True


def test_numeric_match_mixed_null_or_unequal() -> None:
    assert numeric_match_or_both_null(3, None) is False
    assert numeric_match_or_both_null(2, 5) is False


def test_salary_match_both_all_null() -> None:
    assert salary_match(None, None, None, None) is True


def test_salary_match_within_tolerance() -> None:
    # 105k vs 100k, 209k vs 200k — both inside the default 10% band
    assert salary_match(105_000, 209_000, 100_000, 200_000) is True


def test_salary_match_outside_tolerance() -> None:
    # 130k vs 100k — 30% off, beyond the 10% band
    assert salary_match(130_000, 200_000, 100_000, 200_000) is False


def test_salary_match_mixed_null_fails() -> None:
    # expected has a value, extract captured None — recall miss
    assert salary_match(None, None, 100_000, 200_000) is False


def test_salary_match_custom_tolerance() -> None:
    assert salary_match(120_000, 240_000, 100_000, 200_000, tolerance_pct=0.25) is True
