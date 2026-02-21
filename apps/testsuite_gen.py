#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

"""Test suite generator for feature models.

Generates 5 types of test cases: dead feature, false optional,
full mandatory, false mandatory, and partial configuration.

Usage:
    python -m apps/testsuite_gen.py apps/conf/testsuite_gen.toml
"""

import itertools
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def load_config(config_path: str) -> Dict[str, Any]:
    """Parse and validate a TOML testsuite generation config."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "rb") as f:
        config = tomllib.load(f)

    for section in ("generation", "output"):
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


class TestSuiteGenerator:
    """Generates a test suite for a feature model.

    Produces 5 types of test cases matching Java TestSuiteGenerator logic:
    dead features, false optional, full mandatory, false mandatory,
    and partial configuration.
    """

    def __init__(
        self,
        fm: Any,
        name: str,
        max_combinations: int = 1000,
        randomly_search: bool = True,
        max_items: int = 5,
    ) -> None:
        self._fm = fm
        self._name = name
        self._max_combinations = max_combinations
        self._randomly_search = randomly_search
        self._max_items = max_items

        self._testsuite: List[str] = []
        self._testsuite_set: set = set()  # O(1) membership check
        self._non_root_features = [f for f in fm.get_features() if f != fm.root]

        # Counts per type
        self._num_dead = 0
        self._num_false_optional = 0
        self._num_full_mandatory = 0
        self._num_false_mandatory = 0
        self._num_partial = 0

    def generate(self) -> None:
        """Generate all 5 types of test cases."""
        self._dead_features()
        self._num_dead = len(self._testsuite)

        old = len(self._testsuite)
        self._false_optional()
        self._num_false_optional = len(self._testsuite) - old

        old = len(self._testsuite)
        self._full_mandatory()
        self._num_full_mandatory = len(self._testsuite) - old

        old = len(self._testsuite)
        self._false_mandatory()
        self._num_false_mandatory = len(self._testsuite) - old

        old = len(self._testsuite)
        self._partial_config()
        self._num_partial = len(self._testsuite) - old

        total = (self._num_dead + self._num_false_optional
                 + self._num_full_mandatory + self._num_false_mandatory
                 + self._num_partial)
        print(f"\t[{self._name}] Total: {total} "
              f"(dead={self._num_dead}, false_opt={self._num_false_optional}, "
              f"full_mand={self._num_full_mandatory}, false_mand={self._num_false_mandatory}, "
              f"partial={self._num_partial})")

    def _add_tc(self, tc: str) -> None:
        """Add a test case if not already present (O(1) check)."""
        if tc not in self._testsuite_set:
            self._testsuite_set.add(tc)
            self._testsuite.append(tc)

    def _dead_features(self) -> None:
        """Dead feature test cases: f_name (true) for each non-root feature."""
        for f in self._non_root_features:
            self._add_tc(f.name)

    def _false_optional(self) -> None:
        """False optional: ~f_child & parent for alt/or children with mandatory parent.

        Matches Java: feature.isOptional() AND feature.isMandatory() AND
        getMandatoryParents(feature) returns mandatory ancestors.
        """
        for f in self._non_root_features:
            if f.is_mandatory():
                continue
            # Get mandatory ancestors (walk up tree)
            parents = self._get_mandatory_parents(f)
            if not parents:
                continue
            for parent in parents:
                self._add_tc(f"~{f.name} & {parent.name}")

    def _get_mandatory_parents(self, feature: Any) -> List[Any]:
        """Get ancestors that have a mandatory relationship to their parent.

        Walks up the tree from feature's parent, collecting mandatory ancestors.
        Stops at root (root has no parent relationship).
        """
        parents = []
        current = feature.parent
        while current and current != self._fm.root:
            if current.is_mandatory():
                parents.append(current)
            current = current.parent
        return parents

    def _full_mandatory(self) -> None:
        """Full mandatory: ~f for non-mandatory (optional/alt/or) features."""
        for f in self._non_root_features:
            if f.is_optional():
                self._add_tc(f"~{f.name}")

    def _false_mandatory(self) -> None:
        """False mandatory: ~f for mandatory features."""
        for f in self._non_root_features:
            if f.is_mandatory():
                self._add_tc(f"~{f.name}")

    def _partial_config(self) -> None:
        """Partial configuration: combinatorial true/false for feature subsets.

        Generates combinations of cardinality 2..min(num_features, max_items),
        then creates all 2^k true/false permutations per combination.
        """
        num_features = len(self._non_root_features)
        num_items = min(num_features, self._max_items)
        indices = list(range(num_features))

        for k in range(2, num_items + 1):
            print(f"\t[{self._name}] Partial config cardinality={k}")

            total_combos = _n_choose_k(num_features, k)
            print(f"\t\tCombinations: {total_combos}")

            if total_combos > self._max_combinations:
                if self._randomly_search:
                    # Sample combos directly (avoids iterating billions)
                    combos = _sample_combinations(indices, k, self._max_combinations)
                else:
                    # Take first max_combinations sequentially
                    combos = list(itertools.islice(
                        itertools.combinations(indices, k), self._max_combinations))
                for combo in combos:
                    self._add_partial_tcs(combo)
            else:
                for combo in itertools.combinations(indices, k):
                    self._add_partial_tcs(combo)

    def _add_partial_tcs(self, combo: tuple) -> None:
        """Generate all 2^k true/false permutations for a feature combination."""
        features = [self._non_root_features[i] for i in combo]

        for signs in itertools.product(["", "~"], repeat=len(features)):
            parts = [f"{s}{f.name}" for s, f in zip(signs, features)]
            self._add_tc(" & ".join(parts))

    def write_to_file(self, output_dir: str) -> None:
        """Write test suite to file in Java-compatible format."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        filepath = out_path / f"{self._name}.testsuite"

        total = (self._num_dead + self._num_false_optional
                 + self._num_full_mandatory + self._num_false_mandatory
                 + self._num_partial)

        with open(filepath, "w") as f:
            f.write(f"{total}\n")
            f.write(f"{self._num_dead}\n")
            f.write(f"{self._num_false_optional}\n")
            f.write(f"{self._num_full_mandatory}\n")
            f.write(f"{self._num_false_mandatory}\n")
            f.write(f"{self._num_partial}\n")
            for tc in self._testsuite:
                f.write(f"{tc}\n")

        print(f"\t[{self._name}] Written to {filepath}")


def _n_choose_k(n: int, k: int) -> int:
    """Compute binomial coefficient C(n, k)."""
    if k > n:
        return 0
    result = 1
    for i in range(min(k, n - k)):
        result = result * (n - i) // (i + 1)
    return result


def _sample_combinations(
    indices: List[int], k: int, count: int,
) -> List[tuple]:
    """Randomly sample `count` unique k-combinations from `indices`.

    Avoids enumerating all C(n,k) combinations by directly generating
    random combos via random.sample on the index list.
    """
    max_possible = _n_choose_k(len(indices), k)
    actual_count = min(count, max_possible)

    seen: set = set()
    results: List[tuple] = []
    while len(results) < actual_count:
        combo = tuple(sorted(random.sample(indices, k)))
        if combo not in seen:
            seen.add(combo)
            results.append(combo)
    return results


def generate_for_fm(
    fm_cfg: Dict[str, str],
    gen_config: Dict[str, Any],
    output_dir: str,
    seed: Optional[int] = None,
) -> str:
    """Top-level picklable function for multiprocessing.

    Loads a feature model and generates its test suite.
    """
    from flamapy.metamodels.fm_metamodel.transformations import UVLReader

    name = fm_cfg["name"]

    if seed is not None:
        random.seed(seed + hash(name) % (2**31))
    model_path = str(ROOT_PROJECT_FOLDER / fm_cfg["model"])

    print(f"[{name}] Loading feature model from {model_path}")
    fm = UVLReader(model_path).transform()

    gen = TestSuiteGenerator(
        fm=fm,
        name=name,
        max_combinations=gen_config.get("max_combinations", 1000),
        randomly_search=gen_config.get("randomly_search", True),
        max_items=gen_config.get("max_items", 5),
    )
    gen.generate()

    abs_output = str(ROOT_PROJECT_FOLDER / output_dir)
    gen.write_to_file(abs_output)
    return f"[{name}] Done"


def main() -> None:
    """Entry point: parse CLI config and run generation."""
    if len(sys.argv) < 2:
        print("Usage: python -m apps.testsuite_gen <config.toml>")
        sys.exit(1)

    config = load_config(sys.argv[1])
    gen_config = config["generation"]
    output_dir = config["output"]["output_dir"]
    max_workers = config.get("concurrency", {}).get("max_workers", 4)

    seed = gen_config.get("seed", None)

    fm_entries = config["fm"]
    print(f"Processing {len(fm_entries)} feature models with {max_workers} workers")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_for_fm, fm_cfg, gen_config, output_dir, seed): fm_cfg["name"]
            for fm_cfg in fm_entries
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
