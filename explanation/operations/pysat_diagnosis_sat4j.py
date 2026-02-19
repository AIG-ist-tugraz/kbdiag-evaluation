#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import Tuple

from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.checker import ConsistencyChecker, CheckerFactory
from explanation.operations.algorithms.hsdag.hsdag import HSDAG
from explanation.operations.algorithms.hsdag.labeler.fastdiag_labeler import FastDiagLabeler, FastDiagParameters
from explanation.operations.algorithms.profiler import AbstractProfiler
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation


class PySATDiagnosisSAT4J(PySATAbstractExplanation):
    """Operation that computes diagnoses and conflicts using HSDAG and FastDiag.

    This operation identifies diagnoses (minimal sets of constraints whose removal
    makes the system consistent) and conflicts (sets of constraints that are inconsistent)
    using the combination of HSDAG tree search and FastDiag diagnosis labeling.

    Attributes:
        max_conflicts: Maximum number of conflicts to find (None for no limit)
        max_diagnoses: Maximum number of diagnoses to find (None for no limit)
        max_depth: Maximum depth of HSDAG tree (None for no limit)
        depth_first_search: Whether to use depth-first search
        solver_name: SAT solver to use (default: 'glucose3')

    Example:
        >>> operation = PySATDiagnosis()
        >>> operation.max_diagnoses = 5
        >>> result = operation.execute(diagnosis_model)
        >>> messages = result.get_result()
    """

    def __init__(self, profiler_instance: AbstractProfiler = None) -> None:
        """Initialize PySATDiagnosis operation with default values."""
        super().__init__(profiler_instance)

    def _create_labeler(self, checker: ConsistencyChecker, model: DiagnosisModel) -> FastDiagLabeler:
        """Create FastDiag labeler for diagnosis computation.

        Args:
            checker: Consistency checker instance
            model: Diagnosis model

        Returns:
            Configured FastDiagLabeler instance
        """
        set_c = model.get_c()
        set_b = model.get_b()

        parameters = FastDiagParameters(set_c, set_b)
        return FastDiagLabeler(checker, parameters)

    def _create_checker(self, model: DiagnosisModel) -> ConsistencyChecker:
        """Create consistency checker for diagnosis computation."""
        return CheckerFactory.create_sat4jchecker(
            self.profiler, set_kb=model.get_kb(), assumptions=model.get_assumptions())

    def prepare_hsdag(self, model: DiagnosisModel) -> Tuple[ConsistencyChecker, HSDAG]:
        """Prepare HSDAG with FastDiag labeler for diagnosis computation.

        This method uses the helper methods to:
        1. Create a consistency checker
        2. Create a FastDiag labeler
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
        """Set result messages with diagnoses first, then conflicts.

        Args:
            cs_mess: Formatted conflicts message
            diag_mess: Formatted diagnoses message
        """
        self.result_messages.extend([diag_mess, cs_mess])
