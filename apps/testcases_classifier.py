#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Test case classifier for feature models.

Classifies test cases in a testsuite as violated (inconsistent with FM,
<= N conflict sets), non-violated (consistent), or ignored (too many conflicts).

Uses a two-path approach:
  - Fast path: PySAT solver consistency check (most TCs)
  - Slow path: HSDAG conflict counting (only for violated TCs)

Usage:
    python -m apps.testcases_classifier apps/conf/testcases_classifier.toml
"""

import gc
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from pysat.solvers import Solver

from flamapy.metamodels.configuration_metamodel.models import Configuration
from flamapy.metamodels.fm_metamodel.models import Feature

from explanation.models.diagnosis_model_builder import DiagnosisModelBuilder
from explanation.models.testsuite import Assignment, TestCase, TestSuite
from explanation.operations.pysat_explanation_builder import PySATDiagnosisBuilder

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent

TESTSUITE_HEADER_LINES = 6  # total, dead, false_opt, full_mand, false_mand, partial


def load_config(config_path: str) -> Dict[str, Any]:
    """Parse and validate a TOML classifier config."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "rb") as f:
        config = tomllib.load(f)

    for section in ("classification", "output"):
        if section not in config:
            raise ValueError(f"Missing required section: [{section}]")

    if "fm" not in config:
        raise ValueError("No [[fm]] entries found in config")

    return config


def resolve_path(relative: str) -> Path:
    """Resolve a project-relative path and verify it exists."""
    resolved = ROOT_PROJECT_FOLDER / relative
    if not resolved.exists():
        raise FileNotFoundError(f"Path not found: {resolved}")
    return resolved


def read_testsuite(path: Path) -> TestSuite:
    """Read a .testsuite file, skipping the 6-line header.

    The .testsuite format (from testsuite_gen.py):
        <total_count>
        <dead_count>
        <false_optional_count>
        <full_mandatory_count>
        <false_mandatory_count>
        <partial_count>
        <tc_1>
        <tc_2>
        ...
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[TESTSUITE_HEADER_LINES:]

    testcases = [
        TestCase([
            Assignment(part.strip().lstrip("~"), not part.strip().startswith("~"))
            for part in line.split("&")
        ])
        for line in lines
        if line.strip()
    ]
    return TestSuite(testcases)


class TestCasesClassifier:
    """Classifies test cases against feature model constraints.

    Each TC is classified as:
    - non-violated: consistent with FM
    - violated: inconsistent, with <= max_conflict_sets conflicts
    - ignored: inconsistent, with > max_conflict_sets conflicts
    """

    def __init__(
        self,
        fm: Any,
        fm_name: str,
        max_conflict_sets: int = 3,
        solver_name: str = "glucose3",
    ) -> None:
        self._fm = fm
        self._name = fm_name
        self._max_conflict_sets = max_conflict_sets
        self._solver_name = solver_name

        self._violated: List[str] = []
        self._non_violated: List[str] = []
        self._ignored: int = 0

    def classify(self, testsuite: TestSuite) -> None:
        """Classify all test cases in the testsuite.

        Fast path: single PySAT solver with assumptions for consistency check.
        Slow path: HSDAG conflict counting only for violated TCs.
        """
        # Build base model (Use Case 3: FM diagnosis)
        model = (DiagnosisModelBuilder
                 .from_feature_model(self._fm)
                 .use_incremental()
                 .build())

        variables = model.variables  # Dict[str, int]
        base_assumptions = model.get_c() + model.get_b()
        kb_clauses = model.get_kb()

        # Create persistent solver for fast consistency checks
        solver = Solver(self._solver_name, bootstrap_with=kb_clauses)

        total = len(testsuite.testcases)
        print(f"\t[{self._name}] Classifying {total} test cases...")

        try:
            for i, tc in enumerate(testsuite.testcases):
                # Convert TC assignments to SAT literals
                tc_literals = self._tc_to_literals(tc, variables)

                # Fast path: consistency check
                assumptions = base_assumptions + tc_literals
                is_consistent = solver.solve(assumptions=assumptions)

                if is_consistent:
                    self._non_violated.append(self._tc_to_string(tc))
                else:
                    # Slow path: count conflicts
                    num_conflicts = self._count_conflicts(tc)
                    if num_conflicts <= self._max_conflict_sets:
                        self._violated.append(self._tc_to_string(tc))
                    else:
                        self._ignored += 1

                if (i + 1) % 1000 == 0:
                    print(f"\t[{self._name}] Processed {i + 1}/{total} TCs")

                # Periodic GC for violated TCs (HSDAG models)
                if (i + 1) % 100 == 0 and self._violated:
                    gc.collect()

        finally:
            solver.delete()

        print(f"\t[{self._name}] Classification complete: "
              f"violated={len(self._violated)}, "
              f"non_violated={len(self._non_violated)}, "
              f"ignored={self._ignored}")

    def _count_conflicts(self, tc: TestCase) -> int:
        """Count conflict sets for a violated TC using HSDAG + QuickXPlain.

        Builds a per-TC model (Use Case 4: error diagnosis) and runs
        HSDAG with max_conflicts = threshold + 1 to detect overflow.
        """
        config = Configuration({
            Feature(a.feature): a.value for a in tc.assignments
        })
        tc_model = (DiagnosisModelBuilder
                    .from_feature_model(self._fm)
                    .with_test_case(config)
                    .use_incremental()
                    .build())

        op = (PySATDiagnosisBuilder
              .for_conflict()
              .with_max_conflicts(self._max_conflict_sets + 1)
              .with_solver(self._solver_name)
              .build())
        op.execute(tc_model)

        num_conflicts = len(op.hsdag.get_conflicts())
        op.hsdag = None
        return num_conflicts

    @staticmethod
    def _tc_to_literals(tc: TestCase, variables: Dict[str, int]) -> List[int]:
        """Convert TC assignments to SAT variable literals.

        Raises:
            KeyError: If a feature name is not found in the variables map.
        """
        literals = []
        for a in tc.assignments:
            var = variables.get(a.feature)
            if var is None:
                raise KeyError(f"Feature '{a.feature}' not in model variables")
            literals.append(var if a.value else -var)
        return literals

    @staticmethod
    def _tc_to_string(tc: TestCase) -> str:
        """Format TC as string: ~feature1 & feature2 & feature3."""
        parts = []
        for a in tc.assignments:
            parts.append(a.feature if a.value else f"~{a.feature}")
        return " & ".join(parts)

    def write_to_file(self, output_dir: str) -> None:
        """Write .classifiedts output file.

        Format:
            <violated_count>
            <violated_tc_1>
            ...
            <non_violated_count>
            <non_violated_tc_1>
            ...
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        filepath = out_path / f"{self._name}.classifiedts"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{len(self._violated)}\n")
            for tc in self._violated:
                f.write(f"{tc}\n")
            f.write(f"{len(self._non_violated)}\n")
            for tc in self._non_violated:
                f.write(f"{tc}\n")

        print(f"\t[{self._name}] Written to {filepath}")


def classify_single_fm(
    fm_cfg: Dict[str, str],
    max_conflict_sets: int,
    solver_name: str,
    output_dir: str,
) -> None:
    """Classify test cases for a single feature model.

    Top-level function required for ProcessPoolExecutor (must be picklable).
    Each worker independently loads its FM and creates its own solver.
    """
    from flamapy.metamodels.fm_metamodel.transformations import UVLReader

    name = fm_cfg["name"]
    model_path = str(resolve_path(fm_cfg["model"]))
    testsuite_path = resolve_path(fm_cfg["testsuite"])

    print(f"[{name}] Loading feature model from {model_path}")
    fm = UVLReader(model_path).transform()

    print(f"[{name}] Reading testsuite from {testsuite_path}")
    testsuite = read_testsuite(testsuite_path)
    print(f"[{name}] Loaded {len(testsuite.testcases)} test cases")

    classifier = TestCasesClassifier(
        fm=fm,
        fm_name=name,
        max_conflict_sets=max_conflict_sets,
        solver_name=solver_name,
    )
    classifier.classify(testsuite)

    abs_output = str(ROOT_PROJECT_FOLDER / output_dir)
    classifier.write_to_file(abs_output)


def main() -> None:
    """Entry point: parse CLI config and classify test cases."""
    if len(sys.argv) < 2:
        print("Usage: python -m apps.testcases_classifier <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    classification_cfg = config["classification"]
    max_conflict_sets = classification_cfg.get("max_conflict_sets", 3)
    solver_name = config.get("solver", {}).get("solver_name", "glucose3")
    output_dir = config["output"]["output_dir"]

    fm_configs = config["fm"]
    if not fm_configs:
        print("No [[fm]] entries found in config. Nothing to classify.")
        return

    max_workers_cfg = classification_cfg.get("max_workers", 0)

    # Auto-detect: min(num_fms, cpu_count), or use configured value
    if max_workers_cfg <= 0:
        max_workers = min(len(fm_configs), os.cpu_count() or 1)
    else:
        max_workers = min(max_workers_cfg, len(fm_configs))

    if max_workers <= 1:
        # Sequential fallback
        for fm_cfg in fm_configs:
            classify_single_fm(fm_cfg, max_conflict_sets, solver_name, output_dir)
    else:
        print(f"Running {len(fm_configs)} FMs in parallel (max_workers={max_workers})")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    classify_single_fm, fm_cfg,
                    max_conflict_sets, solver_name, output_dir,
                ): fm_cfg["name"]
                for fm_cfg in fm_configs
            }
            failed = []
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"[{name}] FAILED: {e}")
                    failed.append(name)
            if failed:
                sys.exit(1)


if __name__ == "__main__":
    main()
