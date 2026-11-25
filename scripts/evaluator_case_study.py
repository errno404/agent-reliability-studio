#!/usr/bin/env python3
"""Evaluator validation case study: where does a naive lexical evaluator go wrong, and what does stronger DETERMINISTIC scoring fix?

Items are TEMPLATED by the project author from invented facts (8 entities x 8 output classes = 64 outputs). Reference labels are
AUTHOR labels (``label_source: synthetic_fixture``): this is NOT human adjudication and the numbers are NOT a prevalence estimate.
It demonstrates failure classes and what each evaluator does with them. Because the stronger scorer was designed by the same author
who wrote the items, its accuracy here is optimistic by construction; see docs/EVALUATOR_CASE_STUDY.md.

Evaluators compared
  A  naive lexical      pass iff the expected figure appears anywhere (substring)               <- what a quick ``output_contains`` does
  B  keyword judge      evalcore.judge.HeuristicJudge (MUST/MUST_NOT token coverage; the synthetic calibration judge)
  C  stronger scoring   asserted-value extraction: boundary-safe numbers + spelled-out numbers, attribute proximity, negation and
                        attribution (claim/rumour/blog) scopes, forbidden-value check, completeness of required facts

Usage:  python scripts/evaluator_case_study.py                      # print + write evidence/evaluator-study/results.json
        python scripts/evaluator_case_study.py --export-annotation-set datasets/evaluator-study/annotation-v1.yaml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/evalcore/src"))

from evalcore.judge import HeuristicJudge  # noqa: E402
from evalcore.stats import wilson_interval  # noqa: E402

# entity, attribute question, keywords naming the attribute, correct figure, spelled-out form, decoy figure, other-attribute sentence
# (figure inside it is the CORRECT figure used for a different attribute), second attribute (question, keywords, figure)
FACTS = [
    dict(ent="Harlow Rail", q="the size of the Harlow Rail fleet", kw=("fleet", "trains"), val="62", words="sixty-two", decoy="70", unit="trains",
         other="Harlow Rail serves 62 stations spread across its wider network and several regional branch lines nationwide.",
         q2="the maximum service speed of Harlow Rail trains", kw2=("speed",), val2="187"),
    dict(ent="Pelham Public Library", q="the number of volumes held by Pelham Public Library", kw=("volumes", "collection", "holds"), val="2,310,000",
         words="two million three hundred ten thousand", decoy="3,000,000", unit="volumes",
         other="Pelham Public Library welcomed 2,310,000 visitors across all of its busy reading rooms and event spaces last year.",
         q2="the number of branches of the Pelham library system", kw2=("branches",), val2="17"),
    dict(ent="Tarn Wind Farm", q="the number of turbines at Tarn Wind Farm", kw=("turbines",), val="48", words="forty-eight", decoy="36", unit="turbines",
         other="Tarn Wind Farm generates 48 gigawatt-hours during each of its windiest winter months according to site engineers.",
         q2="the installed capacity of Tarn Wind Farm", kw2=("capacity",), val2="144"),
    dict(ent="Vesper General Hospital", q="the number of beds at Vesper General Hospital", kw=("beds",), val="620", words="six hundred twenty",
         decoy="800", unit="beds",
         other="Vesper General Hospital treated 620 patients in its emergency department on the busiest single weekend of the year.",
         q2="the number of operating theatres at Vesper General Hospital", kw2=("theatres",), val2="14"),
    dict(ent="Calder Bridge", q="the length of Calder Bridge in metres", kw=("length", "long", "metres"), val="1,240", words="one thousand two hundred forty",
         decoy="1,190", unit="metres",
         other="Calder Bridge carries 1,240 vehicles through the crossing in the single hour of the heaviest weekday morning peak.",
         q2="the opening year of Calder Bridge", kw2=("opened",), val2="2009"),
    dict(ent="Ondra Probe", q="the launch mass of the Ondra Probe in kilograms", kw=("mass", "kilograms", "weighed"), val="1,850",
         words="one thousand eight hundred fifty", decoy="2,400", unit="kilograms",
         other="The Ondra Probe team numbered 1,850 engineers, technicians and contractors at the peak of the integration campaign.",
         q2="the number of instruments on the Ondra Probe", kw2=("instruments",), val2="6"),
    dict(ent="Mireth University", q="the number of students at Mireth University", kw=("students", "enrolment"), val="18,400",
         words="eighteen thousand four hundred", decoy="25,000", unit="students",
         other="Mireth University received 18,400 applications for its undergraduate programmes during the most recent admissions season.",
         q2="the number of campuses of Mireth University", kw2=("campuses",), val2="3"),
    dict(ent="Lumen Cloud", q="the number of regions in which Lumen Cloud operates", kw=("regions",), val="9", words="nine", decoy="14", unit="regions",
         other="Lumen Cloud documentation lists 9 certified partner programmes for resellers, integrators and managed service providers worldwide.",
         q2="the monthly uptime SLA of Lumen Cloud", kw2=("uptime", "sla"), val2="99.95"),
]

PASS_CLASSES = ("valid", "valid_spelled_out", "valid_refutes_decoy")
CLASSES = {
    "valid": lambda f: f"{f['ent']} has {f['val']} {f['unit']}, according to the official fact sheet.",
    "valid_spelled_out": lambda f: f"The count for {f['ent']} is {f['words']} {f['unit']}.",
    "valid_refutes_decoy": lambda f: f"A fan blog claims {f['decoy']} {f['unit']}, but the official figure for {f['ent']} is {f['val']} {f['unit']}.",
    "unsupported_figure": lambda f: f"{f['ent']} has {f['decoy']} {f['unit']}, according to its fact sheet.",
    "negated_correct_figure": lambda f: f"It is not true that {f['ent']} has {f['val']} {f['unit']}; the real number is {f['decoy']}.",
    "misleading_keyword_overlap": lambda f: f"{f['other']} The {f['kw'][0]} figure was not stated in the sources I checked.",
    "incomplete_answer": lambda f: f"{f['ent']} has {f['val']} {f['unit']}.",  # question asks for BOTH facts; only one is given
    "irrelevant_but_plausible": lambda f: f"{f['ent']} is a well-regarded organisation, and many similar bodies are investing in modernisation and visitor experience.",
}  # fmt: skip
TWO_PART = {"incomplete_answer"}  # these items ask for both attributes


@dataclass
class Item:
    id: str
    cls: str
    question: str
    output: str
    must: list[str]  # required figures
    must_not: list[str]
    kws: list[tuple[str, ...]]
    label: bool  # reference label (author): True = should pass


def build() -> list[Item]:
    items: list[Item] = []
    for i, f in enumerate(FACTS):
        for cls, make in CLASSES.items():
            two = cls in TWO_PART
            q = f"What is {f['q']}" + (f" and {f['q2']}?" if two else "?")
            items.append(
                Item(
                    id=f"es-{i + 1:02d}-{cls}",
                    cls=cls,
                    question=q,
                    output=make(f),
                    must=[f["val"], f["val2"]] if two else [f["val"]],
                    must_not=[f["decoy"]],
                    kws=[f["kw"], f["kw2"]] if two else [f["kw"]],
                    label=cls in PASS_CLASSES,
                )
            )
    return items


# ------------------------------------------------------------------------------------------------- evaluators
def eval_a(it: Item) -> bool:
    """Naive lexical: any required figure appears as a substring."""
    return any(m.lower() in it.output.lower() for m in it.must)


def eval_b(it: Item) -> bool:
    """The repository's synthetic keyword judge (MUST / MUST_NOT coverage)."""
    rubric = "\n".join([f"MUST: {m}" for m in it.must] + [f"MUST_NOT: {m}" for m in it.must_not])
    prompt = f"RUBRIC\n{rubric}\nINPUT: {it.question}\nCANDIDATE OUTPUT: {it.output}"
    return bool(json.loads(HeuristicJudge(strictness=0.6).complete(prompt))["passed"])


_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_NUM = re.compile(r"(?<![\w.,])\d[\d,]*(?:\.\d+)?(?![\w])")
_WORDNUM = re.compile(r"\b((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|and)(?:[- ]|\b))+)", re.I)
NEG = re.compile(r"\b(not|isn't|aren't|wasn't|never|no longer|incorrect|false|untrue|wrongly|myth)\b", re.I)
ATTRIB = re.compile(r"\b(claims?|claimed|rumou?rs?|alleges?|alleged|blog|unofficial|reportedly|supposedly|some say)\b", re.I)


def words_to_int(s: str) -> int | None:
    total, cur = 0, 0
    seen = False
    for w in re.split(r"[-\s]+", s.lower().strip()):
        if w in ("and", ""):
            continue
        if w in _ONES:
            cur += _ONES[w]
        elif w in _TENS:
            cur += _TENS[w]
        elif w == "hundred":
            cur = max(cur, 1) * 100
        elif w == "thousand":
            total += max(cur, 1) * 1000
            cur = 0
        elif w == "million":
            total += max(cur, 1) * 1_000_000
            cur = 0
        else:
            return None
        seen = True
    return (total + cur) if seen else None


def numbers(text: str) -> list[tuple[str, int, int]]:
    """(canonical value, start, end) for digit numbers and spelled-out numbers."""
    out = [(m.group(0).replace(",", ""), m.start(), m.end()) for m in _NUM.finditer(text)]
    for m in _WORDNUM.finditer(text):
        v = words_to_int(m.group(1))
        if v is not None:
            out.append((str(v), m.start(), m.end()))
    return out


def asserted_values(text: str, kws: tuple[str, ...], window: int = 60) -> set[str]:
    """Figures the output ASSERTS for the attribute named by ``kws``: near an attribute keyword, not negated, not merely attributed."""
    low = text.lower()
    res: set[str] = set()
    for val, s, e in numbers(text):
        near = any(k in low[max(0, s - window): e + window] for k in kws)
        before = text[max(0, s - 45): s]
        negated = bool(NEG.search(before))
        prefix = text[max(0, s - 60): s]
        cues = list(ATTRIB.finditer(prefix))
        # attributed to someone else ("a blog claims 70") unless a correction cue sits between the attribution and the figure
        attributed = bool(cues) and not re.search(r"\b(but|however|actual(ly)?|official|real)\b", prefix[cues[-1].end():], re.I)
        if near and not negated and not attributed:
            res.add(val)
    return res


def eval_c(it: Item) -> bool:
    for fig, kws in zip(it.must, it.kws, strict=True):
        got = asserted_values(it.output, kws)
        if fig.replace(",", "") not in got:
            return False  # required figure not asserted for its attribute (missing / negated / wrong attribute / only attributed)
        if any(m.replace(",", "") in got for m in it.must_not):
            return False  # asserts the forbidden figure too
    return True


EVALUATORS = {"A_naive_lexical": eval_a, "B_keyword_judge": eval_b, "C_stronger_deterministic": eval_c}


# STRESS SET: written AFTER evaluator C was frozen and never used to adjust it. Same question for all: "What is the size of the Harlow
# Rail fleet?" (correct figure 62, decoy 70). Labels are the author's judgement of what a careful human grader would decide.
_STRESS = [
    ("Fleet: 62 trains.", True, "terse format"),
    ("Roughly sixty trains, give or take.", False, "approximate, wrong figure"),
    ("It has 62 trains. Just kidding, it is 70.", False, "retraction / sarcasm"),
    ("Not 70 - the fleet is 62 trains.", True, "negates the decoy, asserts the truth"),
    ("The fleet is about 62 trains.", True, "hedged but correct"),
    ("There are 620 trains in the fleet.", False, "digit superstring"),
    ("62.5 trains make up the fleet.", False, "decimal near-miss"),
    ("62 of the trains in the fleet are electric.", False, "figure belongs to a sub-population"),
    ("The fleet will grow to 70 trains next year; today it has 62 trains.", True, "future decoy plus current truth"),
    ("I could not verify the fleet size; some say 62 trains, others 70.", False, "refuses to commit"),
    ("Sixty two trains operate in the fleet.", True, "spelled out with a space"),
    ("The fleet had 62 trains in 2015 but the figure is outdated and the fleet is now 70 trains.", False, "stale correct figure"),
]


def stress_items() -> list[Item]:
    f = FACTS[0]
    return [
        Item(f"stress-{i + 1:02d}", note, "What is the size of the Harlow Rail fleet?", out, [f["val"]], [f["decoy"]], [f["kw"]], lab)
        for i, (out, lab, note) in enumerate(_STRESS)
    ]


def confusion(items: list[Item], fn) -> dict:  # noqa: ANN001
    tp = fp = tn = fn_ = 0
    errors = []
    for it in items:
        pred = fn(it)
        if pred and it.label:
            tp += 1
        elif pred and not it.label:
            fp += 1
            errors.append({"id": it.id, "class": it.cls, "kind": "false_pass", "output": it.output})
        elif not pred and not it.label:
            tn += 1
        else:
            fn_ += 1
            errors.append({"id": it.id, "class": it.cls, "kind": "false_fail", "output": it.output})
    neg, pos = tn + fp, tp + fn_
    fpr_lo, fpr_hi = wilson_interval(fp, neg) if neg else (None, None)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn_,
        "accuracy": (tp + tn) / len(items),
        "false_pass_rate": fp / neg if neg else None, "false_pass_rate_wilson95": [fpr_lo, fpr_hi],
        "false_fail_rate": fn_ / pos if pos else None,
        "errors": errors,
    }  # fmt: skip


def by_class(items: list[Item], fn) -> dict[str, dict]:  # noqa: ANN001
    out = {}
    for cls in CLASSES:
        sub = [i for i in items if i.cls == cls]
        ok = sum(1 for i in sub if fn(i) == i.label)
        out[cls] = {"n": len(sub), "correct": ok, "label": "pass" if sub[0].label else "fail"}
    return out


def export_annotation_set(items: list[Item], path: Path) -> None:
    import yaml

    doc = {
        "name": "evaluator-study", "version": "v1", "dimension": "factual_correctness", "published": True,
        "description": "64 templated outputs for BLIND human annotation. reference_label is the AUTHOR's label (synthetic_fixture), "
        "to be compared with independent human labels; it is NOT human evidence.",
        "items": [
            {"id": i.id, "input": i.question,
             "rubric": {"must": [f"{m}" for m in i.must], "must_not": i.must_not},
             "label_source": "synthetic_fixture", "candidate_output": i.output,
             "reference_label": "pass" if i.label else "fail", "notes": i.cls}
            for i in items
        ],
    }  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=120, allow_unicode=True))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-annotation-set", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/evaluator-study/results.json")
    a = ap.parse_args()
    items = build()
    if a.export_annotation_set:
        export_annotation_set(items, a.export_annotation_set)
        print(f"wrote {len(items)} items to {a.export_annotation_set}")
        return 0
    result = {
        "note": "Author-labelled templated items; NOT human adjudication; not a prevalence estimate.",
        "n_items": len(items), "n_should_pass": sum(i.label for i in items), "n_should_fail": sum(not i.label for i in items),
        "evaluators": {}, "by_class": {},
    }  # fmt: skip
    for name, fn in EVALUATORS.items():
        result["evaluators"][name] = confusion(items, fn)
        result["by_class"][name] = by_class(items, fn)
    stress = stress_items()
    result["stress_set"] = {
        "note": "12 phrasings written AFTER evaluator C was frozen; C was not modified to fit them.",
        "evaluators": {n: confusion(stress, fn) for n, fn in EVALUATORS.items()},
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for name, c in result["evaluators"].items():
        print(f"{name:28s} acc={c['accuracy']:.3f}  false-pass={c['fp']}/{c['fp'] + c['tn']}  false-fail={c['fn']}/{c['tp'] + c['fn']}")
    print("-- stress set (12 phrasings, written after C was frozen)")
    for name, c in result["stress_set"]["evaluators"].items():
        print(f"{name:28s} acc={c['accuracy']:.3f}  false-pass={c['fp']}  false-fail={c['fn']}  errors={[e['id'] for e in c['errors']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
