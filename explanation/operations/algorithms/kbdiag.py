#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import logging
from typing import List, Tuple

from .checker import ConsistencyChecker
from .profiler import get_global_profiler, measure_time, count_calls, AbstractProfiler
from .utils import split, diff


class KBDiag:
    """
    Implementation of KBDiag algorithm.
    The algorithm determines a maximal satisfiable subset MSS (Γ) of C U B U -TV U TC.
    """

    def __init__(self, checker: ConsistencyChecker, m: int = 1, profiler_instance: AbstractProfiler = None) -> None:
        self.checker = checker
        self.m = m
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('kbdiag_runtime')
    @count_calls('kbdiag_calls')
    def find_diagnosis(self, set_c: List, set_b: List, set_tc: List, set_neg_tv: List = None) -> Tuple[List, List]:
        """
        Activate KBDiag algorithm if there exists at least one positive test case,
        which induces an inconsistency in C U B. Otherwise, it returns an empty set.

        // Func KBDiag(C, B, Tν, Tπ, λ) : ∆
        // negTν ← ∧{¬tν | tν ∈ Tν}
        // T′π ← TESTC(negTν, Tπ)
        // if T′π = ∅ then
        //     T′π ← TESTC(C ∪ B ∪ negTν, Tπ)
        //     if (T′π  != ∅) then
        //          return(C − MSSDIRECT(∅, C, B ∪ negTν, T′π, λ))
        //     else
        //          return Φ
        // else
        //     return Φ
        :param set_c: a consideration set of constraints
        :param set_b: a background knowledge
        :param set_tc: a set of positive test cases
        :param set_neg_tv: a set of negated negative test cases (for B ∪ negTν)
        :return: a tuple of (inconsistent test cases, diagnosis)
        """
        if set_neg_tv is None:
            set_neg_tv = []

        logging.debug('kbDiag [C=%s, B=%s, TC=%s, neg_TV=%s]',
                      set_c, set_b, set_tc, set_neg_tv)
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

        # Step 2: T′π ← TESTC(C ∪ B ∪ negTν, Tπ)
        # Find positive test cases that are inconsistent with the full KB
        set_tcp = self.checker.is_consistent_test_cases(set_c + b_with_neg_tv, set_tc, False)
        if len(set_c) == 0 or len(set_tcp) == 0:
            logging.debug('all test cases satisfied - return Φ')
            return [], []

        # Step 3: return C \ MSSDIRECT(∅, C, B ∪ negTν, T′π, λ)
        mss = self._mssDirect([], set_c, b_with_neg_tv, set_tcp)
        diag = diff(set_c, mss)

        logging.debug('return diagnosis=%s', diag)
        return set_tcp, diag

    @count_calls('mssDirect_calls')
    @measure_time('mssDirect_runtime')
    def _mssDirect(self, delta: List, set_c: List, set_b: List, set_tc: List) -> List:
        """
        The implementation of KBDiag algorithm.
        The algorithm determines a maximal satisfiable subset MSS (Γ) of C U B U TC.
        Tv is the set of negative test cases - ignored from this evaluation

        // Func MSSDirect(δ, C, B, Tv, Tπ) : Γ
        // T'π <- Tπ
        // if Δ != Φ then
        //    T'π <- TestC(B U C, Tπ)
        //    if T'π = Φ then return C;
        // if |C| <= m return Φ;
        // k = n/2;
        // C1 = {c1..ck}; C2 = {ck+1..cn};
        // Γ2 = MSSDirect(δ=C1, C1, B, T'π);
        // Γ1 = MSSDirect(δ=C1-Γ2, C2, B U Γ2, T'π);
        // return Γ1 ∪ Γ2;
        :param delta: check to skip redundant consistency checks
        :param set_c: a consideration set of constraints
        :param set_b: a background knowledge
        :param set_tc: a set of test cases
        :return: a maximal satisfiable subset MSS of C U B U TC
        """
        logging.debug('>>> MSSDirect [δ=%s, C=%s, B=%s, TC=%s]', delta, set_c, set_b, set_tc)

        # T'π <- Tπ
        set_tcp = set_tc.copy()

        # if δ != Φ and TestC(B U C, Tπ) return C;
        if len(delta) != 0:
            set_tcp = self.checker.is_consistent_test_cases(
                set_b + set_c, set_tc, False
            )

            if len(set_tcp) == 0:
                logging.debug('<<< return %s', set_c)
                return set_c

        # if singleton(C) return Φ;
        if len(set_c) <= self.m:
            logging.debug('<<< return Φ')
            return []

        # C1 = {c1..ck}; C2 = {ck+1..cn};
        set_c1, set_c2 = split(set_c)

        # Γ1 = MSSDirect(δ=C1, C1, B, T'π);
        delta1 = self._mssDirect(set_c1, set_c1, set_b, set_tcp)
        # Γ2 = MSSDirect(δ=C1-Γ1, C2, B U Γ1, T'π);
        c1_without_delta1 = diff(set_c1, delta1)
        delta2 = self._mssDirect(c1_without_delta1, set_c2, set_b + delta1, set_tcp)

        logging.debug('<<< return [Γ1=%s ∪ Γ2=%s]', delta1, delta2)

        # return Γ1 ∪ Γ2
        return delta1 + delta2