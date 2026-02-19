"""
QuickXPlainWithTestCases

Implementation of QuickXplain algorithm with test cases support.
Finds conflicts in constraint sets that violate test cases.

Based on Java implementation:
at.tugraz.ist.ase.kbdiag.debugging.algorithms.QuickXPlainWithTestCases

Reference:
- Ulrich Junker. "Quickxplain: Conflict detection for arbitrary constraint propagation algorithms."
  IJCAI'01 Workshop on Modelling and Solving problems with constraints. Vol. 4. 2001.

Algorithm:
-----------
QuickXPlain(B, C={c1,c2,…, cm}, TC):
  IF (is empty(C) or consistent(B∪C, TC)) return Φ
  ELSE return QX(Φ, C, B, one testcase from TC)

func QX(Δ, C={c1,c2, …, cq}, B, tc): conflictSet Δ
  IF (Δ != Φ AND inconsistent(B, tc)) return Φ;
  IF (C = {cα}) return(C);
  k=n/2;
  C1 <-- {c1, …, ck}; C2 <-- {ck+1, …, cq};
  CS1 <-- QX(C2, C1, B ∪ C2, tc);
  CS2 <-- QX(CS1, C2, B ∪ CS1, tc);
  return (CS2 ∪ CS1)

Author: Viet-Man Le (Python port)
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import logging
from typing import List, Tuple

from .checker import ConsistencyChecker
from .profiler import get_global_profiler, measure_time, count_calls, AbstractProfiler
from .utils import split


class QuickXPlainWithTestCases:
    """
    Implementation of QuickXPlain algorithm with test cases support.

    This variant of QuickXPlain finds conflicts in a constraint set that
    cause inconsistency with respect to one or more test cases (examples).
    """

    def __init__(self, checker: ConsistencyChecker, profiler_instance: AbstractProfiler = None) -> None:
        """
        Initialize QuickXPlainWithTestCases algorithm.

        Args:
            checker: ConsistencyChecker instance for checking consistency
            profiler_instance: Optional profiler instance. If None, uses global default profiler.
                              Pass NullProfiler() to disable profiling.
        """
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('quickxplain_with_testcases_runtime')
    @count_calls('quickxplain_with_testcases_calls')
    def find_conflict_set(self, set_c: List, set_b: List, set_tc: List, set_neg_tv: List = None) -> \
            Tuple[List, List]:
        """
        Find ONE conflict set from the constraint set C that is inconsistent with test cases.

        Algorithm:
            IF (is empty(C) or consistent(B∪C, TC)) return (None, Φ)
            ELSE
                select one failing test case tc from TC
                return (tc, QX(Φ, C, B, tc))

        Args:
            set_c: Consideration set (possibly faulty constraints)
            set_b: Background knowledge (correct constraints)
            set_tc: List of test cases (examples) to check consistency against
            set_neg_tv: List of negated negative test cases (optional)

        Returns:
            Tuple of (test_case, conflict_set):
                - test_case: The test case that caused the conflict, or None if no conflict
                - conflict_set: Set of constraints causing the conflict, or empty list

        Raises:
            ValueError: If set_tc is empty
        """
        if not set_tc:
            raise ValueError("set_tc cannot be empty")

        if set_neg_tv is None:
            set_neg_tv = []

        logging.debug('>>> QuickXPlainWithTestCases [C=%s, B=%s, TC=%s, neg_TV=%s]',
                      set_c, set_b, set_tc, set_neg_tv)

        # Check consistency with all test cases
        # If C is empty or consistent(B U C, TC) then return (None, Φ)
        if len(set_c) == 0:
            logging.debug('<<< No conflict found (C is empty)')
            return [], []

        # Build background with negated negative test cases
        # B_with_neg_tv = B ∪ negTν
        b_with_neg_tv = set_b + set_neg_tv

        # Step 1: T′π ← TESTC(negTν, Tπ)
        # Check if positive test cases are consistent with negated negative test cases
        if len(set_neg_tv) > 0:
            set_tcp = self.checker.is_consistent_test_cases(set_neg_tv, set_tc, True)
            if len(set_tcp) != 0:
                # Some positive test cases are inconsistent with negated negative test cases
                # This means these positive test cases require the original negative behaviors
                logging.debug('positive test cases inconsistent with neg_tv - return Φ')
                return [], []

        # Check consistency with test cases
        # Returns list of test cases that are INCONSISTENT (fail)
        set_tcp = self.checker.is_consistent_test_cases(b_with_neg_tv + set_c, set_tc, True)

        if len(set_tcp) == 0:
            logging.debug('<<< No conflict found (consistent with all test cases)')
            return [], []

        # Select one failing test case
        test_case = set_tcp[0]
        logging.debug('Selected failing test case: %s', test_case)

        # Find conflict set using QX with the selected test case
        conflict_set = self._qx([], set_c, b_with_neg_tv, test_case)

        logging.debug('<<< Found conflict [test_case=%s, conf=%s]', test_case, conflict_set)
        if not isinstance(test_case, list):
            test_case = [test_case]
        return test_case, conflict_set

    @count_calls('qx_with_testcases_calls')
    @measure_time('qx_with_testcases_runtime')
    def _qx(self, set_d: List, set_c: List, set_b: List, test_case: List) -> List:
        """
        Recursive QuickXPlain with test case.

        Algorithm:
            func QX(Δ, C={c1,c2, …, cq}, B, tc): conflictSet Δ
              IF (Δ != Φ AND inconsistent(B, tc)) return Φ;
              IF (C = {cα}) return(C);
              k=n/2;
              C1 <-- {c1, …, ck}; C2 <-- {ck+1, …, cq};
              CS1 <-- QX(C2, C1, B ∪ C2, tc);
              CS2 <-- QX(CS1, C2, B ∪ CS1, tc);
              return (CS2 ∪ CS1)

        Args:
            set_d: Delta (check to skip redundant consistency checks)
            set_c: Consideration set of constraints
            set_b: Background knowledge
            test_case: The specific test case to check against

        Returns:
            Conflict set or empty list
        """
        logging.debug('>>> QX [D=%s, C=%s, B=%s, tc=%s]', set_d, set_c, set_b, test_case)

        # IF (Δ != Φ AND inconsistent(B, tc)) return Φ
        if len(set_d) != 0:
            # Check if B is consistent with test case
            failing_tcs = self.checker.is_consistent_test_cases(set_b, [test_case], True)
            if failing_tcs:  # If B is inconsistent with test case
                logging.debug('<<< return Φ (B inconsistent with test case)')
                return []

        # IF (C = {cα}) return(C)
        if len(set_c) == 1:
            logging.debug('<<< return %s (singleton)', set_c)
            return set_c

        # Split C into C1 and C2
        # k = q/2; C1 = {c1..ck}; C2 = {ck+1..cq}
        set_c1, set_c2 = split(set_c)
        logging.debug('Split C into C1=%s, C2=%s', set_c1, set_c2)

        # CS1 <-- QX(C2, C1, B ∪ C2, tc)
        cs1 = self._qx(set_c2, set_c1, set_b + set_c2, test_case)

        # CS2 <-- QX(CS1, C2, B ∪ CS1, tc)
        cs2 = self._qx(cs1, set_c2, set_b + cs1, test_case)

        logging.debug('<<< return CS1=%s ∪ CS2=%s', cs1, cs2)

        # return (CS1 ∪ CS2)
        return cs1 + cs2
