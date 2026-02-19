"""Test case operation using KBDiag algorithm with test cases.

This module provides diagnosis operations using the KBDiag algorithm
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
from explanation.operations.algorithms.hsdag.labeler.kbdiag_labeler import KBDiagLabeler, KBDiagParameters
from explanation.operations.algorithms.profiler import AbstractProfiler
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation


class PySATTestCase(PySATAbstractExplanation):
    """Operation for test case diagnosis using KBDiag algorithm.

    This operation computes diagnoses using the KBDiag algorithm which
    works with positive and negative test cases.

    Attributes:
        m: Parameter for KBDiag algorithm (default: 1)
    """

    def __init__(self, profiler_instance: AbstractProfiler = None) -> None:
        """Initialize test case operation with default values."""
        super().__init__(profiler_instance)
        self._m: int = 1

    @property
    def m(self) -> int:
        """Get the parameter m."""
        return self._m

    @m.setter
    def m(self, value: int) -> None:
        """Set m parameter for KBDiag algorithm.

        Args:
            value: parameter value (must be positive or default: 1)

        Raises:
            ValueError: If value is not positive
        """
        if value < 1:
            raise ValueError(f"the parameter m must be positive and greater than 1, got {value}")
        self._m = value

    def _create_labeler(self, checker: ConsistencyChecker, model: DiagnosisModel) -> KBDiagLabeler:
        """Create KBDiag labeler for HSDAG.

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

        parameters = KBDiagParameters(set_c, set_b, set_tc, set_neg_tv)
        return KBDiagLabeler(checker, self.m, parameters)

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

        return checker, self._create_hsdag(labeler)

    def set_result_messages(self, cs_mess: str, diag_mess: str) -> None:
        """Set result messages with diagnoses first.

        Args:
            cs_mess: Formatted conflicts message
            diag_mess: Formatted diagnoses message
        """
        self.result_messages = [diag_mess, cs_mess]
