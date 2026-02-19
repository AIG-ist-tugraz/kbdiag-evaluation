#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

"""Evaluation script for KBDiag diagnosis algorithms.

Reads a TOML config and runs the specified algorithm on each KB/test-case
combination, writing per-iteration results and averages to a text file.

Usage:
    python -m apps.kbdiag_eval apps/conf/kbdiag_eval.toml
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from explanation.models.diagnosis_model_builder import DiagnosisModelBuilder
from explanation.operations.algorithms.profiler import (
    ProfilerPreset,
    profiler_session,
)
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation
from explanation.operations.pysat_explanation_builder import (
    PySATDiagnosisBuilder,
    PySATRedundancyConstraintsBuilder,
    PySATRedundancyTestCasesBuilder,
    PySATTestcaseBuilder,
)
from explanation.transformations.testsuite_reader import TestSuiteReader

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent

VALID_ALGORITHMS = {"kbdiag", "fastdiag", "quickxplain", "wipeoutr_fm", "wipeoutr_t"}
VALID_TASKS = {"1", "all"}


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


def build_model(
    kb_path: Path,
    algorithm: str,
    testsuite_path: Optional[Path],
) -> Any:
    """Build a DiagnosisModel configured for the specified algorithm.

    Args:
        kb_path: Absolute path to UVL model file.
        algorithm: Algorithm name from VALID_ALGORITHMS.
        testsuite_path: Path to test case file (required for kbdiag, wipeoutr_t).

    Returns:
        Configured DiagnosisModel.
    """
    builder = DiagnosisModelBuilder.from_uvl(str(kb_path))

    if algorithm == "kbdiag":
        testsuite = TestSuiteReader(str(testsuite_path)).transform()
        builder.with_positive_testcases(testsuite)
    elif algorithm == "wipeoutr_t":
        testsuite = TestSuiteReader(str(testsuite_path)).transform()
        builder.with_testcases(testsuite)
    elif algorithm == "wipeoutr_fm":
        builder.for_redundancy()

    builder.use_incremental()
    return builder.build()


def create_operation(
    algorithm: str,
    task: str,
    solver_name: str,
) -> PySATAbstractExplanation:
    """Create and configure an operation for the given algorithm.

    Args:
        algorithm: Algorithm name.
        task: "1" or "all".
        solver_name: SAT solver name.

    Returns:
        Configured operation ready for execute().
    """
    max_diag = 1 if task == "1" else None

    if algorithm == "kbdiag":
        op_builder = PySATTestcaseBuilder.for_debugging()
        op_builder.with_max_diagnoses(max_diag).with_solver(solver_name)
        return op_builder.build()
    elif algorithm == "fastdiag":
        op_builder = PySATDiagnosisBuilder.for_diagnosis()
        op_builder.with_max_diagnoses(max_diag).with_solver(solver_name)
        return op_builder.build()
    elif algorithm == "quickxplain":
        op_builder = PySATDiagnosisBuilder.for_conflict()
        op_builder.with_max_diagnoses(max_diag).with_solver(solver_name)
        return op_builder.build()
    elif algorithm == "wipeoutr_fm":
        op_builder = PySATRedundancyConstraintsBuilder.for_redundancy_constraints()
        op_builder.with_solver(solver_name)
        return op_builder.build()
    elif algorithm == "wipeoutr_t":
        op_builder = PySATRedundancyTestCasesBuilder.for_redundancy_test_cases()
        op_builder.with_solver(solver_name)
        return op_builder.build()

    raise ValueError(f"Unknown algorithm: {algorithm}")


def run_evaluation(config: Dict[str, Any]) -> None:
    """Run the evaluation loop as defined in config.

    Args:
        config: Parsed TOML config dict.
    """
    eval_cfg = config["evaluation"]
    algorithm = eval_cfg["algorithm"]
    task = eval_cfg["task"]
    num_iterations = eval_cfg.get("num_iterations", 3)

    solver_name = config["solver"].get("solver_name", "glucose3")

    profiler_cfg = config.get("profiler", {})
    profiler_enabled = profiler_cfg.get("enabled", False)
    if profiler_enabled:
        preset_name = profiler_cfg.get("preset", "benchmark").upper()
        profiler_preset = getattr(ProfilerPreset, preset_name, ProfilerPreset.BENCHMARK)
    else:
        profiler_preset = ProfilerPreset.DISABLED

    result_path_cfg = config["output"].get("result_path", "results")
    result_dir = ROOT_PROJECT_FOLDER / result_path_cfg / task
    result_dir.mkdir(parents=True, exist_ok=True)

    with profiler_session(profiler_preset) as profiler:
        for kb_cfg in config["kb"]:
            kb_name = kb_cfg["name"]
            kb_path = resolve_path(kb_cfg["model"])
            scenarios_dir = kb_cfg.get("scenarios_dir", "")

            averages: Dict[str, float] = {}
            out_file = f"results_{algorithm}_{kb_name}_{task}.txt"
            out_path = result_dir / out_file

            with open(out_path, "a") as f:
                for tc_file in kb_cfg["testcases"]:
                    tc_path = resolve_path(f"{scenarios_dir}/{tc_file}")

                    total_time = 0.0
                    for _ in range(num_iterations):
                        model = build_model(kb_path, algorithm, tc_path)
                        operation = create_operation(algorithm, task, solver_name)

                        start = time.time()
                        operation.execute(model)
                        end = time.time()

                        result = operation.get_result()
                        iteration_time = (end - start) * 1000
                        total_time += iteration_time

                        f.write(f"{kb_name} {tc_file}\n")
                        f.write(f"\tOutput: {result}\n")
                        f.write(f"\tTime: {iteration_time} ms\n")

                    average_time = total_time / num_iterations
                    f.write(f"\tAverage Time: {average_time} ms\n")
                    averages[tc_file] = average_time

                f.write(f"\nAverages\n")
                for key, value in averages.items():
                    f.write(f"\t{key}: {value} ms\n")

        if profiler_enabled:
            profiler.print_summary()


def main() -> None:
    """Entry point: parse CLI arg and run evaluation."""
    if len(sys.argv) < 2:
        print("Usage: python -m apps.kbdiag_eval <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    run_evaluation(config)


if __name__ == "__main__":
    main()
