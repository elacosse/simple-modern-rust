"""Parallel read-only multi-model review runner backed by devtools/review.toml."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_MODELS = ("claude", "gemini", "codex")


@dataclass(frozen=True)
class ModelConfig:
    name: str
    enabled: bool
    command: str
    model: str
    reasoning_effort: str
    extra_args: tuple[str, ...]
    system_prompt_append: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devtools/review.sh",
        description="Run Claude, Gemini, and Codex in parallel for a read-only repository review.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to TOML configuration file (default: devtools/review.toml).",
    )
    parser.add_argument(
        "--change",
        default=None,
        help="OpenSpec change name; saves review outputs under openspec/changes/<name>/reviews/<timestamp>/.",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Git base ref to review against (e.g. main).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Additional review focus instructions appended to the review prompt.",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated subset of models to run (e.g. claude,codex).",
    )
    parser.add_argument(
        "--effort",
        action="append",
        default=[],
        metavar="HARNESS=LEVEL",
        help="Repeatable per-harness reasoning effort override (e.g. --effort codex=medium --effort claude=low).",
    )
    parser.add_argument(
        "--model-prompt",
        action="append",
        default=[],
        metavar="HARNESS=TEXT",
        help="Repeatable per-harness prompt extension (e.g. --model-prompt 'codex=focus on edge cases').",
    )
    parser.add_argument(
        "--model-id",
        action="append",
        default=[],
        metavar="HARNESS=MODEL",
        help="Repeatable per-harness model ID override (e.g. --model-id codex=gpt-5.4).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with non-zero exit code if any enabled model fails (overrides config strict=false).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and print planned invocations without running model harnesses.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional file or directory paths to focus the review on.",
    )
    return parser


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise ValueError(f"Configuration file not found: {config_path}")
    try:
        return tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid TOML in {config_path}: {exc}") from exc


def parse_review_settings(config: dict[str, Any], *, cli_strict: bool) -> tuple[int, str, bool]:
    review_cfg = config.get("review", {})
    if not isinstance(review_cfg, dict):
        raise ValueError("Configuration section [review] must be a TOML table.")

    raw_timeout = review_cfg.get("timeout_seconds", 300)
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, int) or raw_timeout <= 0:
        raise ValueError(f"Invalid [review].timeout_seconds: {raw_timeout!r} (expected positive integer).")

    raw_output_dir = review_cfg.get("output_dir", ".review-runs")
    if not isinstance(raw_output_dir, str) or not raw_output_dir.strip():
        raise ValueError(f"Invalid [review].output_dir: {raw_output_dir!r} (expected non-empty string).")

    raw_strict = review_cfg.get("strict", False)
    if not isinstance(raw_strict, bool):
        raise ValueError(f"Invalid [review].strict: {raw_strict!r} (expected boolean).")

    return raw_timeout, raw_output_dir, raw_strict or cli_strict


def _run_git(project_root: Path, *git_args: str) -> str:
    proc = subprocess.run(
        ["git", *git_args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise ValueError(f"git {' '.join(git_args)} failed: {detail}")
    return proc.stdout.strip()


def inspect_git_scope(
    project_root: Path,
    *,
    base: str | None,
    paths: list[str],
) -> tuple[str, str]:
    """Validate git scope and return (commit_list, diff_stat) for the review prompt."""
    path_args = ["--", *paths] if paths else []

    if base is not None:
        try:
            _run_git(project_root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
        except ValueError as exc:
            raise ValueError(f"Git base ref does not resolve: {base}") from exc

        diff_stat = _run_git(project_root, "diff", "--stat", f"{base}...HEAD", *path_args)
        working_status = _run_git(project_root, "status", "--porcelain", *path_args)
        if not diff_stat and not working_status:
            raise ValueError(f"No changes found relative to git ref '{base}'.")

        commits = _run_git(project_root, "log", f"{base}..HEAD", "--oneline", *path_args)
        stat_parts = [part for part in (diff_stat, working_status and f"Working tree:\n{working_status}") if part]
        return commits, "\n\n".join(stat_parts)

    if not paths:
        working_status = _run_git(project_root, "status", "--porcelain")
        if not working_status:
            raise ValueError(
                "No uncommitted changes found to review. Pass --base <ref> or explicit file/directory paths."
            )
        diff_stat = _run_git(project_root, "diff", "--stat", "HEAD")
        return "", diff_stat or working_status

    return "", ""


def build_user_prompt(
    *,
    base: str | None,
    paths: list[str],
    focus_prompt: str | None,
    change: str | None,
    commits: str = "",
    diff_stat: str = "",
) -> str:
    sections: list[str] = ["Perform a thorough, read-only review of this repository."]

    if change:
        sections.append(
            f"OpenSpec change context: inspect `openspec/changes/{change}/` (proposal, specs, design, tasks) "
            "alongside the implementation."
        )

    if base:
        sections.append(
            f"Review scope: inspect changes relative to git ref `{base}` (`git diff {base}...HEAD` plus any uncommitted changes)."
        )
    elif not paths:
        sections.append(
            "Review scope: inspect the repository's current uncommitted changes (staged and unstaged git diff, plus untracked files if relevant)."
        )

    if commits:
        sections.append(f"Commits in scope (`git log {base}..HEAD --oneline`):\n```\n{commits}\n```")

    if diff_stat:
        sections.append(f"Changed files summary:\n```\n{diff_stat}\n```")

    if paths:
        formatted = ", ".join(f"`{p}`" for p in paths)
        sections.append(f"Target paths: focus on {formatted} and any directly related callers, tests, or specs.")

    if focus_prompt:
        sections.append(f"Additional focus instructions:\n{focus_prompt.strip()}")

    return "\n\n".join(sections)


def compose_system_prompt(base_prompt: str, append_prompt: str) -> str:
    base_clean = base_prompt.strip()
    append_clean = append_prompt.strip()
    if base_clean and append_clean:
        return f"{base_clean}\n\n{append_clean}"
    return base_clean or append_clean


def combine_prompts(system_prompt: str, user_prompt: str) -> str:
    return f"{system_prompt}\n\n---\n\n{user_prompt}" if system_prompt else user_prompt


def parse_model_overrides(entries: list[str], *, flag: str, join_multiple: bool = False) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid {flag} value {entry!r}: expected HARNESS=VALUE.")
        harness, value = entry.split("=", 1)
        harness = harness.strip()
        value = value.strip()
        if harness not in SUPPORTED_MODELS:
            raise ValueError(f"Unknown harness {harness!r} in {flag}. Supported: {', '.join(SUPPORTED_MODELS)}.")
        if not value:
            raise ValueError(f"Empty value for {harness!r} in {flag}.")
        if join_multiple and harness in parsed:
            parsed[harness] = compose_system_prompt(parsed[harness], value)
        else:
            parsed[harness] = value
    return parsed


def _resolve_output_parent(
    project_root: Path,
    *,
    output_dir_setting: str,
    change: str | None,
) -> Path:
    if change is not None:
        if not change or change in {".", "..", "archive"} or "/" in change or "\\" in change or ".." in change:
            raise ValueError(f"Invalid OpenSpec change name: {change!r}")
        changes_root = (project_root / "openspec" / "changes").resolve()
        change_dir = (changes_root / change).resolve()
        if change_dir.parent != changes_root or not change_dir.is_dir():
            raise ValueError(
                f"OpenSpec change directory does not exist: {project_root / 'openspec' / 'changes' / change}"
            )
        reviews_dir = change_dir / "reviews"
        if reviews_dir.resolve().parent != change_dir:
            raise ValueError(f"OpenSpec change reviews directory escapes change root: {reviews_dir}")
        return reviews_dir

    output_path = Path(output_dir_setting)
    return output_path if output_path.is_absolute() else project_root / output_path


def _iter_run_dir_candidates(parent: Path, timestamp: str) -> Iterator[Path]:
    yield parent / timestamp
    suffix = 1
    while True:
        yield parent / f"{timestamp}-{suffix}"
        suffix += 1


def resolve_run_dir(
    project_root: Path,
    *,
    output_dir_setting: str,
    change: str | None,
    timestamp: str,
) -> Path:
    parent = _resolve_output_parent(project_root, output_dir_setting=output_dir_setting, change=change)
    for candidate in _iter_run_dir_candidates(parent, timestamp):
        if not os.path.lexists(candidate):
            return candidate
    raise AssertionError("unreachable")  # pragma: no cover


def create_run_dir(
    project_root: Path,
    *,
    output_dir_setting: str,
    change: str | None,
    timestamp: str,
) -> Path:
    """Atomically reserve a unique timestamped run directory."""
    parent = _resolve_output_parent(project_root, output_dir_setting=output_dir_setting, change=change)
    parent.mkdir(parents=True, exist_ok=True)
    for candidate in _iter_run_dir_candidates(parent, timestamp):
        try:
            candidate.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return candidate
    raise AssertionError("unreachable")  # pragma: no cover


def build_model_command(
    model_cfg: ModelConfig,
    *,
    system_prompt: str,
    user_prompt: str,
    output_file: Path,
) -> tuple[list[str], str | None]:
    """Return (argv, stdin_text)."""
    if model_cfg.name == "claude":
        cmd = [
            model_cfg.command,
            "-p",
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--system-prompt",
            system_prompt,
        ]
        if model_cfg.model:
            cmd.extend(["--model", model_cfg.model])
        if model_cfg.reasoning_effort:
            cmd.extend(["--effort", model_cfg.reasoning_effort])
        cmd.extend(model_cfg.extra_args)
        cmd.append(user_prompt)
        return cmd, None

    if model_cfg.name == "gemini":
        cmd = [
            model_cfg.command,
            "--dangerously-skip-permissions",
            "--output-format",
            "text",
        ]
        if model_cfg.model:
            cmd.extend(["--model", model_cfg.model])
        if model_cfg.reasoning_effort:
            cmd.extend(["--effort", model_cfg.reasoning_effort])
        cmd.extend(model_cfg.extra_args)
        cmd.extend(["-p", combine_prompts(system_prompt, user_prompt)])
        return cmd, None

    if model_cfg.name == "codex":
        cmd = [
            model_cfg.command,
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ephemeral",
            "-o",
            str(output_file),
        ]
        if model_cfg.model:
            cmd.extend(["-m", model_cfg.model])
        if model_cfg.reasoning_effort:
            cmd.extend(["-c", f'model_reasoning_effort="{model_cfg.reasoning_effort}"'])
        cmd.extend(model_cfg.extra_args)
        cmd.append("-")
        return cmd, combine_prompts(system_prompt, user_prompt)

    raise ValueError(f"Unsupported model harness: {model_cfg.name}")


def _base_model_result(model_cfg: ModelConfig, command: list[str]) -> dict[str, Any]:
    return {
        "enabled": model_cfg.enabled,
        "status": "skipped",
        "exit_code": None,
        "duration_seconds": 0.0,
        "model": model_cfg.model,
        "reasoning_effort": model_cfg.reasoning_effort,
        "system_prompt_append": model_cfg.system_prompt_append,
        "output_file": None,
        "stderr_file": None,
        "command": command,
    }


def run_single_model(
    model_cfg: ModelConfig,
    *,
    cmd: list[str],
    stdin_text: str | None,
    run_dir: Path,
    project_root: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    output_file = run_dir / f"{model_cfg.name}.md"
    stderr_file = run_dir / f"{model_cfg.name}.stderr.log"
    base_result = _base_model_result(model_cfg, cmd)

    if shutil.which(cmd[0]) is None:
        return {
            **base_result,
            "status": "missing",
            "exit_code": 127,
            "error": f"Executable not found on PATH: {cmd[0]}",
        }

    child_env = os.environ.copy()
    child_env.pop("CLAUDECODE", None)

    start = time.monotonic()
    with stderr_file.open("w", encoding="utf-8") as err_fh:
        out_fh = None if model_cfg.name == "codex" else output_file.open("w", encoding="utf-8")
        try:
            run_kwargs: dict[str, Any] = {
                "stdout": subprocess.DEVNULL if out_fh is None else out_fh,
                "stderr": err_fh,
                "text": True,
                "cwd": project_root,
                "env": child_env,
                "timeout": timeout_seconds,
                "check": False,
            }
            if stdin_text is not None:
                run_kwargs["input"] = stdin_text
            else:
                run_kwargs["stdin"] = subprocess.DEVNULL
            try:
                proc = subprocess.run(cmd, **run_kwargs)
            except subprocess.TimeoutExpired:
                duration = round(time.monotonic() - start, 3)
                err_fh.write(f"\nTimed out after {timeout_seconds}s\n")
                return {
                    **base_result,
                    "status": "timeout",
                    "exit_code": 124,
                    "duration_seconds": duration,
                    "output_file": output_file.name if output_file.is_file() else None,
                    "stderr_file": stderr_file.name,
                    "error": f"Timed out after {timeout_seconds}s",
                }
            except OSError as exc:
                duration = round(time.monotonic() - start, 3)
                err_fh.write(f"Failed to launch {cmd[0]}: {exc}\n")
                if out_fh is not None:
                    out_fh.close()
                    out_fh = None
                if output_file.is_file() and output_file.stat().st_size == 0:
                    output_file.unlink()
                return {
                    **base_result,
                    "status": "failed",
                    "exit_code": 126,
                    "duration_seconds": duration,
                    "stderr_file": stderr_file.name,
                    "error": f"Failed to launch {cmd[0]}: {exc}",
                }
        finally:
            if out_fh is not None:
                out_fh.close()

    duration = round(time.monotonic() - start, 3)
    if stderr_file.is_file() and stderr_file.stat().st_size == 0:
        stderr_file.unlink()

    has_report = output_file.is_file() and bool(output_file.read_text(encoding="utf-8", errors="replace").strip())
    if not has_report and output_file.is_file():
        output_file.unlink()

    result = {
        **base_result,
        "exit_code": proc.returncode,
        "duration_seconds": duration,
        "output_file": output_file.name if has_report else None,
        "stderr_file": stderr_file.name if stderr_file.is_file() else None,
    }
    if proc.returncode != 0:
        return {**result, "status": "failed"}
    if not has_report:
        return {**result, "status": "failed", "error": "Model exited 0 but produced no review output."}
    return {**result, "status": "ok"}


def _require_str_field(section: str, key: str, value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"Invalid [{section}].{key}: {value!r} (expected string).")
    return value.strip()


def _prepare_models(
    models_cfg: dict[str, Any],
    *,
    selected_models: set[str] | None,
    effort_overrides: dict[str, str],
    prompt_overrides: dict[str, str],
    model_id_overrides: dict[str, str],
) -> dict[str, ModelConfig]:
    effective: dict[str, ModelConfig] = {}
    for name in SUPPORTED_MODELS:
        section = f"models.{name}"
        raw_cfg = models_cfg.get(name)
        if raw_cfg is None:
            raw_dict: dict[str, Any] = {}
            enabled = False
        elif not isinstance(raw_cfg, dict):
            raise ValueError(f"Configuration section [{section}] must be a TOML table.")
        else:
            raw_dict = raw_cfg
            raw_enabled = raw_dict.get("enabled", True)
            if not isinstance(raw_enabled, bool):
                raise ValueError(f"Invalid [{section}].enabled: {raw_enabled!r} (expected boolean).")
            enabled = raw_enabled

        if selected_models is not None:
            enabled = name in selected_models

        default_binary = "agy" if name == "gemini" else name
        command = (
            _require_str_field(section, "command", raw_dict.get("command"), default=default_binary) or default_binary
        )
        model_id = model_id_overrides.get(name, _require_str_field(section, "model", raw_dict.get("model")))
        effort = effort_overrides.get(
            name, _require_str_field(section, "reasoning_effort", raw_dict.get("reasoning_effort"))
        )
        prompt_append = _require_str_field(section, "system_prompt_append", raw_dict.get("system_prompt_append"))
        if name in prompt_overrides:
            prompt_append = compose_system_prompt(prompt_append, prompt_overrides[name])

        raw_extra_args = raw_dict.get("extra_args", [])
        if not isinstance(raw_extra_args, list) or not all(isinstance(arg, str) for arg in raw_extra_args):
            raise ValueError(f"Invalid [{section}].extra_args: {raw_extra_args!r} (expected list of strings).")

        effective[name] = ModelConfig(
            name=name,
            enabled=enabled,
            command=command,
            model=model_id,
            reasoning_effort=effort,
            extra_args=tuple(raw_extra_args),
            system_prompt_append=prompt_append,
        )
    return effective


def _plan_invocations(
    effective_models: dict[str, ModelConfig],
    *,
    base_system_prompt: str,
    user_prompt: str,
    run_dir: Path,
) -> dict[str, tuple[list[str], str | None]]:
    planned: dict[str, tuple[list[str], str | None]] = {}
    for name, m_cfg in effective_models.items():
        if not m_cfg.enabled:
            continue
        sys_prompt = compose_system_prompt(base_system_prompt, m_cfg.system_prompt_append)
        planned[name] = build_model_command(
            m_cfg,
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            output_file=run_dir / f"{name}.md",
        )
    return planned


def main(argv: list[str]) -> int:
    project_root = Path(argv[0]).resolve()
    args = build_parser().parse_args(argv[1:])

    config_path = Path(args.config).resolve() if args.config else project_root / "devtools" / "review.toml"
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")

    try:
        config = load_config(config_path)
        timeout_seconds, output_dir_setting, strict = parse_review_settings(config, cli_strict=args.strict)

        prompts_cfg = config.get("prompts", {})
        models_cfg = config.get("models", {})
        if not isinstance(prompts_cfg, dict):
            raise ValueError("Configuration section [prompts] must be a TOML table.")
        if not isinstance(models_cfg, dict):
            raise ValueError("Configuration section [models] must be a TOML table.")
        base_system_prompt = _require_str_field("prompts", "system", prompts_cfg.get("system"))

        commits, diff_stat = inspect_git_scope(
            project_root,
            base=args.base,
            paths=args.paths,
        )

        selected_models: set[str] | None = None
        if args.models:
            requested = [m.strip() for m in args.models.split(",") if m.strip()]
            invalid = [m for m in requested if m not in SUPPORTED_MODELS]
            if invalid:
                raise ValueError(
                    f"Unknown model(s) in --models: {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_MODELS)}"
                )
            selected_models = set(requested)

        effort_overrides = parse_model_overrides(args.effort, flag="--effort")
        prompt_overrides = parse_model_overrides(args.model_prompt, flag="--model-prompt", join_multiple=True)
        model_id_overrides = parse_model_overrides(args.model_id, flag="--model-id")

        effective_models = _prepare_models(
            models_cfg,
            selected_models=selected_models,
            effort_overrides=effort_overrides,
            prompt_overrides=prompt_overrides,
            model_id_overrides=model_id_overrides,
        )
        enabled_models = [name for name in SUPPORTED_MODELS if effective_models[name].enabled]
        if not enabled_models:
            raise ValueError("No models are enabled in configuration.")

        user_prompt = build_user_prompt(
            base=args.base,
            paths=args.paths,
            focus_prompt=args.prompt,
            change=args.change,
            commits=commits,
            diff_stat=diff_stat,
        )

        if args.dry_run:
            run_dir = resolve_run_dir(
                project_root,
                output_dir_setting=output_dir_setting,
                change=args.change,
                timestamp=timestamp,
            )
            planned = _plan_invocations(
                effective_models,
                base_system_prompt=base_system_prompt,
                user_prompt=user_prompt,
                run_dir=run_dir,
            )
            plan: dict[str, Any] = {
                "dry_run": True,
                "config_path": str(config_path),
                "run_dir": str(run_dir),
                "strict": strict,
                "timeout_seconds": timeout_seconds,
                "user_prompt": user_prompt,
                "models": {},
            }
            for name in SUPPORTED_MODELS:
                if name not in planned:
                    plan["models"][name] = {"enabled": False, "status": "skipped"}
                else:
                    cmd, _ = planned[name]
                    plan["models"][name] = {
                        "enabled": True,
                        "available": shutil.which(cmd[0]) is not None,
                        "command": cmd,
                    }
            print(json.dumps(plan, indent=2))
            return 0

        run_dir = create_run_dir(
            project_root,
            output_dir_setting=output_dir_setting,
            change=args.change,
            timestamp=timestamp,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    planned = _plan_invocations(
        effective_models,
        base_system_prompt=base_system_prompt,
        user_prompt=user_prompt,
        run_dir=run_dir,
    )

    print(f"Starting review run: {run_dir}", flush=True)
    print(f"  Running in parallel: {', '.join(enabled_models)}", flush=True)
    for name in enabled_models:
        print(f"  {name} logs: {run_dir / (name + '.stderr.log')} and {run_dir / (name + '.md')}", flush=True)

    results: dict[str, dict[str, Any]] = {
        name: _base_model_result(effective_models[name], []) for name in SUPPORTED_MODELS if name not in planned
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(planned)) as pool:
        future_to_name: dict[concurrent.futures.Future[dict[str, Any]], str] = {}
        for name, (cmd, stdin_text) in planned.items():
            future = pool.submit(
                run_single_model,
                effective_models[name],
                cmd=cmd,
                stdin_text=stdin_text,
                run_dir=run_dir,
                project_root=project_root,
                timeout_seconds=timeout_seconds,
            )
            future_to_name[future] = name
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            res = future.result()
            results[name] = res
            print(f"  - {name}: {res['status']} ({res['duration_seconds']}s)", flush=True)

    ordered_results = {name: results[name] for name in SUPPORTED_MODELS}
    succeeded = [name for name, res in ordered_results.items() if res["status"] == "ok"]
    failed = [name for name, res in ordered_results.items() if res["enabled"] and res["status"] != "ok"]
    skipped = [name for name, res in ordered_results.items() if res["status"] == "skipped"]

    meta = {
        "timestamp": timestamp,
        "run_dir": str(run_dir),
        "config_path": str(config_path),
        "invocation_argv": argv[1:],
        "change": args.change,
        "base": args.base,
        "paths": args.paths,
        "prompt": args.prompt,
        "user_prompt": user_prompt,
        "overrides": {
            "models": sorted(selected_models) if selected_models is not None else None,
            "effort": effort_overrides,
            "model_prompt": prompt_overrides,
            "model_id": model_id_overrides,
        },
        "strict": strict,
        "timeout_seconds": timeout_seconds,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "models": ordered_results,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"Review run complete: {run_dir}", flush=True)

    if not succeeded:
        print("Error: All enabled review models failed.", file=sys.stderr)
        return 1
    if strict and failed:
        print(f"Error: Strict mode enabled and models failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
