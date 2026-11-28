"""Tests for devtools/review.sh and devtools/review.toml."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_SH = ROOT / "devtools" / "review.sh"
REVIEW_TOML = ROOT / "devtools" / "review.toml"


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _barrier_snippet(barrier_dir: Path | None, name: str, count: int) -> str:
    if barrier_dir is None:
        return ""
    return textwrap.dedent(
        f"""
        touch "{barrier_dir}/{name}.arrived"
        for _ in $(seq 1 100); do
          if [[ "$(ls -1 "{barrier_dir}"/*.arrived 2>/dev/null | wc -l | tr -d ' ')" -ge {count} ]]; then
            break
          fi
          sleep 0.05
        done
        if [[ "$(ls -1 "{barrier_dir}"/*.arrived 2>/dev/null | wc -l | tr -d ' ')" -lt {count} ]]; then
          echo "parallel barrier timed out for {name}" >&2
          exit 98
        fi
        """
    ).strip()


def _make_stub_bins(
    bin_dir: Path,
    *,
    fail_models: set[str] | None = None,
    empty_models: set[str] | None = None,
    barrier_dir: Path | None = None,
    barrier_count: int = 3,
) -> None:
    fail_models = fail_models or set()
    empty_models = empty_models or set()

    # Claude stub: checks CLAUDECODE is unset and echoes system prompt + user prompt.
    claude_exit = 1 if "claude" in fail_models else 0
    claude_empty = 1 if "claude" in empty_models else 0
    _write_executable(
        bin_dir / "claude",
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        if [[ -n "${{CLAUDECODE:-}}" ]]; then
          echo "CLAUDECODE was leaked" >&2
          exit 99
        fi
        {_barrier_snippet(barrier_dir, "claude", barrier_count)}
        if [[ {claude_exit} -ne 0 ]]; then
          echo "claude simulated failure" >&2
          exit {claude_exit}
        fi
        if [[ {claude_empty} -ne 0 ]]; then
          exit 0
        fi
        printf '## Verdict\\napprove\\n\\nARGS:%s\\n' "$*"
        """,
    )

    # Gemini (agy) stub: echoes args (which include system + user prompt).
    gemini_exit = 1 if "gemini" in fail_models else 0
    gemini_empty = 1 if "gemini" in empty_models else 0
    _write_executable(
        bin_dir / "agy",
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        {_barrier_snippet(barrier_dir, "gemini", barrier_count)}
        if [[ {gemini_exit} -ne 0 ]]; then
          echo "gemini simulated failure" >&2
          exit {gemini_exit}
        fi
        if [[ {gemini_empty} -ne 0 ]]; then
          exit 0
        fi
        printf '## Verdict\\ncomment\\n\\nARGS:%s\\n' "$*"
        """,
    )

    # Codex stub: writes stdin (system + user prompt) to the -o target file.
    codex_exit = 1 if "codex" in fail_models else 0
    codex_empty = 1 if "codex" in empty_models else 0
    _write_executable(
        bin_dir / "codex",
        f"""
        #!/usr/bin/env bash
        set -euo pipefail
        {_barrier_snippet(barrier_dir, "codex", barrier_count)}
        if [[ {codex_exit} -ne 0 ]]; then
          echo "codex simulated failure" >&2
          exit {codex_exit}
        fi
        OUT=""
        while [[ $# -gt 0 ]]; do
          if [[ "$1" == "-o" ]]; then
            OUT="$2"
            shift 2
          else
            shift
          fi
        done
        STDIN_CONTENT="$(cat)"
        if [[ {codex_empty} -ne 0 ]]; then
          exit 0
        fi
        if [[ -n "$OUT" ]]; then
          printf '## Verdict\\napprove\\n\\nSTDIN:\\n%s\\n' "$STDIN_CONTENT" > "$OUT"
        else
          printf '## Verdict\\napprove\\n\\nSTDIN:\\n%s\\n' "$STDIN_CONTENT"
        fi
        """,
    )


def _run_review(
    args: list[str],
    *,
    bin_dir: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(REVIEW_SH), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _extract_run_dir(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("Review run complete: "):
            return Path(line.split("Review run complete: ", 1)[1].strip())
    raise AssertionError(f"Could not find run directory in stdout:\n{stdout}")


def test_default_review_toml_is_valid() -> None:
    config = tomllib.loads(REVIEW_TOML.read_text(encoding="utf-8"))
    assert config["review"]["timeout_seconds"] > 0
    assert config["review"]["output_dir"] == ".review-runs"
    assert config["review"]["strict"] is False
    system_prompt = config["prompts"]["system"]
    assert "## Standards" in system_prompt
    assert "## Spec" in system_prompt
    assert "## Summary" in system_prompt
    assert "Feature Envy" in system_prompt
    assert set(config["models"]) == {"claude", "gemini", "codex"}
    assert config["models"]["claude"]["model"] == "claude-opus-5-5"
    assert config["models"]["gemini"]["command"] == "agy"
    assert config["models"]["gemini"]["model"] == "gemini-4-neon"
    assert config["models"]["codex"]["model"] == "gpt-6.2-sol"
    for model_name in ("claude", "gemini", "codex"):
        assert config["models"][model_name]["reasoning_effort"] == "medium"


def test_parallel_run_shared_and_per_model_prompts_and_env_sanitization(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    barrier_dir = tmp_path / "barrier"
    barrier_dir.mkdir()
    _make_stub_bins(bin_dir, barrier_dir=barrier_dir, barrier_count=3)

    out_root = tmp_path / "runs"
    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{out_root}"
            strict = false

            [prompts]
            system = "SHARED_SYSTEM_RUBRIC"

            [models.claude]
            enabled = true
            system_prompt_append = "CLAUDE_EXTRA_LENS"

            [models.gemini]
            enabled = true
            system_prompt_append = "GEMINI_EXTRA_LENS"

            [models.codex]
            enabled = true
            system_prompt_append = ""
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(
        ["--config", str(cfg), "--base", "HEAD~1", "--prompt", "Focus on security"],
        bin_dir=bin_dir,
        extra_env={"CLAUDECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    run_dir = _extract_run_dir(result.stdout)
    assert run_dir.parent == out_root
    for name in ("claude", "gemini", "codex"):
        assert str(run_dir / f"{name}.stderr.log") in result.stdout
        assert str(run_dir / f"{name}.md") in result.stdout

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert sorted(meta["succeeded"]) == ["claude", "codex", "gemini"]
    assert meta["failed"] == []
    assert meta["skipped"] == []
    assert "--dangerously-skip-permissions" in meta["models"]["claude"]["command"]
    assert "--dangerously-skip-permissions" in meta["models"]["gemini"]["command"]
    assert "--sandbox" not in meta["models"]["gemini"]["command"]
    assert "--dangerously-bypass-approvals-and-sandbox" in meta["models"]["codex"]["command"]

    claude_text = (run_dir / "claude.md").read_text(encoding="utf-8")
    assert "SHARED_SYSTEM_RUBRIC" in claude_text
    assert "CLAUDE_EXTRA_LENS" in claude_text
    assert "git diff HEAD~1...HEAD" in claude_text
    assert "Commits in scope" in claude_text
    assert "Focus on security" in claude_text

    gemini_text = (run_dir / "gemini.md").read_text(encoding="utf-8")
    assert "SHARED_SYSTEM_RUBRIC" in gemini_text
    assert "GEMINI_EXTRA_LENS" in gemini_text

    codex_text = (run_dir / "codex.md").read_text(encoding="utf-8")
    assert "SHARED_SYSTEM_RUBRIC" in codex_text
    assert "CLAUDE_EXTRA_LENS" not in codex_text


def test_disabled_model_and_graceful_degradation(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir, fail_models={"gemini"})

    out_root = tmp_path / "runs"
    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{out_root}"
            strict = false

            [prompts]
            system = "BASE"

            [models.claude]
            enabled = true

            [models.gemini]
            enabled = true

            [models.codex]
            enabled = false
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(["--config", str(cfg), "src"], bin_dir=bin_dir)
    assert result.returncode == 0, result.stderr
    run_dir = _extract_run_dir(result.stdout)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

    assert meta["succeeded"] == ["claude"]
    assert meta["failed"] == ["gemini"]
    assert meta["skipped"] == ["codex"]
    assert meta["models"]["codex"]["status"] == "skipped"
    assert meta["models"]["gemini"]["status"] == "failed"
    assert (run_dir / "gemini.stderr.log").is_file()


def test_strict_mode_and_missing_cli_fail(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir)

    out_root = tmp_path / "runs"
    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{out_root}"
            strict = false

            [prompts]
            system = "BASE"

            [models.claude]
            enabled = true

            [models.gemini]
            enabled = true
            command = "definitely-not-installed-review-cli"

            [models.codex]
            enabled = false
            """
        ),
        encoding="utf-8",
    )

    # Non-strict succeeds with 1/2 ok.
    non_strict = _run_review(["--config", str(cfg), "src"], bin_dir=bin_dir)
    assert non_strict.returncode == 0
    non_strict_dir = _extract_run_dir(non_strict.stdout)
    meta = json.loads((non_strict_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["models"]["gemini"]["status"] == "missing"

    # Strict fails with non-zero exit code.
    strict = _run_review(["--config", str(cfg), "--strict", "src"], bin_dir=bin_dir)
    assert strict.returncode == 1
    assert "Strict mode enabled" in strict.stderr


def test_total_failure_exits_nonzero(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir, fail_models={"claude", "gemini", "codex"})

    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{tmp_path / "runs"}"
            strict = false

            [prompts]
            system = "BASE"

            [models.claude]
            enabled = true

            [models.gemini]
            enabled = true

            [models.codex]
            enabled = true
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(["--config", str(cfg), "src"], bin_dir=bin_dir)
    assert result.returncode == 1
    assert "All enabled review models failed" in result.stderr


def test_missing_and_invalid_config_fail_fast(tmp_path: Path) -> None:
    missing = _run_review(["--config", str(tmp_path / "missing.toml")])
    assert missing.returncode == 2
    assert "Configuration file not found" in missing.stderr

    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("[review\nbroken =", encoding="utf-8")
    invalid = _run_review(["--config", str(bad_toml)])
    assert invalid.returncode == 2
    assert "Invalid TOML" in invalid.stderr


def test_change_flag_routes_to_openspec_change_and_rejects_unknown(tmp_path: Path) -> None:
    unknown = _run_review(["--change", "nonexistent-change-xyz", "--dry-run", "src"])
    assert unknown.returncode == 2
    assert "does not exist" in unknown.stderr
    assert not (ROOT / "openspec" / "changes" / "nonexistent-change-xyz").exists()

    # Validate path routing against a temporary change directory inside openspec/changes.
    temp_change_name = f"_test-review-change-{os.getpid()}"
    temp_change_dir = ROOT / "openspec" / "changes" / temp_change_name
    temp_change_dir.mkdir(parents=True, exist_ok=True)
    try:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _make_stub_bins(bin_dir)

        result = _run_review(["--change", temp_change_name, "src"], bin_dir=bin_dir)
        assert result.returncode == 0, result.stderr
        run_dir = _extract_run_dir(result.stdout)
        assert run_dir.parent == temp_change_dir / "reviews"
        assert (run_dir / "meta.json").is_file()
        assert (run_dir / "claude.md").is_file()
        assert (run_dir / "gemini.md").is_file()
        assert (run_dir / "codex.md").is_file()
    finally:
        for child in sorted(temp_change_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        temp_change_dir.rmdir()


def test_bad_base_ref_and_empty_diff_fail_fast() -> None:
    bad_ref = _run_review(["--base", "nonexistent-git-ref-xyz", "--dry-run"])
    assert bad_ref.returncode == 2
    assert "does not resolve" in bad_ref.stderr

    # Reviewing an unchanged tracked file against HEAD has an empty diff.
    empty_diff = _run_review(["--base", "HEAD", "--dry-run", "Cargo.toml"])
    assert empty_diff.returncode == 2
    assert "No changes found" in empty_diff.stderr

    # Reviewing against HEAD~1 injects commit history and diff stat into the prompt.
    with_commits = _run_review(["--base", "HEAD~1", "--dry-run"])
    assert with_commits.returncode == 0, with_commits.stderr
    plan = json.loads(with_commits.stdout)
    assert "Commits in scope" in plan["user_prompt"]
    assert "Changed files summary" in plan["user_prompt"]


def test_reasoning_effort_and_models_subset_flags() -> None:
    subset = _run_review(["--models", "claude,codex", "--dry-run", "src"])
    assert subset.returncode == 0, subset.stderr
    plan = json.loads(subset.stdout)

    assert plan["models"]["claude"]["enabled"] is True
    assert "--effort" in plan["models"]["claude"]["command"]
    assert "medium" in plan["models"]["claude"]["command"]

    assert plan["models"]["codex"]["enabled"] is True
    assert 'model_reasoning_effort="medium"' in plan["models"]["codex"]["command"]

    assert plan["models"]["gemini"]["enabled"] is False
    assert plan["models"]["gemini"]["status"] == "skipped"

    bad_model = _run_review(["--models", "claude,unknown", "--dry-run", "src"])
    assert bad_model.returncode == 2
    assert "Unknown model(s)" in bad_model.stderr


def test_per_model_cli_overrides(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir)

    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{tmp_path / "runs"}"
            strict = false

            [prompts]
            system = "BASE_RUBRIC"

            [models.claude]
            enabled = true
            reasoning_effort = "medium"

            [models.gemini]
            enabled = true
            reasoning_effort = "medium"

            [models.codex]
            enabled = true
            reasoning_effort = "medium"
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(
        [
            "--config",
            str(cfg),
            "--models",
            "codex,claude",
            "--effort",
            "codex=high",
            "--effort",
            "claude=low",
            "--model-id",
            "codex=gpt-5.4",
            "--model-prompt",
            "codex=CHECK_RACE_CONDITIONS",
            "--model-prompt",
            "claude=CHECK_SIMPLIFICATION",
            "src",
        ],
        bin_dir=bin_dir,
    )
    assert result.returncode == 0, result.stderr
    run_dir = _extract_run_dir(result.stdout)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

    assert sorted(meta["succeeded"]) == ["claude", "codex"]
    assert meta["skipped"] == ["gemini"]
    assert meta["models"]["codex"]["reasoning_effort"] == "high"
    assert meta["models"]["codex"]["model"] == "gpt-5.4"
    assert meta["models"]["codex"]["system_prompt_append"] == "CHECK_RACE_CONDITIONS"
    assert meta["models"]["claude"]["reasoning_effort"] == "low"
    assert meta["models"]["claude"]["system_prompt_append"] == "CHECK_SIMPLIFICATION"
    assert meta["overrides"]["models"] == ["claude", "codex"]
    assert meta["overrides"]["effort"] == {"codex": "high", "claude": "low"}
    assert meta["overrides"]["model_prompt"] == {
        "codex": "CHECK_RACE_CONDITIONS",
        "claude": "CHECK_SIMPLIFICATION",
    }
    assert meta["overrides"]["model_id"] == {"codex": "gpt-5.4"}
    assert "--effort" in meta["invocation_argv"]
    assert "src" in meta["user_prompt"]

    codex_text = (run_dir / "codex.md").read_text(encoding="utf-8")
    assert "CHECK_RACE_CONDITIONS" in codex_text
    assert "CHECK_SIMPLIFICATION" not in codex_text

    claude_text = (run_dir / "claude.md").read_text(encoding="utf-8")
    assert "CHECK_SIMPLIFICATION" in claude_text
    assert "CHECK_RACE_CONDITIONS" not in claude_text
    assert "--effort low" in claude_text

    bad_override = _run_review(["--effort", "claude-no-equals", "--dry-run", "src"])
    assert bad_override.returncode == 2
    assert "expected HARNESS=VALUE" in bad_override.stderr


def test_config_validation_rejects_invalid_types(tmp_path: Path) -> None:
    bad_strict = tmp_path / "bad_strict.toml"
    bad_strict.write_text('[review]\nstrict = "false"\n[models.claude]\nenabled = true\n', encoding="utf-8")
    res = _run_review(["--config", str(bad_strict), "--dry-run", "src"])
    assert res.returncode == 2
    assert "strict" in res.stderr

    bad_timeout = tmp_path / "bad_timeout.toml"
    bad_timeout.write_text("[review]\ntimeout_seconds = 0\n[models.claude]\nenabled = true\n", encoding="utf-8")
    res_timeout = _run_review(["--config", str(bad_timeout), "--dry-run", "src"])
    assert res_timeout.returncode == 2
    assert "timeout_seconds" in res_timeout.stderr

    for bad_extra in ('extra_args = "--verbose"', "extra_args = 123", "extra_args = [1, 2]"):
        cfg = tmp_path / "bad_extra.toml"
        cfg.write_text(f"[models.claude]\nenabled = true\n{bad_extra}\n", encoding="utf-8")
        res_extra = _run_review(["--config", str(cfg), "--dry-run", "src"])
        assert res_extra.returncode == 2
        assert "extra_args" in res_extra.stderr


def test_non_utf8_output_and_symlink_reviews_dir_handled(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir)
    # Emit invalid UTF-8 bytes from a failing claude stub and confirm meta.json still writes cleanly.
    _write_executable(
        bin_dir / "claude",
        """
        #!/usr/bin/env bash
        printf '\\xff\\xfe\\xfd'
        exit 1
        """,
    )

    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{tmp_path / "runs"}"
            strict = false

            [prompts]
            system = "BASE"

            [models.claude]
            enabled = true

            [models.gemini]
            enabled = true

            [models.codex]
            enabled = false
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(["--config", str(cfg), "src"], bin_dir=bin_dir)
    assert result.returncode == 0, result.stderr
    run_dir = _extract_run_dir(result.stdout)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["succeeded"] == ["gemini"]
    assert meta["failed"] == ["claude"]

    # A symlinked reviews/ directory escaping the change root must be rejected.
    from devtools import review as review_mod

    fake_change = tmp_path / "openspec" / "changes" / "demo"
    fake_change.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (fake_change / "reviews").symlink_to(outside)
    try:
        review_mod.resolve_run_dir(
            tmp_path, output_dir_setting=".review-runs", change="demo", timestamp="20260101-000000"
        )
    except ValueError as exc:
        assert "escapes change root" in str(exc)
    else:
        raise AssertionError("Expected ValueError for symlinked reviews directory")


def test_empty_output_and_launch_oserror_degrade_gracefully(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_bins(bin_dir, empty_models={"gemini"})
    # Replace codex with a broken shebang so subprocess.run raises OSError.
    _write_executable(bin_dir / "codex", "#!/nonexistent/interpreter\n")

    cfg = tmp_path / "review.toml"
    cfg.write_text(
        textwrap.dedent(
            f"""
            [review]
            timeout_seconds = 30
            output_dir = "{tmp_path / "runs"}"
            strict = false

            [prompts]
            system = "BASE"

            [models.claude]
            enabled = true

            [models.gemini]
            enabled = true

            [models.codex]
            enabled = true
            command = "{bin_dir / "codex"}"
            """
        ),
        encoding="utf-8",
    )

    result = _run_review(["--config", str(cfg), "src"], bin_dir=bin_dir)
    assert result.returncode == 0, result.stderr
    run_dir = _extract_run_dir(result.stdout)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))

    assert meta["succeeded"] == ["claude"]
    assert sorted(meta["failed"]) == ["codex", "gemini"]
    assert meta["models"]["gemini"]["status"] == "failed"
    assert "no review output" in meta["models"]["gemini"]["error"]
    assert meta["models"]["gemini"]["output_file"] is None
    assert meta["models"]["codex"]["status"] == "failed"
    assert meta["models"]["codex"]["exit_code"] == 126


def test_change_rejects_archive_and_dot_and_git_errors_surface(tmp_path: Path) -> None:
    for invalid_change in (".", "archive", "../outside"):
        res = _run_review(["--change", invalid_change, "--dry-run", "src"])
        assert res.returncode == 2
        assert "Invalid OpenSpec change name" in res.stderr

    # Running inspect_git_scope in a non-git directory surfaces the git error instead of "No changes found".
    from devtools import review as review_mod

    try:
        review_mod.inspect_git_scope(tmp_path, base=None, paths=[])
    except ValueError as exc:
        assert "git status" in str(exc)
        assert "No uncommitted changes" not in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-git directory")

    first = review_mod.create_run_dir(tmp_path, output_dir_setting="runs", change=None, timestamp="20260101-000000")
    second = review_mod.create_run_dir(tmp_path, output_dir_setting="runs", change=None, timestamp="20260101-000000")
    assert first.name == "20260101-000000"
    assert second.name == "20260101-000000-1"
