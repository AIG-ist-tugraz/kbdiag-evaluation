"""Redundancy detection operation for test cases using WipeOutR_T algorithm.

This module provides an operation for detecting redundant test cases
in a test suite using the WipeOutR_T algorithm.
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List, cast

from flamapy.core.models import VariabilityModel

from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.profiler import AbstractProfiler
from explanation.operations.algorithms.wipeoutr_t import WipeOutR_T
from explanation.operations.pysat_testcase import PySATTestCase


class PySATRedundancyTestCases(PySATTestCase):
    """Operation for detecting redundant test cases using WipeOutR_T.

    This operation finds test cases that are redundant (logically covered
    by other test cases) in a test suite.

    A test case t_gamma is redundant w.r.t. t_alpha if t_alpha |= t_gamma,
    meaning t_gamma logically follows from t_alpha.

    Attributes:
        redundant: List of redundant test case IDs
        non_redundant: List of non-redundant test case IDs
    """

    def __init__(self, profiler_instance: AbstractProfiler = None) -> None:
        """Initialize redundancy detection operation."""
        super().__init__(profiler_instance)
        self.redundant: str = '[]'
        self.non_redundant: str = '[]'

    # Not used - override execute() instead
    def _create_labeler(self, checker, model):
        pass

    # Not used - override execute() instead
    def prepare_hsdag(self, model):
        pass

    def execute(self, model: VariabilityModel) -> 'PySATRedundancyTestCases':
        """Execute redundancy detection using WipeOutR_T algorithm.

        Args:
            model: Variability model (will be cast to DiagnosisModel)

        Returns:
            Self for method chaining
        """
        model = cast(DiagnosisModel, model)

        # Create checker using parent's method
        checker = self._create_checker(model)

        try:
            # Use WipeOutR_T instead of HSDAG
            wipeoutr = WipeOutR_T(checker, self.profiler)
            redundant, non_redundant = wipeoutr.find_redundant_testcases(
                model.get_tc(), model.get_negation_map())

            # Format result messages
            self._format_result_messages(model, redundant, non_redundant)
        finally:
            checker.cleanup()

        return self

    def _format_result_messages(self, model: DiagnosisModel, redundant: List, non_redundant: List) -> None:
        """Format result messages for display."""
        redundant_names = [model.description_provider.get_description(r)
                           for r in redundant]
        non_redundant_names = [model.description_provider.get_description(r)
                               for r in non_redundant]

        self.redundant = f"[{', '.join(redundant_names)}]" if redundant_names else '[]'
        self.non_redundant = f"[{', '.join(non_redundant_names)}]" if non_redundant_names else '[]'

        redundant_msg = f"Redundant test cases: {self.redundant}" if redundant else "No redundant test cases found"
        non_redundant_msg = f"Non-redundant test cases: {self.non_redundant}" if non_redundant else "No non-redundant test cases"

        self.result_messages = [redundant_msg, non_redundant_msg]

    def get_redundant(self) -> str:
        """Get list of redundant test case IDs."""
        return self.redundant

    def get_non_redundant(self) -> str:
        """Get list of non-redundant test case IDs."""
        return self.non_redundant
