"""Closed integer intervals (synthetic fixture repository)."""


def merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping closed intervals, e.g. [(1,3),(2,5)] -> [(1,5)]."""
    out: list[tuple[int, int]] = []
    for lo, hi in sorted(intervals):
        if out and lo < out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out
