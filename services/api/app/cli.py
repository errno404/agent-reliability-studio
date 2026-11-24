"""`ars` command line interface. Calls the same service layer as the API and worker.

Exit codes for `ars eval compare` / `ars gate check`:  0 pass/improvement/no-meaningful-regression,
1 regression, 2 invalid comparison, 3 inconclusive (conservative policy), 4 usage/runtime error.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from evalcore import load_and_validate
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from .config import REPO_ROOT, get_settings
from .db import get_engine, reset_engine, session_scope
from .models import Base, JudgeConfig, Run, Sample
from .services import catalog, comparisons, jobs
from .services import judges as judge_svc
from .services import runs as run_svc

app = typer.Typer(
    help="Agent Reliability Studio - evaluation infrastructure for tool-using agents.", no_args_is_help=True
)
demo = typer.Typer(help="Seed and verify the zero-key synthetic demo.", no_args_is_help=True)
dataset = typer.Typer(help="Validate and hash golden datasets.", no_args_is_help=True)
evalcmd = typer.Typer(help="Run, compare and diff evaluations.", no_args_is_help=True)
judge = typer.Typer(help="Calibrate and inspect LLM judges.", no_args_is_help=True)
traces = typer.Typer(help="Trace utilities.", no_args_is_help=True)
db = typer.Typer(help="Database lifecycle.", no_args_is_help=True)
gatecmd = typer.Typer(help="CI release gate.", no_args_is_help=True)
for name, t in (
    ("demo", demo),
    ("dataset", dataset),
    ("eval", evalcmd),
    ("judge", judge),
    ("traces", traces),
    ("db", db),
    ("gate", gatecmd),
):
    app.add_typer(t, name=name)
console = Console()
DbOpt = Annotated[str | None, typer.Option("--database-url", help="Override DATABASE_URL")]

EXIT = {
    "significant_improvement": 0,
    "no_meaningful_regression": 0,
    "significant_regression": 1,
    "invalid": 2,
    "inconclusive": 3,
}


def _setup(database_url: str | None) -> None:
    if database_url:
        reset_engine(database_url)
    ensure_schema()


def ensure_schema() -> None:
    """Apply migrations if Alembic is configured, else create tables (tests / throwaway DBs)."""
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(REPO_ROOT / "services/api/alembic.ini"))
        cfg.set_main_option("script_location", str(REPO_ROOT / "services/api/alembic"))
        cfg.set_main_option(
            "sqlalchemy.url", str(get_engine().url.render_as_string(hide_password=False)).replace("%", "%%")
        )
        command.upgrade(cfg, "head")
    except Exception:
        Base.metadata.create_all(get_engine())


# ----------------------------------------------------------------------------- db / demo
@db.command("upgrade")
def db_upgrade(database_url: DbOpt = None) -> None:
    """Apply Alembic migrations (idempotent)."""
    if database_url:
        reset_engine(database_url)
    ensure_schema()
    console.print("[green]database is at head[/green]")


@demo.command("seed")
def demo_seed(database_url: DbOpt = None) -> None:
    """Seed the synthetic demo (idempotent: safe to run twice)."""
    from .seed import seed_all

    _setup(database_url)
    t0 = time.time()
    with session_scope() as s:
        out = seed_all(s)
    console.print(
        f"[green]demo seeded[/green] {out} in {time.time() - t0:.1f}s  [dim](synthetic fixture evidence)[/dim]"
    )


@demo.command("verify")
def demo_verify(database_url: DbOpt = None) -> None:
    """Check the seeded demo for the invariants the product story depends on."""
    from .verify import verify_demo

    _setup(database_url)
    with session_scope() as s:
        problems, checks = verify_demo(s)
    for c in checks:
        console.print(("[green]ok  [/green]" if c[1] else "[red]FAIL[/red]"), c[0])
    if problems:
        raise typer.Exit(1)
    console.print(f"[green]{len(checks)} checks passed[/green]")


# --------------------------------------------------------------------------- dataset
@dataset.command("validate")
def dataset_validate(path: Path) -> None:
    """Validate a dataset file and print its content hash."""
    from evalcore.dataset import DatasetError

    try:
        ds, h = load_and_validate(path)
    except DatasetError as exc:
        for p in exc.problems:
            console.print(f"[red]x[/red] {p}")
        raise typer.Exit(1) from exc
    cats: dict[str, int] = {}
    for c in ds.cases:
        cats[c.category] = cats.get(c.category, 0) + 1
    console.print(
        f"[green]valid[/green] {ds.name}:{ds.version}  cases={len(ds.cases)}  hash={h}  "
        f"{'PUBLISHED (frozen)' if ds.published else 'draft'}  fixture={ds.fixture_version}"
    )
    console.print("categories: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))


@dataset.command("sync")
def dataset_sync(path: Path, database_url: DbOpt = None) -> None:
    """Register a dataset version in the database (refuses to change a published version)."""
    _setup(database_url)
    with session_scope() as s:
        dv = catalog.sync_dataset(s, path)
        console.print(f"synced {dv.dataset.name}:{dv.version} hash={dv.hash}")


# ------------------------------------------------------------------------------ eval
def _find_dv(s: Any, spec: str) -> Any:
    from .models import Dataset, DatasetVersion

    name, _, ver = spec.partition(":")
    dv = s.scalar(
        select(DatasetVersion).join(Dataset).where(Dataset.name == name, DatasetVersion.version == (ver or "v1"))
    )
    if dv is None:
        path = REPO_ROOT / f"datasets/{name}/{ver or 'v1'}.yaml"
        if path.exists():
            dv = catalog.sync_dataset(s, path)
        else:
            console.print(f"[red]unknown dataset {spec}[/red]")
            raise typer.Exit(4)
    return dv


@evalcmd.command("run")
def eval_run(
    agent: Annotated[str, typer.Option(help="e.g. support:v1")],
    dataset_: Annotated[str, typer.Option("--dataset", help="e.g. support:v1")],
    samples: int = 1,
    seed: int = 0,
    name: str | None = None,
    queue_only: bool = False,
    judge_name: str | None = None,
    database_url: DbOpt = None,
) -> None:
    """Run an evaluation now (or just queue it for the worker with --queue-only)."""
    _setup(database_url)
    with session_scope() as s:
        dv = _find_dv(s, dataset_)
        catalog.sync_agent_version(s, agent)
        jr = s.scalar(select(JudgeConfig).where(JudgeConfig.model == judge_name)) if judge_name else None
        rid = f"run-{run_svc.hash_of([agent, dataset_, samples, seed, time.time()])}"
        run = run_svc.create_run(
            s,
            run_id=rid,
            name=name or f"{agent} on {dataset_}",
            agent_spec=agent,
            dv=dv,
            samples=samples,
            seed=seed,
            run_type="live" if "synthetic" not in agent else "synthetic_demo",
            judge=jr,
            queue=queue_only,
        )
        run.run_type, run.is_synthetic = "synthetic_demo", True  # all bundled agents are synthetic
        if queue_only:
            console.print(f"queued {rid}")
            return
        run_svc.execute_run(s, run)
        sm = run.summary
        console.print(
            f"[green]{rid}[/green] {agent} on {dataset_}: success {sm['task_success']['rate']:.1%} "
            f"(n={sm['task_success']['n']}) pass^k={sm['pass_hat_k']:.2f} pass@k={sm['pass_at_k']:.2f} "
            f"exec_errors={sm['execution_error_rate']:.1%}"
        )


@evalcmd.command("compare")
def eval_compare(
    baseline: Annotated[str, typer.Option(help="baseline RUN_ID")],
    candidate: Annotated[str, typer.Option(help="candidate RUN_ID")],
    policy: str = "production",
    mode: str = "strict",
    conservative: bool = True,
    json_out: Path | None = None,
    database_url: DbOpt = None,
) -> None:
    """Statistically compare two runs and apply the release gate. See exit codes in `ars --help`."""
    _setup(database_url)
    with session_scope() as s:
        comp = comparisons.create_comparison(s, baseline, candidate, mode=mode, policy_name=policy)
        gate = comparisons.create_gate(s, comp, conservative)
        console.print(f"[bold]{comp.decision.upper()}[/bold]  gate={gate.verdict.upper()}")
        console.print(comp.explanation)
        for r in gate.reasons:
            console.print(f"  - {r}")
        if json_out:
            json_out.write_text(
                json.dumps(
                    {
                        "decision": comp.decision,
                        "gate": gate.verdict,
                        "reasons": gate.reasons,
                        "explanation": comp.explanation,
                        "result": comp.result,
                    },
                    indent=2,
                    default=str,
                )
            )
        decision = comp.decision
        failed = gate.verdict == "fail"
    code = EXIT[decision]
    raise typer.Exit(code if (failed or code in (1, 2)) else 0)


@evalcmd.command("diff")
def eval_diff(run_a: str, run_b: str, database_url: DbOpt = None) -> None:
    """Trajectory/outcome diff between two runs (first sample of every shared case)."""
    from evalcore.models import AgentResult
    from evalcore.trajectory import diff_trajectories

    _setup(database_url)
    with session_scope() as s:

        def first(rid: str) -> dict[str, Sample]:
            return {
                x.case_id: x for x in s.scalars(select(Sample).where(Sample.run_id == rid, Sample.sample_index == 0))
            }

        a, b = first(run_a), first(run_b)
        t = Table(title=f"{run_a} → {run_b}")
        for col in ("case", "A", "B", "trajectory change"):
            t.add_column(col)
        n = 0
        for cid in sorted(set(a) & set(b)):
            d = diff_trajectories(AgentResult.model_validate(a[cid].result), AgentResult.model_validate(b[cid].result))
            if a[cid].status != b[cid].status or not d["identical"]:
                n += 1
                t.add_row(
                    cid, a[cid].status, b[cid].status, " → ".join(d["baseline"]) + "  ⇒  " + " → ".join(d["candidate"])
                )
        console.print(t)
        console.print(f"{n} case(s) differ of {len(set(a) & set(b))} shared")


# ------------------------------------------------------------------------------ judge
@judge.command("calibrate")
def judge_calibrate(
    judge_model: Annotated[str, typer.Option("--judge", help="judge model name, e.g. keyword-strict-v1")],
    set_path: Annotated[Path, typer.Option("--set")] = Path("datasets/calibration/v1.yaml"),
    database_url: DbOpt = None,
) -> None:
    """Calibrate a judge against a reference-labelled set and apply the admission policy."""
    from evalcore.calibration import AdmissionPolicy

    _setup(database_url)
    with session_scope() as s:
        cset = catalog.sync_calibration_set(s, set_path)
        j = s.scalar(select(JudgeConfig).where(JudgeConfig.model == judge_model.split(":")[-1]))
        if j is None:
            from .seed import LENIENT, STRICT, _judge

            j = _judge(s, LENIENT if "lenient" in judge_model else STRICT)
        c = judge_svc.calibrate(s, j, cset, AdmissionPolicy())
        m = c.metrics
        console.print(
            f"{j.model}: n={m['n']} kappa={m['kappa']:.2f} fpr={m['fpr']:.1%} "
            f"fnr={m['fnr']:.1%} acc={m['accuracy']:.1%}"
        )
        console.print(
            "[green]CALIBRATED — allowed for gating[/green]"
            if c.admitted
            else "[red]NOT CALIBRATED — diagnostic only[/red]: " + "; ".join(c.reasons)
        )
        if not c.admitted:
            raise typer.Exit(1)


# ----------------------------------------------------------------------------- traces
@traces.command("distill")
def traces_distill(
    run: str,
    out: Path = Path("datasets/candidates"),
    only_failed: bool = True,
    limit: int = 5,
    database_url: DbOpt = None,
) -> None:
    """Turn traced samples into CANDIDATE cases (never auto-promoted; needs human review)."""
    import yaml
    from evalcore.distill import distill_case
    from evalcore.models import AgentResult, Case

    from .models import EvalCase

    _setup(database_url)
    out.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        r = s.get(Run, run)
        if r is None:
            console.print("[red]unknown run[/red]")
            raise typer.Exit(4)
        q = select(Sample).where(Sample.run_id == run, Sample.sample_index == 0)
        if only_failed:
            q = q.where(Sample.status == "failed")
        n = 0
        for smp in s.scalars(q.limit(limit)):
            row = s.scalar(
                select(EvalCase).where(
                    EvalCase.dataset_version_id == r.dataset_version_id, EvalCase.case_id == smp.case_id
                )
            )
            if row is None:
                continue
            cand = distill_case(
                Case.model_validate(row.definition),
                AgentResult.model_validate(smp.result),
                run,
                0,
                smp.status == "passed",
            )
            (out / f"{cand['id']}.yaml").write_text(yaml.safe_dump(cand, sort_keys=False, width=120))
            n += 1
        console.print(f"wrote {n} candidate case(s) to {out} - review and edit before adding to a NEW dataset version")


# ------------------------------------------------------------------------------- gate
@gatecmd.command("check")
def gate_check(database_url: DbOpt = None) -> None:
    """Exit non-zero if the latest stored gate decision is a failure."""
    _setup(database_url)
    with session_scope() as s:
        g = comparisons.latest_gate(s)
        if g is None:
            console.print("no gate decisions")
            raise typer.Exit(4)
        console.print(f"latest gate: {g.verdict.upper()} - " + "; ".join(g.reasons))
        raise typer.Exit(0 if g.verdict == "pass" else 1)


@app.command("worker")
def worker(once: bool = False, poll_seconds: float = 2.0, database_url: DbOpt = None) -> None:
    """Run the job worker (claims queued runs; recovers stale jobs)."""
    from .logging_setup import setup_logging

    setup_logging(get_settings().log_level)
    _setup(database_url)
    stale = get_settings().stale_job_seconds
    while True:
        with session_scope() as s:
            did = jobs.work_once(s, stale)
        if once:
            return
        if not did:
            time.sleep(poll_seconds)


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000, database_url: DbOpt = None) -> None:
    """Run the API with uvicorn."""
    import uvicorn

    _setup(database_url)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_config=None,
        proxy_headers=True,
        forwarded_allow_ips=get_settings().forwarded_allow_ips,
    )


@app.command("openapi")
def openapi(out: Path = Path("apps/web/lib/openapi.json")) -> None:
    """Export the OpenAPI spec (drives the generated frontend types)."""
    from .main import app as fastapi_app

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fastapi_app.openapi(), indent=2))
    console.print(f"wrote {out}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
