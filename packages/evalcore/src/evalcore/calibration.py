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
    # RELEASE scope: the point estimate above is not enough on a small set (0 false positives on 30 negatives is still
    # consistent with a true FPR near 11%), so release eligibility also bounds the Wilson upper limit of the FPR.
    max_fpr_upper: float = 0.10
    min_trusted_items: int = 50  # labels from humans/adjudication required for RELEASE admission
    version: str = "adm-2"

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


def judge_identity(backend: str, model: str, prompt_hash: str, config_hash: str = "") -> str:
    """Identity of a judge = everything that can change its verdicts.

    ``config_hash`` must cover generation settings (temperature, ...), rubric contents/version, parser/scoring version and,
    where the provider reports it, the resolved model. Any change => a NEW identity => a new calibration is required, so a
    materially different configuration can never inherit an admission."""
    return hash_obj({"backend": backend, "model": model, "prompt_hash": prompt_hash, "config": config_hash}, 16)


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


TRUSTED_SOURCES = ("human", "adjudicated")


def fpr_upper_bound(metrics: CalibrationMetrics) -> float:
    """95% Wilson upper bound on the false-positive rate."""
    from .stats import wilson_interval

    n_neg = metrics.fp + metrics.tn
    return wilson_interval(metrics.fp, n_neg)[1] if n_neg else 1.0


@dataclass(frozen=True)
class ReleaseEligibility:
    eligible: bool
    scope: str  # "release" | "demonstration" | "diagnostic"
    reasons: list[str]
    fpr_upper: float


def release_eligibility(
    decision_admitted: bool, metrics: CalibrationMetrics, sources: dict[str, int], policy: AdmissionPolicy | None = None
) -> ReleaseEligibility:
    """Is this calibration strong enough to authorise RELEASE decisions?

    Requires: the standard admission, enough TRUSTED (human/adjudicated) labels, and a confidence bound on false positives.
    ``synthetic_fixture`` labels can demonstrate the workflow ("demonstration") but never authorise a release.
    """
    pol = policy or AdmissionPolicy()
    ub = fpr_upper_bound(metrics)
    trusted = sum(sources.get(k, 0) for k in TRUSTED_SOURCES)
    why: list[str] = []
    if not decision_admitted:
        why.append("judge is not admitted by the standard policy")
    if trusted < pol.min_trusted_items:
        why.append(
            f"only {trusted} human/adjudicated reference labels (release needs >= {pol.min_trusted_items}); "
            f"{sources.get('synthetic_fixture', 0)} labels are synthetic fixtures"
        )
    if ub > pol.max_fpr_upper:
        why.append(
            f"95% upper bound on the false-positive rate is {ub:.1%} (release needs <= {pol.max_fpr_upper:.0%}); "
            f"a low point estimate on {metrics.fp + metrics.tn} negatives is weak evidence"
        )
    scope = "release" if not why else ("demonstration" if decision_admitted else "diagnostic")
    return ReleaseEligibility(not why, scope, why, ub)
