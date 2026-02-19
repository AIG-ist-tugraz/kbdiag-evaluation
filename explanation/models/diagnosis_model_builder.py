"""Unified builder for creating configured DiagnosisModel instances.

This module provides a fluent builder interface for creating DiagnosisModel
instances with various configurations for different use cases.
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import Optional

from flamapy.metamodels.configuration_metamodel.models import Configuration
from flamapy.metamodels.fm_metamodel.models import FeatureModel

from .pysat_diagnosis_model import DiagnosisModel
from .task_preparation import TaskInput
from .testsuite import TestSuite


class DiagnosisModelBuilder:
    """Unified builder for creating DiagnosisModel instances.

    Supports all use cases through a fluent interface:

    | Use Case            | Builder Config                                                            | Task Type     | Negation       |
    |---------------------|---------------------------------------------------------------------------|---------------|----------------|
    | 1. Config diagnosis | .with_configuration(cfg)                                                  | DiagnosisTask | No             |
    | 2. Config + FM      | .with_configuration(cfg).with_cf_in_c()                                   | DiagnosisTask | No             |
    | 3. FM diagnosis     | (default)                                                                 | DiagnosisTask | No             |
    | 4. Error diagnosis  | .with_test_case(tc)                                                       | DiagnosisTask | No             |
    | 5. KBDiag           | .with_positive_testcases(tc).with_negative_testcases(tv)                  | TestCaseTask  | Test cases     |
    | 6. WipeOutR_T       | .with_testcases(ts)                                                       | TestCaseTask  | Test cases     |
    | 7. WipeOutR_FM      | .for_redundancy()                                                         | DiagnosisTask | FM constraints |
    | 8. CXPlain          | .with_requirement(req).with_configuration(cfg).with_sub_configuration(sc) | DiagnosisTask | Sub-config     |

    Examples:
        # Use Case 1: Configuration diagnosis
        model = (DiagnosisModelBuilder
            .from_fide("smartwatch.xml")
            .with_configuration(config)
            .use_incremental()
            .build())

        # Use Case 5: KBDiag with test cases
        model = (DiagnosisModelBuilder
            .from_uvl("feature_model.uvl")
            .with_positive_testcases(positive_ts)
            .with_negative_testcases(negative_ts)
            .use_incremental()
            .build())

        # Use Case 7: FM Redundancy Detection
        model = (DiagnosisModelBuilder
            .from_uvl("redundant_fm.uvl")
            .for_redundancy()
            .use_incremental()
            .build())
    """

    def __init__(self):
        """Initialize builder with default values."""
        # Source configuration
        self._source_type: Optional[str] = None
        self._source_path: Optional[str] = None
        self._feature_model: Optional[FeatureModel] = None

        # Mode flags
        self._for_redundancy: bool = False

        # Solver configuration
        self._use_incremental: bool = True

        # Diagnosis inputs
        self._configuration: Optional[Configuration] = None
        self._test_case: Optional[Configuration] = None
        self._with_cf_in_c: bool = False

        # Test case inputs
        self._positive_testcases: Optional[TestSuite] = None
        self._negative_testcases: Optional[TestSuite] = None

        # CXPlain inputs (for future)
        self._requirement: Optional[Configuration] = None
        self._sub_configuration: Optional[Configuration] = None

    # === Source Methods (class methods) ===

    @classmethod
    def from_fide(cls, path: str) -> 'DiagnosisModelBuilder':
        """Create builder from FeatureIDE XML file.

        Args:
            path: Path to FeatureIDE .fide/.xml file.

        Returns:
            DiagnosisModelBuilder instance.
        """
        builder = cls()
        builder._source_type = 'fide'
        builder._source_path = path
        return builder

    @classmethod
    def from_uvl(cls, path: str) -> 'DiagnosisModelBuilder':
        """Create builder from UVL file.

        Args:
            path: Path to UVL file.

        Returns:
            DiagnosisModelBuilder instance.
        """
        builder = cls()
        builder._source_type = 'uvl'
        builder._source_path = path
        return builder

    @classmethod
    def from_dimacs(cls, path: str) -> 'DiagnosisModelBuilder':
        """Create builder from DIMACS CNF file.

        Args:
            path: Path to DIMACS file.

        Returns:
            DiagnosisModelBuilder instance.
        """
        builder = cls()
        builder._source_type = 'dimacs'
        builder._source_path = path
        return builder

    @classmethod
    def from_feature_model(cls, fm: FeatureModel) -> 'DiagnosisModelBuilder':
        """Create builder from existing FeatureModel object.

        Args:
            fm: FeatureModel instance.

        Returns:
            DiagnosisModelBuilder instance.
        """
        builder = cls()
        builder._source_type = 'feature_model'
        builder._feature_model = fm
        return builder

    # === Mode Selection ===

    def for_redundancy(self, enabled: bool = True) -> 'DiagnosisModelBuilder':
        """Configure for FM constraint redundancy detection (WipeOutR_FM).

        When enabled, creates negated forms for all constraints during transformation.

        Args:
            enabled: Whether to enable redundancy detection mode.

        Returns:
            Self for method chaining.
        """
        self._for_redundancy = enabled
        return self

    # === Configuration Methods ===

    def with_configuration(self, config: Configuration) -> 'DiagnosisModelBuilder':
        """Set configuration for diagnosis.

        Args:
            config: Configuration to diagnose.

        Returns:
            Self for method chaining.
        """
        self._configuration = config
        return self

    def with_cf_in_c(self, enabled: bool = True) -> 'DiagnosisModelBuilder':
        """Enable CF-in-C mode (configuration + FM in C set).

        When enabled, both configuration and FM constraints are in set C,
        with only root in set B.

        Args:
            enabled: Whether to enable CF-in-C mode.

        Returns:
            Self for method chaining.
        """
        self._with_cf_in_c = enabled
        return self

    def with_test_case(self, test_case: Configuration) -> 'DiagnosisModelBuilder':
        """Set single test case for error diagnosis.

        Used for dead feature and false optional feature diagnosis.

        Args:
            test_case: Test case configuration.

        Returns:
            Self for method chaining.
        """
        self._test_case = test_case
        return self

    def with_positive_testcases(self, testcases: TestSuite) -> 'DiagnosisModelBuilder':
        """Set positive test cases for debugging/redundancy.

        Positive test cases are configurations that SHOULD be valid.

        Args:
            testcases: TestSuite of positive test cases.

        Returns:
            Self for method chaining.
        """
        self._positive_testcases = testcases
        return self

    def with_negative_testcases(self, testcases: TestSuite) -> 'DiagnosisModelBuilder':
        """Set negative test cases for KBDiag.

        Negative test cases are configurations that SHOULD be invalid.

        Args:
            testcases: TestSuite of negative test cases.

        Returns:
            Self for method chaining.
        """
        self._negative_testcases = testcases
        return self

    def with_testcases(self, testcases: TestSuite) -> 'DiagnosisModelBuilder':
        """Set examples for redundancy detection.

        Args:
            testcases: TestSuite of test cases.

        Returns:
            Self for method chaining.
        """
        self._positive_testcases = testcases
        self._for_redundancy = True
        return self

    def with_requirement(self, req: Configuration) -> 'DiagnosisModelBuilder':
        """Set requirement for CXPlain (future use).

        Args:
            req: Requirement configuration.

        Returns:
            Self for method chaining.
        """
        self._requirement = req
        return self

    def with_sub_configuration(self, sub_config: Configuration) -> 'DiagnosisModelBuilder':
        """Set sub-configuration for CXPlain (future use).

        Args:
            sub_config: Sub-configuration.

        Returns:
            Self for method chaining.
        """
        self._sub_configuration = sub_config
        return self

    # === Solver Mode ===

    def use_incremental(self, enabled: bool = True) -> 'DiagnosisModelBuilder':
        """Use incremental solver mode.

        Incremental mode keeps solver state between checks, improving efficiency.

        Args:
            enabled: Whether to use incremental mode.

        Returns:
            Self for method chaining.
        """
        self._use_incremental = enabled
        return self

    # === Build ===

    def build(self) -> DiagnosisModel:
        """Build and return fully configured DiagnosisModel.

        This method:
        1. Validates builder state
        2. Loads/transforms the feature model
        3. Sets solver mode configuration
        4. Assigns task inputs to model
        5. Calls prepare() to prepare the task

        Returns:
            Fully configured DiagnosisModel with task prepared.

        Raises:
            ValueError: If source is not specified or configuration is invalid.
        """
        # Validate
        self._validate()

        # Create model
        model = self._create_model()

        # Configure solver mode
        model._use_incremental = self._use_incremental

        # Create and assign TaskInput
        model.task_input = TaskInput(
            configuration=self._configuration,
            test_case=self._test_case,
            with_cf_in_c=self._with_cf_in_c,
            positive_test_cases=self._positive_testcases,
            negative_test_cases=self._negative_testcases,
            for_redundancy=self._for_redundancy,
            requirement=self._requirement,
            sub_configuration=self._sub_configuration
        )

        # Prepare the task
        model.prepare()

        return model

    def _validate(self) -> None:
        """Validate builder state before building.

        Validates:
        1. Source is specified
        2. Mutually exclusive inputs are not combined
        3. Required combinations are present

        Raises:
            ValueError: If validation fails
        """
        # 1. Source validation
        if self._source_path is None and self._feature_model is None:
            raise ValueError(
                "Source must be specified (use from_fide/from_uvl/from_dimacs/from_feature_model)")

        # 2. Mutually exclusive inputs
        if self._configuration and self._positive_testcases:
            raise ValueError(
                "Cannot combine configuration with test cases. "
                "Use configuration for diagnosis (use cases 1-2) OR test cases for KBDiag/WipeOutR_T (use cases 5-6)")

        if self._test_case and self._positive_testcases:
            raise ValueError(
                "Cannot combine test_case with positive_test_cases. "
                "Use test_case for error diagnosis (use case 4) OR positive_test_cases for KBDiag/WipeOutR_T (use cases 5-6)")

        if self._test_case and self._configuration:
            raise ValueError(
                "Cannot combine test_case with configuration. "
                "Use configuration for diagnosis (use cases 1-2) OR test_case for error diagnosis (use case 4)")

        # 3. Required combinations
        if self._with_cf_in_c and not self._configuration:
            raise ValueError(
                "with_cf_in_c requires configuration. "
                "Call .with_configuration(cfg) before .with_cf_in_c()")

        if self._negative_testcases and not self._positive_testcases:
            raise ValueError(
                "negative_test_cases requires positive_test_cases. "
                "Call .with_positive_testcases(tc) before .with_negative_testcases(tv)")

        # 4. CXPlain validation (future)
        if self._sub_configuration and not (self._requirement and self._configuration):
            raise ValueError(
                "sub_configuration requires both requirement and configuration. "
                "Call .with_requirement(req) and .with_configuration(cfg) before .with_sub_configuration(sc)")

    def _create_model(self) -> DiagnosisModel:
        """Create DiagnosisModel from source.

        Uses lazy imports to avoid circular dependencies.
        """
        # Determine if negation is needed
        needs_negation = self._for_redundancy

        if self._source_type == 'fide':
            from flamapy.metamodels.fm_metamodel.transformations import FeatureIDEReader
            from ..transformations.fm_to_diag_pysat import FmToDiagPysat

            fm = FeatureIDEReader(self._source_path).transform()
            return FmToDiagPysat(fm, create_negation=needs_negation).transform()

        elif self._source_type == 'uvl':
            from flamapy.metamodels.fm_metamodel.transformations import UVLReader
            from ..transformations.fm_to_diag_pysat import FmToDiagPysat

            fm = UVLReader(self._source_path).transform()
            return FmToDiagPysat(fm, create_negation=needs_negation).transform()

        elif self._source_type == 'dimacs':
            from ..transformations.dimacs_to_diag_pysat import DimacsToDiagPysat

            return DimacsToDiagPysat(self._source_path, create_negation=needs_negation).transform()

        elif self._source_type == 'feature_model':
            from ..transformations.fm_to_diag_pysat import FmToDiagPysat

            return FmToDiagPysat(self._feature_model, create_negation=needs_negation).transform()

        raise ValueError(f"Unknown source type: {self._source_type}")
