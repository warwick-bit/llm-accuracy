"""Bounded whole-pair transport recovery, independent of answer quality."""

from collections.abc import Callable


RETRYABLE = frozenset({"timeout", "missing_result", "host_error"})
STATUSES = RETRYABLE | {
    "ok", "authentication", "rate_limit", "host_unavailable", "auth_copy_failed",
    "oversized_output", "invalid_model", "invalid_effort",
}


def complete_cases(receipts: list[dict], expected: list[str]) -> bool:
    """A stage needs every declared case, in order, with a complete pair."""
    return bool(expected) and [r.get("case") for r in receipts] == expected and all(
        r.get("status") == "complete" for r in receipts
    )


def attempt_receipt(results: dict, valid: dict) -> dict:
    """Persist fixed labels and counts, never response text or host details."""
    return {
        arm: {
            "status": result.get("status")
            if result.get("status") in STATUSES else "unrecognized_status",
            "valid": valid[arm],
            "result_count": result.get("result_count", 0)
            if type(result.get("result_count", 0)) is int else 0,
        }
        for arm, result in results.items()
    }


def run_pair(
    probe: Callable[[str], dict],
    valid_result: Callable[[dict], bool],
    *,
    arms: tuple[str, str] = ("baseline", "candidate"),
    max_attempts: int = 1,
) -> dict:
    """Retry both arms only after transport failure; never examine answer quality.

    Callers must freeze max_attempts before execution and bound each probe's
    runtime and return known host failures as status dictionaries. Unexpected
    exceptions and cancellation propagate without recovery. Returned answers
    remain in memory. Do not persist ``results``.
    A successful pair establishes completion conditional on recovery, not
    equal completion rates or population-level accuracy.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be an integer from 1 through 3")
    if len(arms) != 2 or len(set(arms)) != 2:
        raise ValueError("exactly two distinct arms are required")
    attempts = []
    for index in range(max_attempts):
        order = arms if index % 2 == 0 else tuple(reversed(arms))
        results = {arm: probe(arm) for arm in order}
        valid = {arm: bool(valid_result(value)) for arm, value in results.items()}
        attempts.append(attempt_receipt(results, valid))
        if all(valid.values()):
            status = "complete"
            break
        invalid = [value for arm, value in results.items() if not valid[arm]]
        if any(value.get("status") not in RETRYABLE for value in invalid):
            status = "invalid_result"
            break
        status = "transport_exhausted"
    return {
        "status": status,
        "results": results if status == "complete" else {},
        "attempts": attempts,
    }
