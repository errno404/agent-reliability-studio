import copy
import json
from pathlib import Path

from evalcore import SampleStatus, summarize

from integrations.inspect_ai import ingest_inspect_log, research_cases_as_samples

FIX = Path(__file__).parent / "fixtures" / "research_v2_inspect_log.json"


def test_ingest_real_inspect_log():
    man, samples = ingest_inspect_log(FIX)
    assert man.run_type == "inspect_import" and man.agent == "ars-research-v2" and man.samples_per_case == 2
    assert len(samples) == 12 and {s.sample_index for s in samples} == {0, 1}
    assert all(s.status == SampleStatus.PASSED for s in samples)
    assert samples[0].assertions[0].name == "inspect:contains_all" and samples[0].result.final_output
    assert summarize(samples)["task_success"]["rate"] == 1.0


def test_errors_are_execution_errors_and_wrong_answers_are_failures():
    log = json.loads(FIX.read_text())
    bad = copy.deepcopy(log)
    bad["samples"][0]["error"] = {"message": "provider 500", "traceback": "", "traceback_ansi": ""}
    for score in bad["samples"][1]["scores"].values():
        score["value"] = "I"
    _, samples = ingest_inspect_log(bad)
    assert samples[0].status == SampleStatus.EXECUTION_ERROR and samples[0].failure_labels == ["execution_error"]
    assert samples[1].status == SampleStatus.FAILED
    s = summarize(samples)
    assert s["status_counts"]["execution_error"] == 1 and s["task_success"]["n"] == 11  # error excluded from quality


def test_export_samples_are_plain_and_carry_dataset_hash():
    rows = research_cases_as_samples()
    assert len(rows) == 20 and rows[0]["target"] == ["240 passengers"]
    assert (
        rows[0]["metadata"]["dataset_hash"] and not rows[-1]["metadata"]["executable"]
    )  # the mcp_down case is flagged
