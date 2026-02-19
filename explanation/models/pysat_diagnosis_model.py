"""Diagnosis model."""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List, Dict, Optional

from flamapy.metamodels.pysat_metamodel.models import PySATModel

from .task_preparation import (
    TaskPreparationFactory,
    TaskInput,
    DiagnosisTask,
    TestCaseTask,
    DescriptionProvider,
    DiagnosisFormatter,
)


class DiagnosisModel(PySATModel):
    """PySATModel extension for diagnosis tasks.

    This class uses composition to delegate task preparation to strategies:
    - DiagnosisTaskPreparation: For diagnosis/conflict operations
    - TestCaseTaskPreparation: For operations with test cases (KBDiag, WipeOutR_T)

    Important:
        This model should be created via transformation (FmToDiagPysat or
        DimacsToDiagPysat), which populates constraint_map, negated_constraint_map,
        and next_available_id. Direct instantiation requires manually setting
        these fields correctly.

    Supported task types (via prepare() method):
    1. Configuration diagnosis: prepare(configuration=cfg)
       C = configuration, B = FM + root
    2. Config + FM diagnosis: prepare(configuration=cfg) with is_CF_in_C=True
       C = configuration + FM, B = root only
    3. FM diagnosis: prepare()
       C = FM constraints, B = root only
    4. Error diagnosis: prepare(test_case=tc)
       C = FM constraints, B = root + test_case
    5. KBDiag debugging: prepare(positive_test_cases=tc, negative_test_cases=tv)
       C = FM (excl. root), B = root, TC = positive, TV = negative
    6. WipeOutR_T: prepare(positive_test_cases=ts)
       Test case redundancy detection
    7. WipeOutR_FM: prepare(include_negated_forms=True)
       Constraint redundancy detection (CF = FM constraints, no root)
    """

    @staticmethod
    def get_extension() -> str:
        return 'pysat_diagnosis'

    def __init__(self) -> None:
        super().__init__()
        # map clauses to relationships/constraint
        self.constraint_map: Dict[str, List[List]] = {}
        # map negated clauses to relationships/constraint (for WipeOutR_FM)
        self.negated_constraint_map: Dict[str, List[List]] = {}
        # Next available variable ID after Tseitin variables (set by transformation).
        # Used as starting ID for assumption literals to avoid conflicts.
        self.next_available_id: int = 1000

        # Solver configuration
        self._use_incremental: bool = True  # default to use incremental solver

        # Task input (set by builder or directly before calling prepare())
        self._task_input: Optional[TaskInput] = None

        # Populated after prepare() is called
        self._task: Optional[DiagnosisTask] = None
        self._description_provider: Optional[DescriptionProvider] = None

    @property
    def use_incremental(self) -> bool:
        """Whether to use incremental solver."""
        return self._use_incremental

    def add_clause_to_map(self, description: str, clauses: List[List]) -> None:
        """Add clauses with description to constraint map."""
        self.constraint_map[description] = clauses

    def add_negated_clause_to_map(self, description: str, clauses: List[List]) -> None:
        """Add negated clauses with description to negated constraint map."""
        self.negated_constraint_map[description] = clauses

    @property
    def task_input(self):
        return self._task_input

    @task_input.setter
    def task_input(self, value):
        self._task_input = value

    @property
    def task(self) -> DiagnosisTask:
        """Get the preparation result.
        Call prepare() first."""
        if self._task is None:
            raise RuntimeError("Call prepare() first")
        return self._task

    @property
    def description_provider(self) -> DescriptionProvider:
        """Get the description provider.
        Call prepare() first."""
        if self._description_provider is None:
            raise RuntimeError("Call prepare() first")
        return self._description_provider

    # Convenience getters (delegate to result)
    def get_c(self) -> List:
        """Get the set of potentially faulty constraints."""
        return self.task.set_c

    def get_b(self) -> List:
        """Get the background knowledge."""
        return self.task.set_b

    def get_cf(self) -> List:
        """Get all constraints (C ∪ B) for redundancy detection.

        Returns:
            List of all constraint IDs (set_c + set_b).
        """
        return self.task.get_cf()

    def get_kb(self) -> List[List]:
        """Get the full knowledge base with assumptions."""
        return self.task.set_kb

    def get_negation_map(self) -> dict:
        """Get the mapping from original to negated assumption IDs.

        Returns:
            Dict mapping original assumption ID to negated assumption ID,
            or empty dict if no negated forms.
        """
        return self.task.negation_map

    def get_assumptions(self) -> List:
        """Get the list of assumption literals."""
        return self.task.assumptions

    def get_tc(self) -> List:
        """Get the positive test cases (debugging task only).

        Returns:
            List of positive test case assumptions, or empty list if not debugging task.
        """
        if isinstance(self.task, TestCaseTask):
            return self.task.set_tc
        return []

    def get_tv(self) -> List:
        """Get the negative test cases (debugging task only).

        Returns:
            List of negative test case assumptions, or empty list if not debugging task.
        """
        if isinstance(self.task, TestCaseTask):
            return self.task.set_tv
        return []

    def get_neg_tv(self) -> List:
        """Get the negated negative test cases (debugging task only).

        Used by KBDiag for B = B ∪ neg_Tν.

        Returns:
            List of negated negative test case assumptions, or empty list if not debugging task.
        """
        if isinstance(self.task, TestCaseTask):
            return self.task.set_neg_tv
        return []

    def get_neg_tc(self) -> List:
        """Get the negated positive test cases (debugging task only).

        Used for WipeOutR algorithm.

        Returns:
            List of negated positive test case assumptions, or empty list if not debugging task.
        """
        if isinstance(self.task, TestCaseTask):
            return self.task.set_neg_tc
        return []

    def format_diagnoses(self, diagnoses: List[List]) -> str:
        """Format diagnoses for display.

        Args:
            diagnoses: List of diagnoses to format.

        Returns:
            Human-readable string representation.
        """
        return DiagnosisFormatter.format(diagnoses, self.description_provider)

    def prepare(self, task_input: Optional[TaskInput] = None) -> DiagnosisTask:
        """Unified task preparation method using TaskInput.

        Args:
            task_input: Optional TaskInput to use. If provided, updates the model's
                task input before preparing. If None, uses existing task input.

        Uses task_input (set via builder or directly) which contains:
        - configuration: Configuration to diagnose
        - test_case: Test case for error diagnosis
        - positive_test_cases: TestSuite of positive test cases
        - negative_test_cases: TestSuite of negative test cases
        - for_redundancy: Whether to include negated forms
        - with_cf_in_c: Whether to include CF in C set
        - requirement: requirement for diagnosis
        - sub_configuration: Sub-configuration for diagnosis

        Supported Task Types (Use Case Mapping):
        =========================================
        1. Configuration diagnosis: configuration is set
           C = configuration, B = FM + root

        2. Config + FM diagnosis: configuration + is_cf_in_c=True
           C = configuration + FM, B = root only

        3. FM diagnosis: no inputs set
           C = FM constraints, B = root only

        4. Error diagnosis: test_case is set
           C = FM constraints, B = root + test_case

        5. KBDiag debugging: positive_test_cases (+ optional negative_test_cases)
           C = FM (excl. root), B = root, TC = positive, TV = negative

        6. WipeOutR_T: positive_test_cases set
           Test case redundancy detection

        7. WipeOutR_FM: for_redundancy=True
           Constraint redundancy detection

        Returns:
            DiagnosisTask or TestCaseTask based on TaskInput.

        Note:
            After calling prepare() with new input, any existing checker instances
            must be recreated as they hold references to the previous KB/assumptions.
        """
        if task_input is not None:
            self._task_input = task_input
        # Use empty TaskInput if not set
        _task_input = self._task_input or TaskInput()

        if _task_input.is_testcase_task():
            # Test case task (KBDiag, WipeOutR_T)
            return self._prepare_testcase_task(_task_input)
        else:
            # Diagnosis task (FastDiag, QuickXPlain, WipeOutR_FM)
            return self._prepare_diagnosis_task(_task_input)

    def _prepare_diagnosis_task(self, task_input: TaskInput) -> DiagnosisTask:
        """Internal method to prepare diagnosis task.

        Args:
            task_input: TaskInput containing configuration, test_case, etc.

        Returns:
            DiagnosisTask.
        """
        strategy = TaskPreparationFactory.create_diagnosis(self.use_incremental)
        output = strategy.prepare(self)

        self._task = output.task
        self._description_provider = output.description_provider
        return self._task

    def _prepare_testcase_task(self, task_input: TaskInput) -> TestCaseTask:
        """Internal method to prepare test case task.

        Args:
            task_input: TaskInput containing positive_test_cases, negative_test_cases.

        Returns:
            TestCaseTask with set_c, set_b, set_tc, set_tv populated.
        """
        strategy = TaskPreparationFactory.create_testcase(self.use_incremental)
        output = strategy.prepare(self)

        self._task = output.task
        self._description_provider = output.description_provider
        return self._task
