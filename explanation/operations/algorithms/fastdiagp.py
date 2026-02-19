#!/usr/bin/env python
"""
FastDiagP
https://github.com/AIG-ist-tugraz/FastDiagP

Deep first search approach
The assumption of consistency of B U C is taken into account first

Limit the number of generated consistency checks to maxGCC
maxNumGenCC = min(numCores - 1, 7)
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import logging
import multiprocessing as mp
from typing import List

from . import utils
from .checker import ConsistencyChecker
from .profiler import get_global_profiler, measure_time, count_calls, AbstractProfiler
from .utils import split, diff


class FastDiagP:
    """
    Implementation of FastDiagP algorithm.
    Le, V. M., Silva, C. V., Felfernig, A., Benavides, D., Galindo, J., & Tran, T. N. T. (2023, June).
    FastDiagP: An algorithm for parallelized direct diagnosis.
    In Proceedings of the AAAI Conference on Artificial Intelligence (Vol. 37, No. 5, pp. 6442-6449).
    """

    def __init__(self, checker: ConsistencyChecker, profiler_instance: AbstractProfiler = None) -> None:
        """
        Initialize FastDiagP algorithm.

        :param checker: ConsistencyChecker instance
        :param profiler_instance: Optional profiler for metrics tracking
        """
        self.checker = checker
        self.profiler = profiler_instance if profiler_instance is not None else get_global_profiler()
        self.maxNumGenCC = 0

        self.lookup_table = {}
        self.counter_readyCC = 0
        self.pool = None
        self.currentNumGenCC = 0
        self.genhash = ""

    @measure_time('fastdiagp_runtime')
    @count_calls('fastdiagp_calls')
    def find_diagnosis(self, set_c: List, set_b: List) -> List:
        """
        Activate FastDiag algorithm if there exists at least one constraint,
        which induces an inconsistency in B. Otherwise, it returns an empty set.

        // Func FastDiag(C, B) : Δ
        // if isEmpty(C) or consistent(B U C) return Φ
        // else return C \\ FD(Φ, C, B)
        :param set_c: a consideration set of constraints
        :param set_b: a background knowledge
        :return: a diagnosis or an empty set
        """
        logging.debug('fastDiag [C=%s, B=%s]', set_c, set_b)
        # print(f'fastDiag [C={C}, B={B}]')

        # if isEmpty(C) or consistent(B U C) return Φ
        if len(set_c) == 0 or self.checker.is_consistent(set_b + set_c):
            logging.debug('return Φ')
            # print('return Φ')
            return []

        # return C \ FD(C, B, Φ)
        numCores = mp.cpu_count()

        self.maxNumGenCC = min(numCores - 1, 4)
        self.profiler.set_gauge('maxNumGenCC', self.maxNumGenCC)
        self.pool = mp.Pool(self.maxNumGenCC)

        mss = self._fd([], set_c, set_b)
        diag = diff(set_c, mss)

        self.profiler.set_gauge('lookup_table_size', len(self.lookup_table))

        self.pool.close()
        self.pool.terminate()

        logging.debug('return %s', diag)
        # print(f'return {diag}')
        return diag

    @count_calls('fd_calls')
    @measure_time('fd_runtime')
    def _fd(self, delta: List, set_c: List, set_b: List) -> List:
        """
        The implementation of MSS-based FastDiag algorithm.
        The algorithm determines a maximal satisfiable subset MSS (Γ) of C U B.

        // Func FD(Δ, C = {c1..cn}, B) : MSS
        // if Δ != Φ and consistent(B U C) return C;
        // if singleton(C) return Φ;
        // k = n/2;
        // C1 = {c1..ck}; C2 = {ck+1..cn};
        // Δ1 = FD(C2, C1, B);
        // Δ2 = FD(C1 - Δ1, C2, B U Δ1);
        // return Δ1 ∪ Δ2;
        :param delta: check to skip redundant consistency checks
        :param set_c: a consideration set of constraints
        :param set_b: a background knowledge
        :return: a maximal satisfiable subset MSS of C U B
        """
        logging.debug('>>> FD [Δ=%s, C=%s, B=%s]', delta, set_c, set_b)

        # if Δ != Φ and consistent(B U C) return C;
        # if len(delta) != 0 and self.checker.is_consistent(set_b + set_c):
        if len(delta) != 0 and self.is_consistent_with_lookahead(set_c, set_b, delta):
            logging.debug('<<< return %s', set_c)
            return set_c

        # if singleton(C) return Φ;
        if len(set_c) == 1:
            logging.debug('<<< return Φ')
            return []

        # C1 = {c1..ck}; C2 = {ck+1..cn};
        set_c1, set_c2 = split(set_c)

        # Δ1 = FD(C2, C1, B);
        delta1 = self._fd(set_c2, set_c1, set_b)
        # Δ2 = FD(C1 - Δ1, C2, B U Δ1);
        c1_without_delta1 = diff(set_c1, delta1)
        delta2 = self._fd(c1_without_delta1, set_c2, set_b + delta1)

        logging.debug('<<< return [Δ1=%s ∪ Δ2=%s]', delta1, delta2)

        # return Δ1 + Δ2
        return delta1 + delta2

    @count_calls(key='is_consistent_with_lookahead_calls')
    @measure_time(key='is_consistent_with_lookahead_runtime')
    def is_consistent_with_lookahead(self, set_c: List, set_b: List, delta: List) -> bool:
        BwithC = set_b + set_c

        self.genhash = hashcode = utils.get_hashcode(BwithC)
        if not (hashcode in self.lookup_table):
            self.currentNumGenCC = 1  # reset the number of generated consistency checks

            self.profiler.increment('lookahead_calls')
            with self.profiler.timer('lookahead_runtime'):
                self.lookahead(set_c, set_b, [delta], 0)
        else:
            self.profiler.increment('lookup_CC_ok')

        return self.lookup_CC(hashcode)

    def lookup_CC(self, hashcode: str) -> (bool, float):
        result = self.lookup_table.get(hashcode)

        if result.ready:
            self.profiler.increment('ready')
            # self.counter_readyCC = self.counter_readyCC + 1
        else:
            self.profiler.increment('not_ready')
        return result.get()

    def lookahead(self, set_c: List, set_b: List, delta: List, level: int) -> None:
        # logging.debug(">>> lookahead [l={}, Δ={}, C={}, B={}]".format(level, Δ, C, B))

        if self.currentNumGenCC < self.maxNumGenCC:
            BwithC = set_b + set_c

            if self.genhash == "":
                hashcode = utils.get_hashcode(BwithC)
            else:
                hashcode = self.genhash
                self.genhash = ""

            if not (hashcode in self.lookup_table):  # and hashcode not in need_to_checks:
                self.currentNumGenCC = self.currentNumGenCC + 1

                # create a new consistency checker for each lookahead
                checker = self.checker.copy()

                future = self.pool.apply_async(checker.is_consistent, args=(BwithC,))
                self.lookup_table.update({hashcode: future})

                # logging.debug(">>> addCC [l={}, C={}]".format(level, hashcode))

            # B U C assumed consistent
            if len(delta) > 1 and len(delta[0]) == 1:
                hashcode = utils.get_hashcode(BwithC + delta[0])
                if hashcode in self.lookup_table:  # case 2.1
                    delta2l, delta2r = utils.split(delta[1])
                    delta_prime = delta.copy()
                    del delta_prime[0]
                    del delta_prime[0]
                    delta_prime.insert(0, delta2r)

                    # LookAhead(delta2l, B U C, delta2r U (Δ \ {delta1, Δ2})), l + 1)
                    self.lookahead(delta2l, BwithC, delta_prime, level + 1)
            elif len(delta) >= 1 and len(delta[0]) == 1:  # case 2.2
                delta1 = delta[0]
                delta_prime = delta.copy()
                del delta_prime[0]

                # LookAhead(delta1, B U C, Δ \ {delta1}, l + 1)
                self.lookahead(delta1, BwithC, delta_prime, level + 1)
            elif len(delta) >= 1 and len(delta[0]) > 1:  # case 2.3
                delta1l, delta1r = utils.split(delta[0])
                delta_prime = delta.copy()
                del delta_prime[0]
                delta_prime.insert(0, delta1r)

                # LookAhead(delta1l, B U C, delta1r U (Δ \ {delta1})), l + 1)
                self.lookahead(delta1l, BwithC, delta_prime, level + 1)

            # B U C assumed inconsistent
            if len(set_c) > 1:  # case 1.1
                Cl, Cr = utils.split(set_c)
                delta_prime = delta.copy()
                delta_prime.insert(0, Cr)

                # LookAhead(Cl, B, Cr U Δ, l + 1)
                self.lookahead(Cl, set_b, delta_prime, level + 1)
            elif len(set_c) == 1 and len(delta) >= 1 and len(delta[0]) == 1:  # case 1.2
                delta1 = delta[0]
                delta_prime = delta.copy()
                del delta_prime[0]

                # LookAhead(delta1, B, Δ \ {delta1}, l + 1)
                self.lookahead(delta1, set_b, delta_prime, level + 1)
            elif len(set_c) == 1 and len(delta) >= 1 and len(delta[0]) > 1:  # case 1.3
                delta1l, delta1r = utils.split(delta[0])
                delta_prime = delta.copy()
                del delta_prime[0]
                delta_prime.insert(0, delta1r)

                # LookAhead(delta1l, B, delta1r U (Δ \ {delta1})), l + 1)
                self.lookahead(delta1l, set_b, delta_prime, level + 1)
