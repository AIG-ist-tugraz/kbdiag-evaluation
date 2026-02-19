"""
Consistency checkers for CNF formula satisfiability.

Implementations: IncrementalPySATChecker (persistent solver with assumptions),
NonIncrementalPySATChecker (fresh solver per check), SAT4JChecker (external Java solver).
All support pickling for multiprocessing and context manager protocol.

Use CheckerFactory.create_from_model() or CheckerFactory.create_sat4jchecker() to instantiate.
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import List, Protocol, runtime_checkable

from pysat.formula import CNF
from pysat.solvers import Solver

from .profiler import get_global_profiler, count_calls, AbstractProfiler


@runtime_checkable
class CheckerModel(Protocol):
    """Protocol for models compatible with CheckerFactory.

    Any class with these attributes/methods satisfies this protocol
    via structural subtyping (no inheritance needed).
    """
    use_incremental: bool

    def get_kb(self) -> List[List[int]]: ...

    def get_assumptions(self) -> List[int]: ...


class ConsistencyChecker(ABC):
    """Abstract base class for consistency checkers."""

    def __init__(self, profiler_instance: AbstractProfiler = None):
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    def _compute_delta(self, set_c: List) -> tuple:
        """Compute enabled/disabled assumption partition: delta = assumptions \\ set_c."""
        set_c_set = set(set_c)
        delta = [item for item in self.assumptions if item not in set_c_set]
        return set_c, delta

    @abstractmethod
    def is_consistent(self, set_c: List) -> bool:
        """Check if the given CNF formula is consistent."""
        pass

    @count_calls(key="is_consistent_test_cases_calls")
    def is_consistent_test_cases(self, set_c: List, set_tc: List, stop_at_first_violation: bool) -> List:
        """Check consistency against multiple test cases, returning inconsistent ones."""
        set_tcp = []
        # Accumulates test cases inconsistent with CNF formula
        for tc in set_tc:
            if not self.is_consistent(set_c + [tc]):
                set_tcp.append(tc)
            if stop_at_first_violation and len(set_tcp) > 0:
                break
        return set_tcp

    @abstractmethod
    def copy(self):
        """Create a copy for multiprocessing."""
        pass

    def cleanup(self) -> None:
        """Release resources. Override in subclasses with persistent state."""
        pass

    def __getstate__(self):
        state = self.__dict__.copy()
        state['profiler'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        if self.profiler is None:
            self.profiler = get_global_profiler()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class IncrementalPySATChecker(ConsistencyChecker):
    """Incremental checker using PySAT with persistent solver and assumptions."""

    def __init__(self, set_kb: List[List[int]], assumptions: List[int],
                 solver_name: str = 'glucose3', profiler_instance: AbstractProfiler = None) -> None:
        super().__init__(profiler_instance)
        self.solver_name = solver_name
        self.set_kb = set_kb
        self.assumptions = assumptions
        self.solver = Solver(solver_name, bootstrap_with=set_kb, use_timer=True)

    @count_calls(key="is_consistent_calls")
    def is_consistent(self, set_c: List) -> bool:
        enabled, disabled = self._compute_delta(set_c)
        final_assumptions = enabled + [-1 * item for item in disabled]

        result = self.solver.solve(assumptions=final_assumptions)

        self.profiler.record_time("solver_time", self.solver.time())
        if self.solver.time_accum() is not None:
            self.profiler.set_gauge("solver_time_accum", self.solver.time_accum())

        return result

    def copy(self):
        return IncrementalPySATChecker(
            self.set_kb, self.assumptions, self.solver_name, self.profiler
        )

    def cleanup(self) -> None:
        if hasattr(self, 'solver') and self.solver is not None:
            self.solver.delete()
            self.solver = None

    def __getstate__(self):
        state = super().__getstate__()
        if 'solver' in state:
            state['solver'] = None
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        if hasattr(self, 'solver_name') and hasattr(self, 'set_kb'):
            self.solver = Solver(self.solver_name, bootstrap_with=self.set_kb, use_timer=True)


class NonIncrementalPySATChecker(ConsistencyChecker):
    """Non-incremental checker using PySAT — fresh solver per check."""

    def __init__(self, set_kb: List[List[int]], assumptions: List[int],
                 solver_name: str = 'glucose3', profiler_instance: AbstractProfiler = None) -> None:
        super().__init__(profiler_instance)
        self.solver_name = solver_name
        self.set_kb = set_kb
        self.assumptions = assumptions

    @count_calls(key="is_consistent_calls")
    def is_consistent(self, set_c: List) -> bool:
        enabled, disabled = self._compute_delta(set_c)
        final_assumptions = enabled + [-1 * item for item in disabled]

        solver = Solver(self.solver_name, bootstrap_with=self.set_kb, use_timer=True)
        result = solver.solve(assumptions=final_assumptions)

        self.profiler.record_time("solver_time", solver.time())
        solver.delete()

        return result

    def copy(self):
        return NonIncrementalPySATChecker(
            list(self.set_kb), list(self.assumptions),
            self.solver_name, self.profiler
        )


class SAT4JChecker(ConsistencyChecker):
    """Checker using external SAT4J solver via subprocess. Assumptions encoded as unit clauses."""

    def __init__(self, set_kb: List[List[int]] = None,
                 assumptions: List[int] = None,
                 jar_path: str = "solver_apps/org.sat4j.core.jar",
                 profiler_instance: AbstractProfiler = None, timeout: int = 300) -> None:
        super().__init__(profiler_instance)
        self.jar_path = jar_path
        self.timeout = timeout
        self.set_kb = set_kb or []
        self.assumptions = assumptions or []

        if not os.path.exists(jar_path):
            raise FileNotFoundError(
                f"SAT4J jar not found at: {jar_path}\n"
                f"Please ensure the solver is installed."
            )

    @count_calls(key="is_consistent_calls")
    def is_consistent(self, set_c: List) -> bool:
        enabled, disabled = self._compute_delta(set_c)
        assumption_clauses = [[a] for a in enabled] + [[-a] for a in disabled]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=True) as f:
            cnf = CNF()
            cnf.extend(self.set_kb + assumption_clauses)
            cnf.to_file(f.name)

            with self.profiler.timer("solver_time"):
                try:
                    result = subprocess.run(
                        ["java", "-jar", self.jar_path, f.name],
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        check=False
                    )
                    output = result.stdout
                except subprocess.TimeoutExpired:
                    output = "TIMEOUT"
                except Exception as e:
                    raise RuntimeError(f"Failed to run SAT4J: {e}")

        return "SATISFIABLE" in output and "UNSATISFIABLE" not in output

    def copy(self):
        return SAT4JChecker(
            list(self.set_kb), list(self.assumptions),
            self.jar_path, self.profiler, self.timeout
        )


class CheckerFactory:
    """Factory for creating consistency checker instances."""

    @staticmethod
    def create_sat4jchecker(profiler_instance: AbstractProfiler = None,
                            sat4j_jar_path: str = "solver_apps/org.sat4j.core.jar",
                            set_kb: List[List[int]] = None,
                            assumptions: List[int] = None) -> ConsistencyChecker:
        return SAT4JChecker(set_kb=set_kb, assumptions=assumptions,
                            jar_path=sat4j_jar_path,
                            profiler_instance=profiler_instance)

    @staticmethod
    def create_from_model(model: CheckerModel,
                          solver_name: str = 'glucose3',
                          profiler_instance: AbstractProfiler = None) -> ConsistencyChecker:
        if model.use_incremental:
            return IncrementalPySATChecker(
                model.get_kb(), model.get_assumptions(),
                solver_name, profiler_instance
            )
        else:
            return NonIncrementalPySATChecker(
                model.get_kb(), model.get_assumptions(),
                solver_name, profiler_instance
            )
