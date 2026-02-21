#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Test cases selector for classified test suites.

Selects test case scenarios from classified test suites (.classifiedts)
with configurable cardinalities and violation ratios. Port of
TestCasesSelectorV1.java for real-world knowledge bases.

Usage:
    python -m apps.testcases_selector apps/conf/testcases_selector.toml
"""

import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def load_config(config_path: str) -> Dict[str, Any]:
    """Parse and validate a TOML test cases selector config."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "rb") as f:
        config = tomllib.load(f)

    for section in ("selection", "output"):
        if section not in config:
            raise ValueError(f"Missing required section: [{section}]")

    if "ts" not in config:
        raise ValueError("No [[ts]] entries found in config")

    return config


class TestCasesSelector:
    """Selects test case scenarios from a classified test suite.

    Implements incremental accumulation: for cardinalities [5, 10, 25],
    selects 5 TCs, then 5 MORE (total 10), then 15 MORE (total 25).
    Each cardinality output is a superset of the previous.
    """

    def __init__(
        self,
        name: str,
        classified_ts_path: str,
        cardinalities: List[int],
        num_scenarios: int,
        violated_percent: float,
        seed: Optional[int] = None,
        min_priority_conflicts: int = 2,
        selection_strategy: str = "random",
    ) -> None:
        self._name = name
        self._classified_ts_path = classified_ts_path
        self._cardinalities = cardinalities
        self._num_scenarios = num_scenarios
        self._violated_percent = violated_percent
        self._seed = seed
        self._min_priority_conflicts = min_priority_conflicts
        self._selection_strategy = selection_strategy

        self._violated: List[tuple[int, str, Set[int]]] = []  # (count, tc, constraint_ids)
        self._nonviolated: List[str] = []

    def select(self, output_dir: str) -> None:
        """Run selection for all scenarios and cardinalities."""
        self._read_classified_ts()

        # Split violated pool into priority (>= threshold) and regular (< threshold)
        priority_pool = [(c, tc, ids) for c, tc, ids in self._violated
                         if c >= self._min_priority_conflicts]
        regular_pool = [(c, tc, ids) for c, tc, ids in self._violated
                        if c < self._min_priority_conflicts]
        nonviolated_pool = list(self._nonviolated)

        print(f"[{self._name}] Priority pool: {len(priority_pool)}, "
              f"Regular pool: {len(regular_pool)}, "
              f"Non-violated: {len(nonviolated_pool)}, "
              f"Strategy: {self._selection_strategy}")

        if len(nonviolated_pool) == 0:
            print(f"[{self._name}] No non-violated test cases, skipping")
            return

        for scenario_idx in range(self._num_scenarios):
            if self._seed is not None:
                random.seed(self._seed + scenario_idx)
            testcases: List[str] = []
            covered_ids: Set[int] = set()  # persists across cardinalities

            # Iterates cardinalities; selects and writes testcases from prioritized pools
            for cardinality in self._cardinalities:
                remaining = cardinality - len(testcases)

                # Java Math.round half-up (Python round uses banker's rounding)
                total_violated_available = len(priority_pool) + len(regular_pool)
                num_violated = min(
                    max(int(math.floor(remaining * self._violated_percent + 0.5)), 1),
                    total_violated_available,
                )
                num_nonviolated = max(
                    min(remaining - num_violated, len(nonviolated_pool)),
                    0,
                )

                if self._selection_strategy == "diversity":
                    # Diversity-weighted draw from priority pool first
                    selected_items = self._draw_diversity_weighted(
                        priority_pool, num_violated, covered_ids,
                    )
                    # Fill from regular pool if needed
                    remaining_violated = num_violated - len(selected_items)
                    if remaining_violated > 0:
                        selected_items.extend(self._draw_diversity_weighted(
                            regular_pool, remaining_violated, covered_ids,
                        ))
                    selected_violated = [tc for _, tc, _ in selected_items]
                else:
                    # Legacy random behavior
                    random.shuffle(priority_pool)
                    from_priority = min(num_violated, len(priority_pool))
                    selected_violated = [tc for _, tc, _ in priority_pool[:from_priority]]
                    priority_pool = priority_pool[from_priority:]

                    remaining_violated = num_violated - from_priority
                    if remaining_violated > 0:
                        random.shuffle(regular_pool)
                        from_regular = min(remaining_violated, len(regular_pool))
                        selected_violated.extend(tc for _, tc, _ in regular_pool[:from_regular])
                        regular_pool = regular_pool[from_regular:]

                testcases.extend(selected_violated)

                # Shuffle and select from nonviolated pool
                random.shuffle(nonviolated_pool)
                selected_nonviolated = nonviolated_pool[:num_nonviolated]
                nonviolated_pool = nonviolated_pool[num_nonviolated:]
                testcases.extend(selected_nonviolated)

                print(f"  [{self._name}] c{cardinality} scenario {scenario_idx}: "
                      f"violated={num_violated}, nonviolated={num_nonviolated}, "
                      f"total={len(testcases)}")

                if len(testcases) < cardinality:
                    print(f"  [{self._name}] WARNING: c{cardinality} scenario "
                          f"{scenario_idx}: only {len(testcases)} TCs (pool exhausted)")

                self._write_testcases(
                    output_dir, testcases, cardinality, scenario_idx,
                )

    @staticmethod
    def _parse_fingerprint(fingerprint_str: str) -> Set[int]:
        """Parse '{3,7},{5,12}' into flat set of constraint IDs: {3, 5, 7, 12}."""
        ids: Set[int] = set()
        for cs in fingerprint_str.split("},{"):
            cs = cs.strip("{}")
            for id_str in cs.split(","):
                if id_str.strip():
                    ids.add(int(id_str.strip()))
        return ids

    def _draw_diversity_weighted(
        self,
        pool: List[tuple[int, str, Set[int]]],
        n: int,
        covered_ids: Set[int],
    ) -> List[tuple[int, str, Set[int]]]:
        """Draw n items weighted by novel constraint IDs.

        Each draw updates covered_ids, biasing subsequent draws toward
        TCs with constraint IDs not yet covered.
        """
        selected = []
        # Selects items; updates covered IDs to bias subsequent draws
        for _ in range(min(n, len(pool))):
            weights = [max(len(ids - covered_ids), 1) for _, _, ids in pool]
            idx = random.choices(range(len(pool)), weights=weights, k=1)[0]
            item = pool.pop(idx)
            selected.append(item)
            covered_ids.update(item[2])
        return selected

    def _read_classified_ts(self) -> None:
        """Parse .classifiedts file with backward-compatible format detection.

        Formats:
          - New: count|fingerprint|tc (fingerprint starts with '{')
          - Old: count|tc
          - Legacy: tc only (no '|')
        """
        path = ROOT_PROJECT_FOLDER / self._classified_ts_path
        with open(path) as f:
            lines = f.read().splitlines()

        idx = 0
        num_violated = int(lines[idx]); idx += 1
        for _ in range(num_violated):
            line = lines[idx]; idx += 1
            parts = line.split("|", 2)
            if len(parts) == 3 and parts[1].startswith("{"):
                # New format: count|fingerprint|tc
                count = int(parts[0])
                constraint_ids = self._parse_fingerprint(parts[1])
                tc_str = parts[2]
                self._violated.append((count, tc_str, constraint_ids))
            elif len(parts) >= 2:
                # Old format: count|tc
                self._violated.append((int(parts[0]), parts[1], set()))
            else:
                # Legacy: tc only
                self._violated.append((1, line, set()))

        num_nonviolated = int(lines[idx]); idx += 1
        self._nonviolated = lines[idx:idx + num_nonviolated]

    def _write_testcases(
        self,
        output_dir: str,
        testcases: List[str],
        cardinality: int,
        scenario_idx: int,
    ) -> None:
        """Write testcases file: first line = count, then one TC per line."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        filename = f"{self._name}_c{cardinality}_{scenario_idx}.testcases"
        filepath = out_path / filename

        with open(filepath, "w") as f:
            f.write(f"{len(testcases)}\n")
            for tc in testcases:
                f.write(f"{tc}\n")

        print(f"  [{self._name}] Saved {filepath}")


def select_for_ts(
    ts_cfg: Dict[str, str],
    sel_config: Dict[str, Any],
    output_dir: str,
    seed: Optional[int] = None,
) -> str:
    """Top-level picklable function for ProcessPoolExecutor."""
    name = ts_cfg["name"]
    selector = TestCasesSelector(
        name=name,
        classified_ts_path=ts_cfg["classified_ts"],
        cardinalities=sel_config["cardinalities"],
        num_scenarios=sel_config.get("num_scenarios", 1),
        violated_percent=sel_config.get("violated_percent", 0.20),
        seed=seed,
        min_priority_conflicts=sel_config.get("min_priority_conflicts", 2),
        selection_strategy=sel_config.get("selection_strategy", "random"),
    )
    abs_output = str(ROOT_PROJECT_FOLDER / output_dir)
    selector.select(abs_output)
    return f"[{name}] Done"


def main() -> None:
    """Entry point: parse CLI config and run selection."""
    if len(sys.argv) < 2:
        print("Usage: python -m apps.testcases_selector <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    sel_config = config["selection"]
    output_dir = config["output"]["output_dir"]
    max_workers = config.get("concurrency", {}).get("max_workers", 4)

    seed = sel_config.get("seed", None)

    ts_entries = config["ts"]
    print(f"Processing {len(ts_entries)} test suites with {max_workers} workers")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(select_for_ts, ts_cfg, sel_config, output_dir, seed): ts_cfg["name"]
            for ts_cfg in ts_entries
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                print(result)
            except Exception as e:
                print(f"[{name}] Error: {e}")


if __name__ == "__main__":
    main()
