"""WipeOutR_FM algorithm for redundancy detection in feature models.

This module implements the WipeOutR_FM algorithm from the WipeOutR paper
for detecting redundant constraints in feature models.
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


class WipeOutR_FM:
    """
    Implementation of WipeOutR_FM algorithm for feature model redundancy detection.

    A constraint cα is redundant if CF - {cα} |= cα, meaning cα logically
    follows from the remaining constraints.

    Algorithm WipeOutR_FM(CF = {c1..cn})
    1: CF_Δ ← CF
    2: for all cα ∈ CF do
    3:     if inconsistent(CF_Δ - {cα} ∪ {¬cα}) then
    4:         CF_Δ ← CF_Δ - cα
    5:     end if
    6: end for
    7: return(CF_Δ)
    """

    def __init__(self, checker: ConsistencyChecker,
                 profiler_instance: AbstractProfiler = None) -> None:
        """Initialize WipeOutR_FM algorithm.

        Args:
            checker: ConsistencyChecker instance for SAT solving
            profiler_instance: Optional profiler for performance tracking
        """
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()

    @measure_time('wipeoutr_fm_runtime')
    @count_calls('wipeoutr_fm_calls')
    def find_redundancies(self, set_c: List,
                          negation_map: Dict[int, int]) -> Tuple[List, List]:
        """
        Find redundant constraints in CF.

        A constraint cα is identified as redundant if:
        - CF_Δ - {cα} ∪ {¬cα} is inconsistent
        - This means CF_Δ - {cα} |= cα (cα is entailed by remaining constraints)

        Args:
            set_c: List of constraint assumption IDs (original forms)
            negation_map: Mapping from original to negated assumption IDs

        Returns:
            List of redundant constraint IDs that can be removed
        """
        logging.debug('WipeOutR_FM [CF=%s, negation_map=%s]', set_c, negation_map)

        # CF_Δ ← CF (working copy that will be reduced)
        c_delta = set_c.copy()
        redundant = []

        for c_alpha in set_c:
            # Skip if cα already removed from CF_Δ
            if c_alpha not in c_delta:
                continue

            # Build CF_Δ - {cα}
            cf_without_alpha = diff(c_delta, [c_alpha])

            # Get ¬cα
            if c_alpha not in negation_map:
                logging.warning('No negated form for constraint %s, skipping', c_alpha)
                continue

            neg_alpha = negation_map[c_alpha]

            # Check inconsistent(CF_Δ - {cα} ∪ {¬cα})
            test_set = cf_without_alpha + [neg_alpha]
            is_consistent = self.checker.is_consistent(test_set)

            logging.debug('Checking c_%s: consistent(CF_Δ - {c_%s} ∪ {¬c_%s}) = %s',
                          c_alpha, c_alpha, c_alpha, is_consistent)

            if not is_consistent:
                # cα is redundant: CF_Δ - {cα} |= cα
                c_delta.remove(c_alpha)
                redundant.append(c_alpha)
                logging.debug('Constraint %s is redundant', c_alpha)

        logging.debug('Redundant constraints: %s', redundant)
        logging.debug('Non-redundant CF_Δ: %s', c_delta)

        return redundant, c_delta

    @measure_time('wipeoutr_fm_nonredundant_runtime')
    def find_non_redundant(self, set_cf: List,
                           negation_map: Dict[int, int]) -> List:
        """
        Find non-redundant constraints in CF.

        This is the complement of find_redundancies - returns CF_Δ directly.

        Args:
            set_cf: List of constraint assumption IDs (original forms)
            negation_map: Mapping from original to negated assumption IDs

        Returns:
            List of non-redundant constraint IDs (CF_Δ)
        """
        _, non_redundant = self.find_redundancies(set_cf, negation_map)
        return non_redundant
