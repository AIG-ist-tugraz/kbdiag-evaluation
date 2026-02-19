"""Redundancy detection operation for constraints using WipeOutR_FM algorithm.

This module provides an operation for detecting redundant constraints
in a feature model using the WipeOutR_FM algorithm.
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
from explanation.operations.algorithms.wipeoutr_fm import WipeOutR_FM
from explanation.operations.pysat_diagnosis import PySATDiagnosis


class PySATRedundancyConstraints(PySATDiagnosis):
    """Operation for detecting redundant constraints using WipeOutR_FM.

    This operation finds constraints that are redundant (logically implied
    by other constraints) in a feature model.

    A constraint c_i is redundant if KB \\ {c_i} |= c_i, meaning c_i
    logically follows from the remaining constraints.

    Attributes:
        redundant: List of redundant constraint IDs
        non_redundant: List of non-redundant constraint IDs
    """

    def __init__(self, profiler_instance: AbstractProfiler = None) -> None:
        """Initialize redundancy detection operation."""
        super().__init__(profiler_instance)
        self.redundant: List = []
        self.non_redundant: List = []

    # Not used - override execute() instead
    def _create_labeler(self, checker, model):
        pass

    # Not used - override execute() instead
    def prepare_hsdag(self, model):
        pass

    def execute(self, model: VariabilityModel) -> 'PySATRedundancyConstraints':
        """Execute redundancy detection using WipeOutR_FM algorithm.

        Args:
            model: Variability model (will be cast to DiagnosisModel)

        Returns:
            Self for method chaining
        """
        model = cast(DiagnosisModel, model)

        # Create checker using parent's method
        checker = self._create_checker(model)

        try:
            # Use WipeOutR_FM to find redundant constraints
            wipeoutr = WipeOutR_FM(checker, self.profiler)
            c = list(reversed(model.get_c()))
            self.redundant, self.non_redundant = wipeoutr.find_redundancies(
                c, model.get_negation_map())

            # Format result messages
            self._format_result_messages(model)
        finally:
            checker.cleanup()

        return self

    def _format_result_messages(self, model: DiagnosisModel) -> None:
        """Format result messages for display."""
        redundant_names = [model.description_provider.get_description(r)
                           for r in self.redundant]
        non_redundant_names = [model.description_provider.get_description(r)
                               for r in self.non_redundant]

        if self.redundant:
            redundant_msg = f"Redundant constraints: [{', '.join(redundant_names)}]"
        else:
            redundant_msg = "No redundant constraints found"

        if self.non_redundant:
            non_redundant_msg = f"Non-redundant constraints: [{', '.join(non_redundant_names)}]"
        else:
            non_redundant_msg = "No non-redundant constraints"

        self.result_messages = [redundant_msg, non_redundant_msg]

    def get_redundant(self) -> List:
        """Get list of redundant constraint IDs."""
        return self.redundant

    def get_non_redundant(self) -> List:
        """Get list of non-redundant constraint IDs."""
        return self.non_redundant

    def get_result(self) -> List[str]:
        """Get result messages."""
        return self.result_messages
