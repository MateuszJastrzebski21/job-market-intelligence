"""Field-comparison metrics for extraction-quality evaluation.

Pure functions, no I/O. Each compares one extracted field against its
ground-truth label. Argument order is always ``(actual, expected)``.
"""


def exact_match(actual: object | None, expected: object | None) -> bool:
    """Equality, with both-``None`` counting as a match.

    Used for categorical fields: seniority, remote_policy, employment_type,
    salary_currency.
    """
    return actual == expected


def jaccard_similarity(actual: list[str], expected: list[str]) -> float:
    """Case-insensitive Jaccard similarity of two string lists.

    Both sides are lowercased and stripped before set construction, so
    ``"PyTorch"`` and ``"pytorch "`` are the same element. Returns
    ``|intersection| / |union|``.

    Both lists empty → ``1.0``: the extractor correctly produced nothing
    when nothing was expected. One side empty, the other not → ``0.0``.
    """
    actual_set = {s.strip().lower() for s in actual}
    expected_set = {s.strip().lower() for s in expected}
    union = actual_set | expected_set
    if not union:
        return 1.0
    return len(actual_set & expected_set) / len(union)


def numeric_match_or_both_null(actual: int | None, expected: int | None) -> bool:
    """Exact integer equality, or both ``None``.

    Used for years_experience_min, where no tolerance applies.
    """
    return actual == expected


def _endpoint_within_tolerance(
    actual: int | None, expected: int | None, tolerance_pct: float
) -> bool:
    """One salary endpoint: both ``None`` matches; a ``None`` on either side
    alone does not; otherwise within ``tolerance_pct`` relative tolerance."""
    if actual is None or expected is None:
        return actual is None and expected is None
    if expected == 0:
        return actual == 0
    return abs(actual - expected) <= tolerance_pct * abs(expected)


def salary_match(
    actual_min: int | None,
    actual_max: int | None,
    expected_min: int | None,
    expected_max: int | None,
    tolerance_pct: float = 0.1,
) -> bool:
    """True when both salary endpoints agree within ``tolerance_pct``.

    A ``None`` expected endpoint is matched only by a ``None`` actual
    endpoint. All-null on both sides is a match (the extractor correctly
    declined to invent a salary).
    """
    return _endpoint_within_tolerance(
        actual_min, expected_min, tolerance_pct
    ) and _endpoint_within_tolerance(actual_max, expected_max, tolerance_pct)
