"""Judge calibration: metrics, Cohen's kappa, admission policy, annotator agreement.

A judge is a model; it must be measured against reference labels before it may gate.
Positive class = "pass". A *false positive* is a judge pass where the reference says
fail (a lenient judge ships bad behaviour), which is why FPR is a hard admission limit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from itertools import combinations

from .hashing import hash_obj


@dataclass(frozen=True)
class CalibrationMetrics:
    n: int
    n_pos: int  # reference label == pass
    n_neg: int
    tp: int
    fp: int
    tn: int
    fn: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    kappa: float
    fpr: float
    fnr: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Cohen's kappa for two binary raters.

    When chance agreement is 1 (a rater used one class only on both sides) kappa is
    undefined; we return 1.0 only for perfect agreement and 0.0 otherwise, so a lack of
    variance is never reported as evidence of agreement beyond chance.
    """
    if len(a) != len(b):
        raise ValueError("rating sequences must have equal length")
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def _div(a: float, b: float) -> float:
    return a / b if b else 0.0


def calibration_metrics(predicted: Sequence[bool], reference: Sequence[bool]) -> CalibrationMetrics:
    if len(predicted) != len(reference):
        raise ValueError("predicted and reference must have equal length")
    pairs = list(zip(predicted, reference, strict=True))
    tp = sum(p and r for p, r in pairs)
    fp = sum(p and not r for p, r in pairs)
    tn = sum((not p) and (not r) for p, r in pairs)
    fn = sum((not p) and r for p, r in pairs)
    n = len(pairs)
    prec, rec = _div(tp, tp + fp), _div(tp, tp + fn)
    return CalibrationMetrics(
        n=n,
        n_pos=tp + fn,
        n_neg=tn + fp,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        accuracy=_div(tp + tn, n),
        precision=prec,
        recall=rec,
        f1=_div(2 * prec * rec, prec + rec),
        kappa=cohens_kappa(list(predicted), list(reference)),
        fpr=_div(fp, fp + tn),
        fnr=_div(fn, fn + tp),
    )


@dataclass(frozen=True)
class AdmissionPolicy:
    """Defaults are a conservative starting point, not universal scientific truths."""

    min_items: int = 50
    min_per_class: int = 10
    min_kappa: float = 0.60
    max_fpr: float = 0.05
    version: str = "adm-1"

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reasons: list[str] = field(default_factory=list)
    metrics: CalibrationMetrics | None = None
    policy: AdmissionPolicy = field(default_factory=AdmissionPolicy)

    @property
    def label(self) -> str:
        return "CALIBRATED — allowed for gating" if self.admitted else "NOT CALIBRATED — diagnostic only"


def admit(metrics: CalibrationMetrics, policy: AdmissionPolicy | None = None) -> AdmissionDecision:
    pol = policy or AdmissionPolicy()
    why: list[str] = []
    if metrics.n < pol.min_items:
        why.append(f"only {metrics.n} labeled items (need >= {pol.min_items})")
    if metrics.n_pos < pol.min_per_class:
        why.append(f"only {metrics.n_pos} 'pass' reference items (need >= {pol.min_per_class})")
    if metrics.n_neg < pol.min_per_class:
        why.append(f"only {metrics.n_neg} 'fail' reference items (need >= {pol.min_per_class})")
    if metrics.kappa < pol.min_kappa:
        why.append(f"Cohen's kappa {metrics.kappa:.2f} < {pol.min_kappa:.2f}")
    if metrics.fpr > pol.max_fpr:
        why.append(f"false-positive rate {metrics.fpr:.2%} > {pol.max_fpr:.0%}")
    return AdmissionDecision(not why, why, metrics, pol)


def judge_identity(backend: str, model: str, prompt_hash: str) -> str:
    """A judge configuration is identified by (backend, model, prompt hash). Any change => recalibrate."""
    return hash_obj({"backend": backend, "model": model, "prompt_hash": prompt_hash}, 16)


def mean_pairwise_kappa(annotations: dict[str, dict[str, bool]]) -> tuple[float | None, int]:
    """Inter-annotator agreement over items labelled by >=2 annotators.

    ``annotations``: annotator -> {item_id: label}. Returns (mean pairwise kappa, items compared).
    With fewer than two annotators there is no agreement to compute -> ``None``; we never
    claim consensus from a single annotator.
    """
    annotators = sorted(annotations)
    if len(annotators) < 2:
        return None, 0
    kappas: list[float] = []
    shared_total: set[str] = set()
    for x, y in combinations(annotators, 2):
        shared = sorted(set(annotations[x]) & set(annotations[y]))
        if len(shared) < 2:
            continue
        shared_total.update(shared)
        kappas.append(cohens_kappa([annotations[x][i] for i in shared], [annotations[y][i] for i in shared]))
    if not kappas:
        return None, 0
    return sum(kappas) / len(kappas), len(shared_total)


def find_disagreements(annotations: dict[str, dict[str, bool]]) -> dict[str, dict[str, bool]]:
    """Items where annotators disagree -> {item_id: {annotator: label}} (the adjudication queue)."""
    by_item: dict[str, dict[str, bool]] = defaultdict(dict)
    for who, labels in annotations.items():
        for item, lab in labels.items():
            by_item[item][who] = lab
    return {i: v for i, v in by_item.items() if len(v) >= 2 and len(set(v.values())) > 1}
