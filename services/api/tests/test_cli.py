from app.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_dataset_validate_ok_and_bad(tmp_path):
    ok = runner.invoke(app, ["dataset", "validate", "datasets/support/v1.yaml"])
    assert ok.exit_code == 0 and "PUBLISHED" in ok.output
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\nversion: v1\ncases:\n  - {id: a, title: t, category: c, assertions: []}\n")
    r = runner.invoke(app, ["dataset", "validate", str(bad)])
    assert r.exit_code == 1 and "description" in r.output


def test_compare_exit_codes(seeded_db):
    ok = runner.invoke(
        app,
        [
            "eval",
            "compare",
            "--baseline",
            "demo-support-v1",
            "--candidate",
            "demo-support-v2",
            "--policy",
            "demo-20",
            "--database-url",
            seeded_db,
        ],
    )
    assert ok.exit_code == 0 and "SIGNIFICANT_IMPROVEMENT" in ok.output
    reg = runner.invoke(
        app,
        [
            "eval",
            "compare",
            "--baseline",
            "demo-support-v2",
            "--candidate",
            "demo-support-v1",
            "--policy",
            "demo-20",
            "--database-url",
            seeded_db,
        ],
    )
    assert reg.exit_code == 1 and "SIGNIFICANT_REGRESSION" in reg.output
    inv = runner.invoke(
        app,
        [
            "eval",
            "compare",
            "--baseline",
            "demo-support-v1",
            "--candidate",
            "demo-support-v2-draftds",
            "--database-url",
            seeded_db,
        ],
    )
    assert inv.exit_code == 2 and "INVALID" in inv.output
    inc = runner.invoke(
        app,
        [
            "eval",
            "compare",
            "--baseline",
            "demo-coding-v1",
            "--candidate",
            "demo-coding-v2",
            "--policy",
            "demo-20",
            "--database-url",
            seeded_db,
        ],
    )
    assert inc.exit_code == 3


def test_judge_calibrate_exit_codes(seeded_db):
    assert (
        runner.invoke(
            app, ["judge", "calibrate", "--judge", "keyword-strict-v1", "--database-url", seeded_db]
        ).exit_code
        == 0
    )
    bad = runner.invoke(app, ["judge", "calibrate", "--judge", "keyword-lenient-v0", "--database-url", seeded_db])
    assert bad.exit_code == 1 and "NOT CALIBRATED" in bad.output


def test_demo_verify_and_diff(seeded_db):
    assert runner.invoke(app, ["demo", "verify", "--database-url", seeded_db]).exit_code == 0
    d = runner.invoke(app, ["eval", "diff", "demo-support-v1", "demo-support-v2", "--database-url", seeded_db])
    assert d.exit_code == 0 and "differ" in d.output


def test_distill_writes_candidates_not_dataset(seeded_db, tmp_path):
    r = runner.invoke(
        app, ["traces", "distill", "demo-support-v2", "--out", str(tmp_path), "--database-url", seeded_db]
    )
    assert r.exit_code == 0
    files = list(tmp_path.glob("candidate-*.yaml"))
    assert files and "candidate" in files[0].read_text() and "NEEDS HUMAN REVIEW" in files[0].read_text()
