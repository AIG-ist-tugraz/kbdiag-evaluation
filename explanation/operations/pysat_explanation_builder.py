"""Builder for configuring diagnosis/test case operations.

This module provides a fluent builder interface for creating and configuring
diagnosis/test case operations.

The builder hierarchy:
- PySATExplanationBuilder: Abstract base class with common methods
- PySATDiagnosisBuilder: For diagnosis/conflict operations (FastDiag, QuickXPlain)
- PySATTestcaseBuilder: For test case operations with test cases (KBDiag)
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from abc import ABC
from typing import Optional, TypeVar

from explanation.operations.algorithms.profiler import AbstractProfiler
from explanation.operations.algorithms.hsdag.hsdag import SearchStrategy
from explanation.operations.pysat_abstract_explanation import PySATAbstractExplanation
from explanation.operations.pysat_conflict import PySATConflict
from explanation.operations.pysat_conflict_sat4j import PySATConflictSAT4J
from explanation.operations.pysat_diagnosis import PySATDiagnosis
from explanation.operations.pysat_diagnosis_sat4j import PySATDiagnosisSAT4J
from explanation.operations.pysat_redundancy_constraints import PySATRedundancyConstraints
from explanation.operations.pysat_redundancy_testcases import PySATRedundancyTestCases
from explanation.operations.pysat_testcase import PySATTestCase
from explanation.operations.pysat_testcase_quickxplain import PySATTestCaseQuickXPlain

# Type variable for method chaining with correct return types
T = TypeVar('T', bound='PySATExplanationBuilder')


class PySATExplanationBuilder(ABC):
    """Abstract base builder for configuring diagnosis/debugging operations.

    This builder provides a fluent interface for setting up diagnosis/debugging operations
    with various configuration options. It supports method chaining for convenient
    configuration.

    Subclasses:
        - PySATDiagnosisBuilder: For diagnosis/conflict operations
        - PySATTestcaseBuilder: For debugging operations with test cases

    Example:
        >>> builder = PySATDiagnosisBuilder.for_diagnosis()
        >>> operation = (builder
        ...     .with_max_diagnoses(10)
        ...     .with_max_depth(5)
        ...     .build())
        >>> result = operation.execute(diagnosis_model)
    """

    def __init__(self, operation: PySATAbstractExplanation):
        """Initialize builder with a specific operation type.

        Args:
            operation: The operation instance to configure
        """
        self._operation = operation

    def with_max_conflicts(self: T, max_conflicts: Optional[int]) -> T:
        """Set maximum number of conflicts to find.

        Args:
            max_conflicts: Maximum number of conflicts (None for no limit,
                         must be positive if specified)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If max_conflicts is not positive
        """
        self._operation.max_conflicts = max_conflicts
        return self

    def with_max_diagnoses(self: T, max_diagnoses: Optional[int]) -> T:
        """Set maximum number of diagnoses to find.

        Args:
            max_diagnoses: Maximum number of diagnoses (None for no limit,
                          must be positive if specified)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If max_diagnoses is not positive
        """
        self._operation.max_diagnoses = max_diagnoses
        return self

    def with_max_depth(self: T, max_depth: Optional[int]) -> T:
        """Set maximum depth of HSDAG tree.

        Args:
            max_depth: Maximum depth (None for no limit,
                      must be positive if specified)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If max_depth is not positive
        """
        self._operation.max_depth = max_depth
        return self

    def with_depth_first_search(self: T, enabled: bool = True) -> T:
        """Enable or disable depth-first search in HSDAG.

        Args:
            enabled: Whether to use depth-first search (default: True)

        Returns:
            Self for method chaining
        """
        self._operation.depth_first_search = enabled
        return self

    def with_search_strategy(self: T, strategy: SearchStrategy) -> T:
        """Set the search strategy for HSDAG.

        Args:
            strategy: SearchStrategy.BREADTH_FIRST (default) or SearchStrategy.BEST_FIRST

        Returns:
            Self for method chaining
        """
        self._operation.search_strategy = strategy
        return self

    def with_solver(self: T, solver_name: str) -> T:
        """Set the SAT solver to use.

        Args:
            solver_name: Name of the SAT solver (e.g., 'glucose3', 'sat4j')

        Returns:
            Self for method chaining
        """
        self._operation.solver_name = solver_name
        return self

    def build(self) -> PySATAbstractExplanation:
        """Build and return the configured operation.

        Returns:
            Configured PySATAbstractExplanation instance ready for execution
        """
        return self._operation


class PySATDiagnosisBuilder(PySATExplanationBuilder):
    """Builder for diagnosis and conflict detection operations.

    This builder is used for operations that work with:
    - Feature model diagnosis/conflict (finding faulty constraints)
    - Configuration diagnosis/conflict (finding conflicting selections)
    - Test case diagnosis (finding constraints violating test cases)

    Uses FastDiag (for diagnoses) or QuickXPlain (for conflicts) algorithms.

    Example:
        >>> operation = (PySATDiagnosisBuilder.for_diagnosis()
        ...     .with_max_diagnoses(5)
        ...     .build())
        >>> result = operation.execute(model)

    Example with SAT4J solver:
        >>> operation = (PySATDiagnosisBuilder.for_diagnosis_sat4j()
        ...     .build())
    """

    @classmethod
    def for_conflict(cls) -> 'PySATDiagnosisBuilder':
        """Create a builder for conflict detection operations.

        Returns:
            PySATDiagnosisBuilder configured for PySATConflict
        """
        return cls(PySATConflict())

    @classmethod
    def for_diagnosis(cls) -> 'PySATDiagnosisBuilder':
        """Create a builder for diagnosis operations.

        Returns:
            PySATDiagnosisBuilder configured for PySATDiagnosis
        """
        return cls(PySATDiagnosis())

    @classmethod
    def for_diagnosis_sat4j(cls) -> 'PySATDiagnosisBuilder':
        """Create a builder for diagnosis operations using SAT4J solver.

        Returns:
            PySATDiagnosisBuilder configured for PySATDiagnosis with SAT4J
        """
        return cls(PySATDiagnosisSAT4J())

    @classmethod
    def for_conflict_sat4j(cls) -> 'PySATDiagnosisBuilder':
        """Create a builder for conflict detection operations using SAT4J solver.

        Returns:
            PySATDiagnosisBuilder configured for PySATConflict with SAT4J
        """
        return cls(PySATConflictSAT4J())


class PySATTestcaseBuilder(PySATExplanationBuilder):
    """Builder for debugging operations with test cases.

    This builder is used for operations that work with positive and negative
    test cases using the KBDiag algorithm.

    Example:
        >>> operation = (PySATTestCaseBuilder.for_debugging()
        ...     .with_max_diagnoses(5)
        ...     .with_m(2)
        ...     .build())
        >>> result = operation.execute(model)
    """

    def __init__(self, operation: PySATTestCase):
        """Initialize builder with a PySATTestCase operation.

        Args:
            operation: The PySATTestCase instance to configure
        """
        super().__init__(operation)
        self._testcase_operation = operation

    @classmethod
    def for_debugging(cls) -> 'PySATTestCaseBuilder':
        """Create a builder for test case operations with test cases.

        Uses KBDiag algorithm to find diagnoses based on positive/negative test cases.

        Returns:
            PySATTestCaseBuilder configured for PySATTestCase

        Example:
            >>> operation = (PySATTestCaseBuilder.for_debugging()
            ...     .with_max_diagnoses(1)
            ...     .build())
        """
        return cls(PySATTestCase())

    def with_m(self, m: int) -> 'PySATTestCaseBuilder':
        """Set m parameter for KBDiag algorithm.

        The m parameter controls how many test cases are considered at once
        during the diagnosis process.

        Args:
            m: Parameter value (default: 1)

        Returns:
            Self for method chaining
        """
        self._testcase_operation.m = m
        return self


class PySATTestcaseQuickXplainBuilder(PySATExplanationBuilder):
    """Builder for debugging operations with test cases.

    This builder is used for operations that work with positive and negative
    test cases using the HSDAG+QuickXPlainWithTestCase algorithm.

    Example:
        >>> operation = (PySATTestcaseQuickXplainBuilder.for_debugging()
        ...     .with_max_diagnoses(5)
        ...     .build())
        >>> result = operation.execute(model)
    """

    def __init__(self, operation: PySATTestCaseQuickXPlain):
        """Initialize builder with a PySATTestCaseQuickXPlain operation.

        Args:
            operation: The PySATTestCaseQuickXPlain instance to configure
        """
        super().__init__(operation)
        self._testcase_operation = operation

    @classmethod
    def for_debugging(cls) -> 'PySATTestcaseQuickXplainBuilder':
        """Create a builder for test case operations with test cases.

        Uses HSDAG+QuickXPlainWithTestCase algorithm to find diagnoses based on positive/negative test cases.

        Returns:
            PySATTestcaseQuickXplainBuilder configured for PySATTestCaseQuickXPlain

        Example:
            >>> operation = (PySATTestcaseQuickXplainBuilder.for_debugging()
            ...     .with_max_diagnoses(1)
            ...     .build())
        """
        return cls(PySATTestCaseQuickXPlain())


class PySATRedundancyTestCasesBuilder:
    """Builder for test case redundancy detection operations.

    This builder is used for detecting redundant test cases in a test suite
    using the WipeOutR_T algorithm.

    A test case t_gamma is redundant w.r.t. t_alpha if t_alpha |= t_gamma,
    meaning t_gamma logically follows from t_alpha.

    Example:
        >>> operation = (PySATRedundancyTestCasesBuilder.for_redundancy_test_cases()
        ...     .build())
        >>> result = operation.execute(model)
        >>> redundant = result.get_redundant()
    """

    def __init__(self, operation: PySATRedundancyTestCases):
        """Initialize builder with a PySATRedundancyTestCases operation.

        Args:
            operation: The PySATRedundancyTestCases instance to configure
        """
        self._operation = operation

    @classmethod
    def for_redundancy_test_cases(cls, profiler: AbstractProfiler = None) -> 'PySATRedundancyTestCasesBuilder':
        """Create a builder for test case redundancy detection operations.

        Uses WipeOutR_T algorithm to find redundant test cases.

        Args:
            profiler: Optional profiler for performance tracking

        Returns:
            PySATRedundancyTestCasesBuilder configured for PySATRedundancyTestCases

        Example:
            >>> operation = (PySATRedundancyTestCasesBuilder.for_redundancy_test_cases()
            ...     .build())
        """
        return cls(PySATRedundancyTestCases(profiler))

    def with_solver(self, solver_name: str) -> 'PySATRedundancyTestCasesBuilder':
        """Set the SAT solver to use.

        Args:
            solver_name: Name of the SAT solver (e.g., 'glucose3')

        Returns:
            Self for method chaining
        """
        self._operation.solver_name = solver_name
        return self

    def build(self) -> PySATRedundancyTestCases:
        """Build and return the configured operation.

        Returns:
            Configured PySATRedundancyTestCases instance ready for execution
        """
        return self._operation


class PySATRedundancyConstraintsBuilder:
    """Builder for constraint redundancy detection operations.

    This builder is used for detecting redundant constraints in a feature model
    using the WipeOutR_FM algorithm.

    A constraint c_i is redundant if KB \\ {c_i} |= c_i, meaning c_i
    logically follows from the remaining constraints.

    Example:
        >>> operation = (PySATRedundancyConstraintsBuilder.for_redundancy_constraints()
        ...     .with_solver('glucose3')
        ...     .build())
        >>> result = operation.execute(model)
        >>> redundant = result.get_redundant()
    """

    def __init__(self, operation: PySATRedundancyConstraints):
        """Initialize builder with a PySATRedundancyConstraints operation.

        Args:
            operation: The PySATRedundancyConstraints instance to configure
        """
        self._operation = operation

    @classmethod
    def for_redundancy_constraints(cls, profiler: AbstractProfiler = None) -> 'PySATRedundancyConstraintsBuilder':
        """Create a builder for constraint redundancy detection operations.

        Uses WipeOutR_FM algorithm to find redundant constraints.

        Args:
            profiler: Optional profiler for performance tracking

        Returns:
            PySATRedundancyConstraintsBuilder configured for PySATRedundancyConstraints

        Example:
            >>> operation = (PySATRedundancyConstraintsBuilder.for_redundancy_constraints()
            ...     .build())
        """
        return cls(PySATRedundancyConstraints(profiler))

    def with_solver(self, solver_name: str) -> 'PySATRedundancyConstraintsBuilder':
        """Set the SAT solver to use.

        Args:
            solver_name: Name of the SAT solver (e.g., 'glucose3')

        Returns:
            Self for method chaining
        """
        self._operation.solver_name = solver_name
        return self

    def build(self) -> PySATRedundancyConstraints:
        """Build and return the configured operation.

        Returns:
            Configured PySATRedundancyConstraints instance ready for execution
        """
        return self._operation
