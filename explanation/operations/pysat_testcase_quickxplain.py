"""Test case operation using HSDAG + QuickXPlainWithTestCases algorithm with test cases.

This module provides diagnosis operations using the HSDAG + QuickXPlainWithTestCases algorithm
which works with positive and negative test cases.
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import Tuple

from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.checker import ConsistencyChecker
from explanation.operations.algorithms.hsdag.hsdag import HSDAG
from explanation.operations.algorithms.hsdag.labeler.quickxplain_with_testcases_labeler import \
    QuickXPlainWithTestCasesParameters, QuickXPlainWithTestCasesLabeler
from explanation.operations.algorithms.profiler import AbstractProfiler
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation


class PySATTestCaseQuickXPlain(PySATAbstractExplanation):
    """Operation for test case diagnosis using HSDAG + QuickXPlainWithTestCases algorithm.

    This operation computes conflicts using the QuickXPlainWithTestCases algorithm which
    works with positive and negative test cases.
    """

    def __init__(self, profiler_instance: AbstractProfiler = None) -> None:
        """Initialize test case operation with default values."""
        super().__init__(profiler_instance)

    def _create_labeler(self, checker: ConsistencyChecker, model: DiagnosisModel) -> QuickXPlainWithTestCasesLabeler:
        """Create QuickXPlainWithTestCasesLabeler labeler for HSDAG.

        Args:
            checker: Consistency checker instance
            model: Diagnosis model

        Returns:
            KBDiagLabeler instance
        """
        set_c = model.get_c()
        set_b = model.get_b()
        set_tc = model.get_tc()
        set_neg_tv = model.get_neg_tv()

        parameters = QuickXPlainWithTestCasesParameters(set_c, set_b, set_tc, set_neg_tv)
        return QuickXPlainWithTestCasesLabeler(checker, parameters)

    def prepare_hsdag(self, model: DiagnosisModel) -> Tuple[ConsistencyChecker, HSDAG]:
        """Prepare HSDAG with KBDiag labeler for test case computation.

        This method uses the helper methods to:
        1. Create a consistency checker
        2. Create a KBDiag labeler
        3. Configure HSDAG with operation parameters

        Args:
            model: Diagnosis model to use

        Returns:
            Tuple of (consistency_checker, configured_hsdag)
        """
        checker = self._create_checker(model)
        labeler = self._create_labeler(checker, model)
        set_c = model.get_c()

        return checker, self._create_hsdag(labeler, constraint_ordering=set_c)

    def set_result_messages(self, cs_mess: str, diag_mess: str) -> None:
        """Set result messages with diagnoses first.

        Args:
            cs_mess: Formatted conflicts message
            diag_mess: Formatted diagnoses message
        """
        self.result_messages = [diag_mess, cs_mess]
