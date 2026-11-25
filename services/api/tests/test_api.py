def test_health_ready_meta(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json()["database"] == "ok"
    m = client.get("/api/meta").json()
    assert m["demo_mode"] is True and "SYNTHETIC" in m["synthetic_notice"]


def test_openapi_has_typed_schemas(client):
    spec = client.get("/openapi.json").json()
    assert {"RunOut", "ComparisonDetail", "JudgeOut", "SampleDetail", "TraceOut", "BlindItem"} <= set(
        spec["components"]["schemas"]
    )


def test_overview_tells_the_story(client):
    o = client.get("/api/overview").json()
    assert o["headline"]["decision"] == "significant_improvement" and o["gate"]["verdict"] == "pass"
    assert "Localized regression: 'address'" in o["what_changed"]
    assert o["kpis"]["candidate"]["task_success"]["rate"] > o["kpis"]["baseline"]["task_success"]["rate"]
    assert o["trend"] and o["failure_categories"]


def test_comparison_states_and_validity(client):
    comps = {c["name"]: c for c in client.get("/api/comparisons").json()}
    assert comps["Support v1 vs v2 on a DIFFERENT dataset version"]["decision"] == "invalid"
    prod = comps["Support v1 → v2 (production policy, min 50 cases)"]
    assert prod["decision"] == "inconclusive" and prod["n_common_cases"] == 30
    det = client.get(f"/api/comparisons/{prod['id']}").json()
    assert det["baseline"]["agent_version"] == "v1" and det["candidate"]["agent_version"] == "v2"
    invalid = client.get(f"/api/comparisons/{comps['Support v1 vs v2 on a DIFFERENT dataset version']['id']}").json()
    assert any("dataset_mismatch" in r for r in invalid["validity"]["reasons"])


def test_case_comparison_shows_changed_arguments(client):
    cid = next(c["id"] for c in client.get("/api/comparisons").json() if c["name"] == "Support v1 → v2")
    d = client.get(f"/api/comparisons/{cid}/cases/sup-17-address-unit-apt").json()
    assert d["diff"]["changed_arguments"][0]["candidate"]["city"] == "Apt 5"
    assert d["diff"]["changed_outcome"] and d["expected_assertions"]


def test_execution_error_is_distinct_from_failure(client):
    smp = client.get("/api/runs/demo-research-v2/samples?status=execution_error").json()
    assert smp["total"] >= 1 and smp["items"][0]["error_kind"] == "provider"
    one = client.get(f"/api/samples/{smp['items'][0]['id']}").json()
    assert "NOT counted as a quality failure" in one["status_explanation"]


def test_trace_tree(client):
    sid = client.get("/api/runs/demo-support-v2/samples?case=sup-01-refund-eligible-simple").json()["items"][0]["id"]
    t = client.get(f"/api/samples/{sid}/trace").json()
    kinds = {s["kind"] for s in t["spans"]}
    assert {"agent", "model", "tool"} <= kinds and t["trajectory"][0] == "lookup_order"
    root = next(s for s in t["spans"] if s["parent_id"] is None)
    assert root["attributes"]["gen_ai.operation.name"] == "invoke_agent"
    # observable evidence only: tool args/results are present, no reasoning content is stored anywhere
    assert not any("reasoning" in k or "thought" in k for sp in t["spans"] for k in sp["attributes"])


def test_judges_calibrated_vs_not(client):
    js = client.get("/api/judges").json()
    by_model = {(j["model"], j["rubric_version"]): j for j in js}
    assert by_model[("keyword-strict-v1", "r1")]["status_label"].startswith("ADMITTED ON DEMONSTRATION LABELS")
    assert by_model[("keyword-lenient-v0", "r1")]["status"] == "not_calibrated"
    assert "never calibrated" in by_model[("keyword-strict-v1", "r2")]["status_label"]
    strict = by_model[("keyword-strict-v1", "r1")]
    assert len(strict["history"]) == 2 and strict["history"][0]["admitted"] and not strict["history"][1]["admitted"]
    assert strict["latest"]["metrics"]["kappa"] >= 0.6 and strict["latest"]["metrics"]["fpr"] <= 0.05


def test_gate_blocks_uncalibrated_judge(client):
    g = client.get("/api/gates").json()
    assert any(not x["judge_ok"] and x["verdict"] == "fail" for x in g)
    assert {x["verdict"] for x in g} == {"pass", "fail"}


def test_blind_annotation_never_leaks_labels(client):
    item = client.get("/api/annotation/next?annotator=alice").json()
    assert set(item) == {"item_id", "input", "candidate_output", "rubric"}
    assert client.post(
        "/api/annotation", json={"item_id": item["item_id"], "annotator": "alice", "label": True}
    ).json()["ok"]
    nxt = client.get("/api/annotation/next?annotator=alice").json()
    assert nxt["item_id"] != item["item_id"]
    assert (
        client.post(
            "/api/annotation", json={"item_id": "cal-02a", "annotator": "demo-annotator-a", "label": True}
        ).status_code
        == 422
    )
    s = client.get("/api/annotation/summary").json()
    assert s["consensus_claimed"] and "synthetic_demo" in s["sources"] and s["disagreement_queue"]


def test_single_annotator_claims_no_consensus(client):
    # only one annotator labels this fresh set of items -> agreement is computed over demo pairs, never alice alone
    assert client.get("/api/annotation/progress?annotator=alice").json()["total"] == 60


def test_mutations_blocked_in_demo_mode(client):
    assert client.post("/api/runs", json={"agent": "support:v1", "dataset": "support:v1"}).status_code == 403
    assert client.post("/api/judges/1/calibrate").status_code == 403
    assert client.post("/api/comparisons", json={"baseline_run_id": "a", "candidate_run_id": "b"}).status_code == 403


def test_pagination_and_filters(client):
    r = client.get("/api/runs?page_size=2&page=2").json()
    assert len(r["items"]) == 2 and r["total"] >= 11 and r["page"] == 2
    assert all(x["agent"] == "coding" for x in client.get("/api/runs?agent=coding").json()["items"])


def test_failures_report_increase_vs_baseline(client):
    f = client.get("/api/failures?run_id=demo-support-v2&baseline_run_id=demo-support-v1").json()
    wta = next(c for c in f["clusters"] if c["label"] == "wrong_tool_arguments")
    assert wta["increased"] and wta["examples"] and "increased" in f["summary"]


def test_dataset_exposes_frozen_state(client):
    ds = {(d["dataset"], d["version"]): d for d in client.get("/api/datasets").json()}
    assert ds[("support", "v1")]["published"] and not ds[("support", "v2")]["published"]
    assert ds[("support", "v1")]["hash"] != ds[("support", "v2")]["hash"]
    detail = client.get("/api/datasets/support/v1").json()
    assert detail["case_count"] == len(detail["cases"]) == 30 and detail["cases"][0]["definition"]["assertions"]


def test_unknown_resources_404(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/comparisons/9999").status_code == 404


def test_annotations_are_append_only_and_adjudication_is_guarded(client):
    ok = client.post("/api/annotation", json={"item_id": "cal-03a", "annotator": "bob", "label": True})
    assert ok.status_code == 200
    # impersonation / tampering: the same annotator id cannot overwrite an existing label
    assert (
        client.post("/api/annotation", json={"item_id": "cal-03a", "annotator": "bob", "label": False}).status_code
        == 409
    )
    # a skipped item can still be filled in later
    assert (
        client.post("/api/annotation", json={"item_id": "cal-03b", "annotator": "bob", "label": None}).status_code
        == 200
    )
    assert (
        client.post("/api/annotation", json={"item_id": "cal-03b", "annotator": "bob", "label": True}).status_code
        == 200
    )
    adj = {"item_id": "cal-03a", "adjudicator": "carol", "label": True}
    assert client.post("/api/annotation/adjudicate", json=adj).status_code == 200
    assert client.post("/api/annotation/adjudicate", json=adj).status_code == 409
    assert client.post("/api/annotation/adjudicate", json={**adj, "adjudicator": "demo-annotator-a"}).status_code == 422


def test_annotator_id_rejects_trailing_newline_and_bad_chars(client):
    for bad in ["alice\n", "a", "a" * 41, "bad id", "ünï", "x;drop"]:
        r = client.post("/api/annotation", json={"item_id": "cal-04a", "annotator": bad, "label": True})
        assert r.status_code == 422, bad
        r = client.post("/api/annotation/adjudicate", json={"item_id": "cal-04a", "adjudicator": bad, "label": True})
        assert r.status_code == 422, bad
    assert client.get("/api/annotation/next", params={"annotator": "alice\n"}).status_code == 422


def test_persisted_content_is_redacted_no_secret_in_database(seeded_db):
    # red-team v1 agents really leak the synthetic canary in their raw output; it must never reach storage
    from app.db import session_scope
    from app.models import AssertionResultRow, Sample, SpanRow
    from sqlalchemy import select

    with session_scope() as s:
        leaked = []
        for model, cols in (
            (Sample, ("input_text", "final_output", "result")),
            (AssertionResultRow, ("evidence", "actual", "expected")),
            (SpanRow, ("attributes",)),
        ):
            for row in s.scalars(select(model)):
                if any("DEMO_SECRET_DO_NOT_REVEAL" in str(getattr(row, c)) for c in cols):
                    leaked.append(model.__name__)
        assert leaked == []
