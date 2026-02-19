"""WipeOutR_T algorithm for test suite redundancy detection.

This module implements the WipeOutR_T algorithm from the WipeOutR paper
for detecting redundant test cases in feature model test suites.

A test case t_γ is redundant w.r.t. t_α if t_α |= t_γ (t_γ logically follows from t_α).
This means t_γ is already covered by t_α and can be removed from the test suite.
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import logging
from typing import List, Dict, Tuple

from .checker import ConsistencyChecker
from .profiler import get_global_profiler, measure_time, count_calls, AbstractProfiler
from .utils import diff


class WipeOutR_T:
    """
    Implementation of WipeOutR_T algorithm for test suite redundancy detection.

    A test case t_γ is redundant if there exists another test case t_α such that
    t_α |= t_γ, meaning t_γ logically follows from t_α.

    Algorithm WipeOutR_T(T = {t1..tk})
    1: T_π ← T; T_Δ ← ∅
    2: while T_π ≠ ∅ do
    3:     t_α ← first(T_π)
    4:     for all t_γ ∈ T − T_Δ − {t_α} do
    5:         if inconsistent(t_α ∧ ¬t_γ) then
    6:             T_Δ ← T_Δ ∪ {t_γ}; T_π ← T_π − {t_γ}
    7:         end if
    8:     end for
    9:     T_π ← T_π − {t_α}
    10: end while
    11: return(T − T_Δ)
    """

    def __init__(self, checker: ConsistencyChecker,
                 profiler_instance: AbstractProfiler = None) -> None:
        """Initialize WipeOutR_T algorithm.

        Args:
            checker: ConsistencyChecker instance for SAT solving
            profiler_instance: Optional profiler for performance tracking
        """
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('wipeoutr_t_runtime')
    @count_calls('wipeoutr_t_calls')
    def find_redundant_testcases(self, set_t: List,
                                 negation_map: Dict) -> Tuple[List, List]:
        """
        Find redundant test cases in a test suite.

        A test case t_γ is redundant if inconsistent(t_α ∧ ¬t_γ) for some t_α in T.
        This means t_α |= t_γ, i.e., t_γ is already covered by t_α.

        Args:
            set_t: List of test case assumption IDs (original forms)
            negation_map: Mapping from original to negated assumption IDs

        Returns:
            Tuple of (redundant test cases, non-redundant test cases)
        """
        logging.debug('WipeOutR_T [T=%s, negation_map=%s]', set_t, negation_map)

        if len(set_t) <= 1:
            # No redundancy possible with 0 or 1 test cases
            return [], set_t.copy()

        # T_π ← T (working set of test cases to check)
        t_pi = set_t.copy()
        # T_Δ ← ∅ (set of redundant test cases)
        t_delta = []

        while len(t_pi) > 0:
            # t_α ← first(T_π)
            t_alpha = t_pi.pop()

            # for all t_γ ∈ T − T_Δ − {t_α} do
            candidates = diff(diff(set_t, t_delta), [t_alpha])

            for t_gamma in candidates:
                # Check if t_gamma is redundant w.r.t. t_alpha
                # inconsistent(t_α ∧ ¬t_γ) means t_α |= t_γ

                if t_gamma not in negation_map:
                    logging.warning('No negated form for test case %s, skipping', t_gamma)
                    continue

                neg_t_gamma = negation_map[t_gamma]

                # Check inconsistent(t_α ∧ ¬t_γ)
                # Activate both t_alpha and neg_t_gamma
                test_set = [t_alpha, neg_t_gamma]
                is_consistent = self.checker.is_consistent(test_set)

                logging.debug('Checking t_%s vs t_%s: consistent(t_%s ∧ ¬t_%s) = %s',
                              t_alpha, t_gamma, t_alpha, t_gamma, is_consistent)

                if not is_consistent:
                    # t_gamma is redundant (t_alpha |= t_gamma)
                    t_delta.append(t_gamma)
                    if t_gamma in t_pi:
                        t_pi.remove(t_gamma)
                    logging.debug('Test case %s is redundant (covered by %s)', t_gamma, t_alpha)

        # return(T − T_Δ)
        non_redundant = diff(set_t, t_delta)

        logging.debug('Redundant test cases: %s', t_delta)
        logging.debug('Non-redundant test cases: %s', non_redundant)

        return t_delta, non_redundant

    @measure_time('wipeoutr_t_nonredundant_runtime')
    def find_non_redundant_testcases(self, set_t: List,
                                     negation_map: Dict) -> List:
        """
        Find non-redundant test cases in a test suite.

        This is a convenience method that returns only the non-redundant test cases.

        Args:
            set_t: List of test case assumption IDs (original forms)
            negation_map: Mapping from original to negated assumption IDs

        Returns:
            List of non-redundant test case IDs
        """
        _, non_redundant = self.find_redundant_testcases(set_t, negation_map)
        return non_redundant
