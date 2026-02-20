#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Evaluation script for KBDiag diagnosis algorithms.

Reads a TOML config and runs the specified algorithm on each KB/test-case
combination, writing per-iteration results and averages to a text file.

Usage:
    python -m apps.eval_runner apps/conf/kbdiag_eval.toml
"""

import fnmatch
import multiprocessing
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from explanation.models.diagnosis_model_builder import DiagnosisModelBuilder
from explanation.operations.algorithms.profiler import (
    ProfilerPreset,
    use_global_profiler,
)
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation
from explanation.operations.pysat_explanation_builder import (
    PySATTestcaseBuilder,
    PySATTestcaseQuickXplainBuilder,
)
from explanation.transformations.testsuite_reader import TestSuiteReader

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent

VALID_ALGORITHMS = {"kbdiag", "quickxplain_with_testcases"}
VALID_TASKS = {"1", "all"}

# Profiler metric keys → short display labels
PROFILER_COUNTER_LABELS = {
    # "kbdiag_runtime": "KBDiag runtime",
    "mssDirect_calls": "mssDirect calls",
    "is_consistent_test_cases_calls": "Consistency checks (TC)",
    "is_consistent_calls": "Consistency checks",
    # "quickxplain_with_testcases_runtime": "QuickXPlain+TC runtime",
    "quickxplain_with_testcases_calls": "QuickXPlain+TC calls",
    "qx_with_testcases_calls": "QX+TC calls",
    # "hsdag_runtime": "HSDAG runtime",
    "node_label_runtime": "Node labeling runtime",
    "path_label_cumulative_runtime": "Cumulative path labeling runtime",
}


@dataclass
class IterationResult:
    """Result of a single iteration."""
    result: Any
    time_first: float
    time_all: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    formatted_diagnoses: List[str] = field(default_factory=list)
    diag_sizes: List[int] = field(default_factory=list)
    num_diagnoses: int = 0


@dataclass
class ScenarioResult:
    """Result of all iterations of one scenario."""
    iterations: List[IterationResult] = field(default_factory=list)
    timed_out: bool = False


def load_config(config_path: str) -> Dict[str, Any]:
    """Parse and validate a TOML evaluation config.

    Args:
        config_path: Path to the TOML file.

    Returns:
        Parsed config dict.

    Raises:
        FileNotFoundError: If config file does not exist.
        ValueError: If required sections or values are missing/invalid.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "rb") as f:
        config = tomllib.load(f)

    # Validate required sections
    for section in ("evaluation", "solver", "kb", "output"):
        if section not in config:
            raise ValueError(f"Missing required section: [{section}]")

    algorithm = config["evaluation"].get("algorithm", "")
    if algorithm not in VALID_ALGORITHMS:
        raise ValueError(
            f"Invalid algorithm '{algorithm}'. Must be one of: {VALID_ALGORITHMS}"
        )

    task = config["evaluation"].get("task", "")
    if task not in VALID_TASKS:
        raise ValueError(f"Invalid task '{task}'. Must be one of: {VALID_TASKS}")

    # Validate num_iterations
    num_iterations = config["evaluation"].get("num_iterations", 3)
    if not isinstance(num_iterations, int) or num_iterations < 1:
        raise ValueError(f"Invalid num_iterations={num_iterations}. Must be an integer >= 1.")

    # Validate m parameter
    m = config["evaluation"].get("m", 1)
    if not isinstance(m, int) or m < 1:
        raise ValueError(f"Invalid m={m}. Must be an integer >= 1.")

    # Validate dry_run
    dry_run = config["evaluation"].get("dry_run", True)
    if not isinstance(dry_run, bool):
        raise ValueError(f"Invalid dry_run={dry_run}. Must be a boolean.")

    # Validate timeout
    timeout = config["evaluation"].get("timeout", 600)
    if not isinstance(timeout, (int, float)) or timeout < 0:
        raise ValueError(f"Invalid timeout={timeout}. Must be a non-negative number.")

    # Validate timeout_all (optional)
    timeout_all = config["evaluation"].get("timeout_all", None)
    if timeout_all is not None:
        if not isinstance(timeout_all, (int, float)) or timeout_all < 0:
            raise ValueError(f"Invalid timeout_all={timeout_all}. Must be a non-negative number.")

    # Validate use_incremental
    use_incremental = config["solver"].get("use_incremental", True)
    if not isinstance(use_incremental, bool):
        raise ValueError(f"Invalid use_incremental={use_incremental}. Must be a boolean.")

    # Validate task_overrides in each KB section
    for kb_cfg in config["kb"]:
        for pattern, override_task in kb_cfg.get("task_overrides", {}).items():
            if override_task not in VALID_TASKS:
                raise ValueError(
                    f"Invalid task_override '{override_task}' for pattern '{pattern}' "
                    f"in KB '{kb_cfg.get('name', '?')}'. Must be one of: {VALID_TASKS}"
                )

    return config


def resolve_path(relative: str) -> Path:
    """Resolve a project-relative path and verify it exists.

    Args:
        relative: Path relative to project root.

    Returns:
        Resolved absolute Path.

    Raises:
        FileNotFoundError: If path does not exist.
    """
    resolved = ROOT_PROJECT_FOLDER / relative
    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {resolved}")
    return resolved


def resolve_task(tc_file: str, default_task: str, overrides: Dict[str, str]) -> str:
    """Resolve effective task for a testcase file using glob overrides.

    Args:
        tc_file: Test case filename.
        default_task: Default task from evaluation config.
        overrides: Dict of glob pattern → task value.

    Returns:
        Effective task string ("1" or "all").
    """
    for pattern, override_task in overrides.items():
        if fnmatch.fnmatch(tc_file, pattern):
            return override_task
    return default_task


def build_model(
    kb_path: Path,
    testsuite_path: Optional[Path],
    use_incremental: bool = True,
) -> Any:
    """Build a DiagnosisModel configured for the specified algorithm.

    Args:
        kb_path: Absolute path to UVL model file.
        testsuite_path: Path to test case file (required for kbdiag, wipeoutr_t).
        use_incremental: Whether to enable incremental solver mode.

    Returns:
        Configured DiagnosisModel.
    """
    builder = DiagnosisModelBuilder.from_uvl(str(kb_path))

    testsuite = TestSuiteReader(str(testsuite_path)).transform()
    builder.with_positive_testcases(testsuite)
    builder.use_incremental(use_incremental)
    return builder.build()


def create_operation(
    algorithm: str,
    task: str,
    solver_name: str,
    m: int = 1,
) -> PySATAbstractExplanation:
    """Create and configure an operation for the given algorithm.

    Args:
        algorithm: Algorithm name.
        task: "1" or "all".
        solver_name: SAT solver name.
        m: KBDiag m parameter (only used for kbdiag algorithm).

    Returns:
        Configured operation ready for execute().
    """
    max_diag = 1 if task == "1" else 10

    if algorithm == "kbdiag":
        op_builder = PySATTestcaseBuilder.for_debugging()
        op_builder.with_max_diagnoses(max_diag).with_solver(solver_name)
        op_builder.with_m(m)
        return op_builder.build()
    elif algorithm == "quickxplain_with_testcases":
        op_builder = PySATTestcaseQuickXplainBuilder.for_debugging()
        op_builder.with_max_diagnoses(max_diag).with_solver(solver_name)
        return op_builder.build()

    raise ValueError(f"Unknown algorithm: {algorithm}")


def run_single_scenario(
    kb_model_path: str,
    algorithm: str,
    tc_path: str,
    effective_task: str,
    solver_name: str,
    m: int,
    num_iterations: int,
    profiler_preset_name: str,
    profiler_enabled: bool,
    use_incremental: bool = True,
) -> ScenarioResult:
    """Run all iterations of one scenario in a worker process.

    Top-level function required for ProcessPoolExecutor (must be picklable).
    Each worker independently builds models and creates solvers.
    """
    from explanation.operations.algorithms.profiler import (
        ProfilerPreset, use_global_profiler,
    )
    preset = getattr(ProfilerPreset, profiler_preset_name, ProfilerPreset.DISABLED)
    profiler = use_global_profiler(preset)

    kb_path = Path(kb_model_path)
    tc = Path(tc_path)
    scenario = ScenarioResult()

    # Iterates scenario; profiles operation; captures results and metrics
    for _ in range(num_iterations):
        model = build_model(kb_path, tc, use_incremental)
        operation = create_operation(algorithm, effective_task, solver_name, m=m)

        profiler.reset()
        profiler.start()
        try:
            operation.execute(model)
        finally:
            profiler.stop()

        result = operation.get_result()
        metrics = profiler.get_all_metrics() if profiler_enabled else {}
        # runtime_first = 0.0
        # runtime_all = 0.0
        # if 'kbdiag_runtime' in metrics:
        #     runtime_first = metrics['kbdiag_runtime'][0]
        #     runtime_all = sum(metrics['kbdiag_runtime'])
        # elif 'quickxplain_with_testcases_runtime' in metrics:
        #     runtime_first = metrics['hsdag_runtime'][0]
        #     runtime_all = sum(metrics['hsdag_runtime'])
        runtime_key = ('kbdiag_runtime' if 'kbdiag_runtime' in metrics
                       else 'hsdag_runtime' if 'quickxplain_with_testcases_runtime' in metrics
                       else None)
        if runtime_key:
            runtime_first = metrics[runtime_key][0]
            runtime_all = sum(metrics[runtime_key])
        else:
            runtime_first = 0.0
            runtime_all = 0.0

        # Extract structured diagnosis data from HSDAG
        diagnoses = operation.get_diagnoses()
        formatted_diags = [model.format_diagnoses([d]) for d in diagnoses]
        diag_sizes = [len(d) for d in diagnoses]

        scenario.iterations.append(IterationResult(
            result=result,
            time_first=runtime_first,
            time_all=runtime_all,
            metrics=metrics,
            formatted_diagnoses=formatted_diags,
            diag_sizes=diag_sizes,
            num_diagnoses=len(diagnoses),
        ))

    return scenario


def _worker_wrapper(queue: multiprocessing.Queue, *args) -> None:
    """Wrapper for multiprocessing.Process that puts result on queue."""
    try:
        result = run_single_scenario(*args)
        queue.put(result)
    except Exception as e:
        queue.put(e)


def write_profiler_metrics(f, metrics: Dict[str, Any]) -> None:
    """Write profiler counter metrics to result file."""
    f.write("\t--- Profiler ---\n")
    for key, label in PROFILER_COUNTER_LABELS.items():
        if key in metrics:
            f.write(f"\t{label}: {metrics[key]}\n")


def _get_cc_count(metrics: Dict[str, Any]) -> int:
    """Extract total consistency check count from profiler metrics."""
    return metrics.get("is_consistent_test_cases_calls", 0)


def write_iteration(
    f,
    kb_name: str,
    tc_file: str,
    iter_result: 'IterationResult',
    effective_task: str,
    profiler_on: bool,
) -> None:
    """Write per-iteration output to result file.

    task=1 format:
        KB TC
            Diagnosis: [c1, c2]
            |D|: 2
            CC: 20
            Time: 0.000778 s

    task=all format:
        KB TC
            Diagnosis 1 (|D|=7): [c1, c2, ...]
            Diagnosis 2 (|D|=5): [c1, c2, ...]
            #Diagnoses: 2
            CC: 150
            Time: 0.023000 s
    """
    f.write(f"{kb_name} {tc_file}\n")

    if effective_task == "1":
        diag_str = iter_result.formatted_diagnoses[0] if iter_result.formatted_diagnoses else "none"
        diag_size = iter_result.diag_sizes[0] if iter_result.diag_sizes else 0
        f.write(f"\tDiagnosis: {diag_str}\n")
        f.write(f"\t|D|: {diag_size}\n")
    else:
        # path_label_cumulative_runtime aligns with diagnoses only for CONFLICT-type
        # labelers (quickxplain_with_testcases). For DIAGNOSIS-type (kbdiag),
        # path_labels are conflicts, not diagnoses.
        is_conflict_labeler = 'quickxplain_with_testcases_runtime' in iter_result.metrics
        cumulative_rts = (iter_result.metrics.get('path_label_cumulative_runtime', [])
                          if is_conflict_labeler else [])
        for i, (diag_str, size) in enumerate(
            zip(iter_result.formatted_diagnoses, iter_result.diag_sizes), 1
        ):
            if i <= len(cumulative_rts):
                f.write(f"\tDiagnosis {i} (|D|={size}, t={cumulative_rts[i-1]:.6f}s): {diag_str}\n")
            else:
                f.write(f"\tDiagnosis {i} (|D|={size}, t={iter_result.metrics['kbdiag_runtime'][i-1]:.6f}s): {diag_str}\n")
        f.write(f"\t#Diagnoses: {iter_result.num_diagnoses}\n")

    if profiler_on and iter_result.metrics:
        cc = _get_cc_count(iter_result.metrics)
        f.write(f"\tCC: {cc}\n")

    runtime_str = ('KBDiag runtime' if 'kbdiag_runtime' in iter_result.metrics
                   else 'QuickXPlain+TC runtime' if 'quickxplain_with_testcases_runtime' in iter_result.metrics
                   else None)
    if effective_task == "1":
        f.write(f"\t{runtime_str}: {iter_result.time_first:.6f} s\n")
    else:
        f.write(f"\t{runtime_str}: {iter_result.time_all:.6f} s\n")

    if profiler_on and iter_result.metrics:
        write_profiler_metrics(f, iter_result.metrics)

def write_timeout(f, kb_name: str, tc_file: str, timeout: float) -> None:
    """Write timeout marker to result file."""
    f.write(f"{kb_name} {tc_file}\n")
    f.write(f"\tDiag: TO\n")
    f.write(f"\tTime: {timeout:.6f} s (timeout)\n")


def write_summary(
    f,
    algorithm: str,
    m: int,
    task: str,
    averages: Dict[str, float],
    summary_data: Dict[str, Dict[str, Any]],
) -> None:
    """Write summary table to result file.

    Args:
        summary_data: tc_key → {"first_diag_size": int, "num_diagnoses": int}
    """
    f.write(f"\n=== Evaluation Results: {algorithm} (m={m}, task={task}) ===\n")
    f.write(f"{'Testcase':<25} | {'Avg Time (s)':>12} | {'|D|':>5} | {'#Diag':>6}\n")
    f.write("-" * 57 + "\n")
    for tc, avg_time in averages.items():
        data = summary_data.get(tc, {})
        d_size = data.get("first_diag_size", "?")
        n_diag = data.get("num_diagnoses", "?")
        f.write(f"{tc:<25} | {avg_time:>12.6f} | {d_size:>5} | {n_diag:>6}\n")


def format_summary_text(
    algorithm: str,
    m: int,
    task: str,
    averages: Dict[str, float],
    summary_data: Dict[str, Dict[str, Any]],
) -> str:
    """Format summary table as plain text (for email body)."""
    lines = [
        f"Evaluation Results: {algorithm} (m={m}, task={task})",
        f"{'Testcase':<25} | {'Avg Time (s)':>12} | {'|D|':>5} | {'#Diag':>6}",
        "-" * 57,
    ]
    for tc, avg_time in averages.items():
        data = summary_data.get(tc, {})
        d_size = data.get("first_diag_size", "?")
        n_diag = data.get("num_diagnoses", "?")
        lines.append(f"{tc:<25} | {avg_time:>12.6f} | {d_size:>5} | {n_diag:>6}")
    return "\n".join(lines)


def run_warmup(config: Dict[str, Any], m: int) -> None:
    """Run 1 dry iteration per KB to warm up solver.

    Args:
        config: Parsed TOML config dict.
        m: KBDiag m parameter.
    """
    eval_cfg = config["evaluation"]
    algorithm = eval_cfg["algorithm"]
    task = eval_cfg["task"]
    solver_name = config["solver"].get("solver_name", "glucose3")

    use_incremental = config["solver"].get("use_incremental", True)

    print("Warming up...")
    for kb_cfg in config["kb"]:
        kb_name = kb_cfg["name"]
        if not kb_cfg.get("testcases"):
            print(f"\tWarmup: {kb_name} skipped (no testcases)")
            continue
        kb_path = resolve_path(kb_cfg["model"])
        first_tc = kb_cfg["testcases"][0]
        scenarios_dir = kb_cfg.get("scenarios_dir", "")
        tc_path = resolve_path(f"{scenarios_dir}/{first_tc}")

        model = build_model(kb_path, tc_path, use_incremental)
        operation = create_operation(algorithm, task, solver_name, m=m)
        operation.execute(model)
        print(f"\tWarmup: {kb_name} done")
    print("Warmup complete.\n")


def run_evaluation(config: Dict[str, Any]) -> None:
    """Run the evaluation loop as defined in config.

    Args:
        config: Parsed TOML config dict.
    """
    eval_cfg = config["evaluation"]
    algorithm = eval_cfg["algorithm"]
    task = eval_cfg["task"]
    num_iterations = eval_cfg.get("num_iterations", 3)
    m = eval_cfg.get("m", 1)
    dry_run = eval_cfg.get("dry_run", True)
    timeout = eval_cfg.get("timeout", 600)
    timeout_all = eval_cfg.get("timeout_all", None)

    solver_name = config["solver"].get("solver_name", "glucose3")
    use_incremental = config["solver"].get("use_incremental", True)

    profiler_cfg = config.get("profiler", {})
    profiler_enabled = profiler_cfg.get("enabled", False)
    if profiler_enabled:
        preset_name = profiler_cfg.get("preset", "benchmark").upper()
        profiler_preset = getattr(ProfilerPreset, preset_name, ProfilerPreset.BENCHMARK)
    else:
        profiler_preset = ProfilerPreset.DISABLED

    # Set up global profiler (without starting it yet)
    profiler = use_global_profiler(profiler_preset)

    result_path_cfg = config["output"].get("result_path", "results")
    result_dir = ROOT_PROJECT_FOLDER / result_path_cfg / task
    result_dir.mkdir(parents=True, exist_ok=True)

    # Warmup before measurement
    if dry_run:
        run_warmup(config, m)

    # Collect summary data across all KBs
    all_averages_first: Dict[str, float] = {}
    all_averages_all: Dict[str, float] = {}
    all_summary: Dict[str, Dict[str, Any]] = {}

    for kb_cfg in config["kb"]:
        kb_name = kb_cfg["name"]
        kb_path = resolve_path(kb_cfg["model"])
        scenarios_dir = kb_cfg.get("scenarios_dir", "")
        task_overrides = kb_cfg.get("task_overrides", {})

        # Track which output files are used for per-KB summaries
        used_out_paths: Dict[str, Any] = {}  # task_label → path

        for tc_file in kb_cfg["testcases"]:
            effective_task = resolve_task(tc_file, task, task_overrides)
            effective_timeout = timeout_all if (effective_task == "all" and timeout_all is not None) else timeout
            tc_path = resolve_path(f"{scenarios_dir}/{tc_file}")

            # Run scenario (with or without timeout)
            worker_args = (
                str(kb_path), algorithm, str(tc_path),
                effective_task, solver_name, m, num_iterations,
                profiler_preset.name, profiler_enabled, use_incremental,
            )
            if effective_timeout > 0:
                queue: multiprocessing.Queue = multiprocessing.Queue()
                proc = multiprocessing.Process(
                    target=_worker_wrapper, args=(queue, *worker_args),
                )
                proc.start()
                proc.join(timeout=effective_timeout)
                if proc.is_alive():
                    proc.kill()
                    proc.join()
                    scenario_result = ScenarioResult(timed_out=True)
                    print(f"\t[{kb_name}] {tc_file}: TIMEOUT ({effective_timeout}s)")
                else:
                    worker_result = queue.get_nowait()
                    if isinstance(worker_result, Exception):
                        raise worker_result
                    scenario_result = worker_result
            else:
                # No timeout — run inline (zero overhead)
                scenario_result = run_single_scenario(*worker_args)

            tc_key = f"{kb_name}/{tc_file}"

            if scenario_result.timed_out:
                # Write TO marker to output files
                if effective_task == "all":
                    for out_task in ("1", "all"):
                        out_dir = result_dir.parent / out_task
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / f"results_{algorithm}_{kb_name}_{out_task}.txt"
                        used_out_paths[out_task] = out_path
                        with open(out_path, "a") as f:
                            write_timeout(f, kb_name, tc_file, effective_timeout)
                else:
                    out_path = result_dir / f"results_{algorithm}_{kb_name}_{effective_task}.txt"
                    used_out_paths[effective_task] = out_path
                    with open(out_path, "a") as f:
                        write_timeout(f, kb_name, tc_file, effective_timeout)

                all_averages_first[tc_key] = float(effective_timeout)
                all_averages_all[tc_key] = float(effective_timeout)
                all_summary[tc_key] = {"first_diag_size": "TO", "num_diagnoses": "TO"}
            else:
                # Write iteration results
                total_time_all = 0.0
                total_time_first = 0.0
                last_iter = None
                for iter_res in scenario_result.iterations:
                    last_iter = iter_res

                    if effective_task == "all":
                        total_time_all += iter_res.time_all
                        total_time_first += iter_res.time_first

                        for out_task in ("1", "all"):
                            out_dir = result_dir.parent / out_task
                            out_dir.mkdir(parents=True, exist_ok=True)
                            out_path = out_dir / f"results_{algorithm}_{kb_name}_{out_task}.txt"
                            used_out_paths[out_task] = out_path
                            with open(out_path, "a") as f:
                                write_iteration(f, kb_name, tc_file, iter_res,
                                                out_task, profiler_enabled)
                    else:
                        total_time_all += iter_res.time_first

                        out_path = result_dir / f"results_{algorithm}_{kb_name}_{effective_task}.txt"
                        used_out_paths[effective_task] = out_path
                        with open(out_path, "a") as f:
                            write_iteration(f, kb_name, tc_file, iter_res,
                                            effective_task, profiler_enabled)

                all_averages_all[tc_key] = total_time_all / num_iterations
                all_averages_first[tc_key] = total_time_first / num_iterations

                if last_iter is not None:
                    first_size = last_iter.diag_sizes[0] if last_iter.diag_sizes else 0
                    all_summary[tc_key] = {
                        "first_diag_size": first_size,
                        "num_diagnoses": last_iter.num_diagnoses,
                    }

        # Per-KB summary in each used output file
        kb_averages_first = {k: v for k, v in all_averages_first.items() if k.startswith(f"{kb_name}/")}
        kb_averages_all = {k: v for k, v in all_averages_all.items() if k.startswith(f"{kb_name}/")}
        kb_summary = {k: v for k, v in all_summary.items() if k.startswith(f"{kb_name}/")}
        for out_task, out_path in used_out_paths.items():
            with open(out_path, "a") as f:
                if out_task == "all":
                    write_summary(f, algorithm, m, out_task, kb_averages_all, kb_summary)
                else:
                    write_summary(f, algorithm, m, out_task, kb_averages_first, kb_summary)

    # Stdout profiler summary (only useful when running inline, i.e. timeout=0 or timeout_all=0)
    any_inline = timeout == 0 or timeout_all == 0
    if profiler_enabled and any_inline:
        profiler.print_summary()

    # Print overall summary to stdout
    if task == "all":
        print(f"\n=== Evaluation Results: {algorithm} (m={m}, task={task}) ===")
        print(f"{'Testcase':<35} | {'Avg Time (s)':>12} | {'|D|':>5} | {'#Diag':>6}")
        print("-" * 65)
        for tc, avg_time in all_averages_all.items():
            data = all_summary.get(tc, {})
            d_size = data.get("first_diag_size", "?")
            n_diag = data.get("num_diagnoses", "?")
            print(f"{tc:<35} | {avg_time:>12.6f} | {d_size:>5} | {n_diag:>6}")
    else:
        print(f"\n=== Evaluation Results: {algorithm} (m={m}, task={task}) ===")
        print(f"{'Testcase':<35} | {'Avg Time (s)':>12} | {'|D|':>5} | {'#Diag':>6}")
        print("-" * 65)
        for tc, avg_time in all_averages_first.items():
            data = all_summary.get(tc, {})
            d_size = data.get("first_diag_size", "?")
            n_diag = data.get("num_diagnoses", "?")
            print(f"{tc:<35} | {avg_time:>12.6f} | {d_size:>5} | {n_diag:>6}")

    # Email notification
    email_cfg = config.get("email", {})
    if email_cfg.get("enabled", False):
        try:
            from apps.email_notify import send_evaluation_email
            prefix = email_cfg.get("subject_prefix", "[KBDiag]")
            subject = f"{prefix} Evaluation Complete - {algorithm}"
            body = format_summary_text(algorithm, m, task, all_averages_first, all_summary)
            send_evaluation_email(subject, body)
        except Exception as e:
            print(f"Warning: Email notification failed: {e}")


def main() -> None:
    """Entry point: parse CLI arg and run evaluation."""
    if len(sys.argv) < 2:
        print("Usage: python -m apps.eval_runner <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    run_evaluation(config)


if __name__ == "__main__":
    main()
