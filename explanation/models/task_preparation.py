"""Task preparation strategies and utilities for diagnosis.

This module provides strategy pattern implementations for preparing diagnosis tasks.

Strategy hierarchy:
- DiagnosisTaskPreparationStrategy: For diagnosis/conflict operations
  - DiagnosisTaskPreparation (single impl, mode via constructor)
- TestCaseTaskPreparationStrategy: For operations with test cases (KBDiag, WipeOutR_T)
  - TestCaseTaskPreparation (single impl, mode via constructor)

Task hierarchy:
- DiagnosisTask (base, with assumptions)
  - TestCaseTask (adds test case fields)
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, TYPE_CHECKING

from flamapy.metamodels.configuration_metamodel.models import Configuration
from flamapy.metamodels.fm_metamodel.models.feature_model import Feature

from explanation.models.testsuite import TestSuite
from explanation.operations.algorithms.utils import get_hashcode

if TYPE_CHECKING:
    from .pysat_diagnosis_model import DiagnosisModel

# Each constraint produces a pair of assumptions (original + negated),
# so we stride by 2 to select only original assumptions.
_ASSUMPTION_PAIR_STRIDE = 2
_ASSUMPTION_SINGLE_STRIDE = 1


# === INPUT DATA CLASS ===

@dataclass
class TaskInput:
    """Input parameters for task preparation.

    Single source of truth for user inputs passed through:
    DiagnosisModelBuilder → DiagnosisModel → TaskPreparation

    Use Cases Mapping:
    ==================
    1. Configuration diagnosis: configuration is set
    2. Config + FM diagnosis: configuration + with_cf_in_c=True
    3. FM diagnosis: no inputs (defaults)
    4. Error diagnosis: test_case is set
    5. KBDiag: positive_test_cases (+ optional negative_test_cases)
    6. WipeOutR_T: positive_test_cases + for_redundancy=True
    7. WipeOutR_FM: for_redundancy=True
    8. CXPlain (future): requirement + configuration + sub_configuration
    """
    # Diagnosis inputs
    configuration: Optional[Configuration] = None
    test_case: Optional[Configuration] = None
    with_cf_in_c: bool = False

    # Test case inputs
    positive_test_cases: Optional[TestSuite] = None
    negative_test_cases: Optional[TestSuite] = None

    # Redundancy detection
    for_redundancy: bool = False

    # CXPlain inputs (future)
    requirement: Optional[Configuration] = None
    sub_configuration: Optional[Configuration] = None

    def is_testcase_task(self) -> bool:
        """Check if this input is for a test case task."""
        return self.positive_test_cases is not None


# === UTILITIES ===

def convert_keys_to_features(configuration: Configuration) -> Configuration:
    """Convert string keys to Feature objects."""
    new_elements = {Feature(key) if isinstance(key, str) else key: value
                    for key, value in configuration.elements.items()}
    return Configuration(new_elements)


# === RESULT DATA CLASSES (Core data only) ===

@dataclass
class DiagnosisTask:
    """Base class for a diagnosis task.

    Contains core data needed by algorithms, including assumptions
    for both incremental and non-incremental modes.
    """
    # set of constraints which could be faulty
    set_c: List = field(default_factory=list)
    # background knowledge (i.e., the knowledge that is known to be true)
    set_b: List = field(default_factory=list)
    # set of all CNF with added assumptions
    set_kb: List = field(default_factory=list)
    # mapping: original assumption ID -> negated assumption ID
    # Used by WipeOutR_FM (constraints) and WipeOutR_T (test cases)
    negation_map: Dict = field(default_factory=dict)
    # list of assumptions for solver
    assumptions: List = field(default_factory=list)

    def get_cf(self) -> List:
        """Get all constraints (C ∪ B)."""
        return self.set_b + self.set_c


@dataclass
class TestCaseTask(DiagnosisTask):
    """Base class for tasks with test cases.

    Contains common fields for both incremental and non-incremental modes.
    Used by KBDiag algorithm with positive/negative test cases,
    and WipeOutR_T for test case redundancy detection.
    """
    # positive test cases (original form)
    set_tc: List = field(default_factory=list)
    # negative test cases (original form)
    set_tv: List = field(default_factory=list)
    # negated negative test cases (for KBDiag: B = B ∪ neg_Tν)
    set_neg_tv: List = field(default_factory=list)
    # negated positive test cases (for WipeOutR)
    set_neg_tc: List = field(default_factory=list)


# === DESCRIPTION PROVIDERS (For formatting only) ===

class DescriptionProvider:
    """Maps keys to descriptions, separated by category.

    Automatically handles both key types:
    - int keys (Incremental mode) → used directly
    - list keys (NonIncremental mode) → hashed via get_hashcode()

    Used only for formatting diagnosis results, not for algorithm logic.
    """

    def __init__(self):
        self.constraint_map: Dict = {}
        self.configuration_map: Dict = {}
        self.test_case_map: Dict = {}

    def _to_key(self, item):
        """Auto-detect key type and transform accordingly."""
        if isinstance(item, int):
            return item
        return get_hashcode(item)

    def get_description(self, item) -> str:
        """Get description, searching in order: constraint -> configuration -> test_case."""
        key = self._to_key(item)
        if key in self.constraint_map:
            return self.constraint_map[key]
        if key in self.configuration_map:
            return self.configuration_map[key]
        if key in self.test_case_map:
            return self.test_case_map[key]
        return str(item)

    def add_constraint_description(self, key, description: str) -> None:
        """Add description for KB constraint."""
        self.constraint_map[self._to_key(key)] = description

    def add_configuration_description(self, key, description: str) -> None:
        """Add description for configuration item."""
        self.configuration_map[self._to_key(key)] = description

    def add_test_case_description(self, key, description: str) -> None:
        """Add description for test case."""
        self.test_case_map[self._to_key(key)] = description

    def get_descriptions_for(self, ids: List[int]) -> Dict[int, str]:
        """Extract descriptions for given assumption IDs."""
        return {aid: self.get_description(aid) for aid in ids}

    def reset_constraint(self) -> None:
        """Reset constraint map."""
        self.constraint_map = {}

    def reset_configuration(self) -> None:
        """Reset configuration map."""
        self.configuration_map = {}


# === PREPARATION OUTPUT ===

@dataclass
class PreparationOutput:
    """Container for preparation result and description provider."""
    task: DiagnosisTask
    description_provider: DescriptionProvider


# === STRATEGY INTERFACES ===

class DiagnosisTaskPreparationStrategy(ABC):
    """Abstract strategy for preparing diagnosis tasks.

    Used for:
    - Configuration diagnosis
    - Feature model diagnosis
    - Configuration + feature model diagnosis
    - Error diagnosis with test case
    - Redundancy detection (with negated_constraint_map)

    The model parameter accepts any object with: constraint_map, negated_constraint_map,
    variables, task_input, next_available_id, background_knowledge (duck-typed).
    """

    @abstractmethod
    def prepare(self, model: Any) -> PreparationOutput:
        """Prepare diagnosis task and return result with description provider."""
        pass

    @property
    @abstractmethod
    def mode_name(self) -> str:
        """Return mode name for logging."""
        pass


class TestCaseTaskPreparationStrategy(ABC):
    """Abstract strategy for preparing tasks with test cases.

    Used for KBDiag algorithm with positive/negative test cases,
    WipeOutR_T for test case redundancy detection, and ConGen.

    The model parameter accepts any object with: constraint_map, negated_constraint_map,
    variables, task_input, next_available_id, background_knowledge (duck-typed).
    """

    @abstractmethod
    def prepare(self, model: Any) -> PreparationOutput:
        """Prepare test case task and return result with description provider."""
        pass

    @property
    @abstractmethod
    def mode_name(self) -> str:
        """Return mode name for logging."""
        pass


# === SHARED KB PREPARATION FUNCTIONS ===

def prepare_kb(result: DiagnosisTask,
               provider: DescriptionProvider,
               constraint_map: Dict[str, List[List]],
               id_assumption: int,
               negated_constraint_map: Optional[Dict[str, List[List]]]) -> int:
    """Prepare KB with assumptions and optionally negated forms.

    Args:
        result: Task to populate with KB data
        provider: Description provider for formatting
        constraint_map: Constraint name to clauses mapping
        id_assumption: Starting assumption ID
        negated_constraint_map: Optional negated constraints for redundancy detection

    Returns:
        Next available assumption ID
    """
    for key, clauses in constraint_map.items():
        # --- Original constraint with assumption ---
        original_id = id_assumption
        for clause in clauses:
            # assumption => clause (i.e., -assumption v clause)
            new_clause = clause.copy()
            new_clause.append(-original_id)
            result.set_kb.append(new_clause)

        result.assumptions.append(original_id)
        provider.add_constraint_description(original_id, key)
        id_assumption += 1

        # --- Negated constraint (if provided) ---
        if negated_constraint_map is not None:
            negated_key = f"NOT({key})"
            if negated_key in negated_constraint_map:
                negated_id = id_assumption
                for neg_clause in negated_constraint_map[negated_key]:
                    new_neg_clause = neg_clause.copy()
                    new_neg_clause.append(-negated_id)
                    result.set_kb.append(new_neg_clause)

                result.assumptions.append(negated_id)
                result.negation_map[original_id] = negated_id
                provider.add_constraint_description(negated_id, negated_key)
                id_assumption += 1

    return id_assumption


def prepare_configuration(result: DiagnosisTask,
                          provider: DescriptionProvider,
                          variables: Dict[str, int],
                          configuration: Configuration,
                          id_assumption: int) -> int:
    """Prepare configuration with assumptions.

    Args:
        result: Task to populate
        provider: Description provider
        variables: Variable name to ID mapping
        configuration: Configuration to prepare
        id_assumption: Starting assumption ID

    Returns:
        Next available assumption ID
    """
    configuration = convert_keys_to_features(configuration)
    for feat in configuration.elements:
        if feat.name not in variables:
            raise KeyError(f'Feature {feat.name} is not in the model.')

    for feat, value in configuration.elements.items():
        desc = f'{feat.name} = {"true" if value else "false"}'
        var = variables[feat.name] if value else -1 * variables[feat.name]
        clause = [var, -1 * id_assumption]

        result.assumptions.append(id_assumption)
        result.set_kb.append(clause)
        provider.add_configuration_description(id_assumption, desc)

        id_assumption += 1

    return id_assumption


# === DIAGNOSIS STRATEGY ===

class DiagnosisTaskPreparation(DiagnosisTaskPreparationStrategy):
    """Prepare diagnosis task using assumptions.

    Supported task types:
    1. Configuration diagnosis (is_CF_in_C = False):
        C = configuration, B = feature model (PySATModel) + root
    2. Configuration and feature model diagnosis (is_CF_in_C = True):
        C = configuration + feature model (PySATModel), B = root only
    3. Feature model diagnosis (test_case is None):
        C = FM constraints, B = root only
    4. Error diagnosis (debugging):
        C = FM constraints, B = root + test case
    5. Redundancy Detection Task (need negative constraints)
        C = CF (i.e., = PySATModel + {f0 = true}), B = {}
    """

    def __init__(self, mode_name: str = "diagnosis"):
        self._mode_name = mode_name

    @property
    def mode_name(self) -> str:
        return self._mode_name

    def prepare(self, model: 'DiagnosisModel') -> PreparationOutput:
        result = DiagnosisTask()
        provider = DescriptionProvider()

        task_input = model.task_input

        # Determine if negated forms should be used
        negated_constraint_map = model.negated_constraint_map if task_input.for_redundancy else None

        # Use next_available_id to avoid conflicts with Tseitin variables
        id_assumption = model.next_available_id

        # Prepare KB with assumptions and optionally negated forms
        id_assumption = prepare_kb(
            result, provider, model.constraint_map, id_assumption, negated_constraint_map)

        start_id_config = len(result.assumptions)
        if task_input.configuration is not None:
            id_assumption = prepare_configuration(
                result, provider, model.variables, task_input.configuration, id_assumption)

        start_id_test_case = len(result.assumptions)
        if task_input.test_case is not None:
            prepare_configuration(
                result, provider, model.variables, task_input.test_case, id_assumption)

        # Assign set_c and set_b
        has_negated_forms = negated_constraint_map is not None
        self._assign_sets(result, task_input, start_id_config, start_id_test_case, has_negated_forms)

        return PreparationOutput(result, provider)

    def _assign_sets(self, result: DiagnosisTask, task_input: TaskInput,
                     start_id_config: int, start_id_test: int,
                     has_negated_forms: bool = True) -> None:
        """Assign set_c and set_b based on use case."""
        # With negation: [root, neg_root, c1, neg_c1, ...] -> step=2
        # Without negation: [root, c1, c2, ...] -> step=1
        step = _ASSUMPTION_PAIR_STRIDE if has_negated_forms else _ASSUMPTION_SINGLE_STRIDE

        if task_input.configuration is not None:
            if not task_input.with_cf_in_c:
                # C = configuration, B = FM + root
                result.set_b = [result.assumptions[i] for i in range(0, start_id_config, step)]
                result.set_c = result.assumptions[start_id_config:]
            else:
                # C = configuration + FM, B = root only
                result.set_b = [result.assumptions[0]]
                result.set_c = [result.assumptions[i] for i in range(step, start_id_config, step)] + \
                               result.assumptions[start_id_config:]
        else:
            if task_input.test_case is not None:
                # C = FM constraints, B = root + test case
                result.set_b = [result.assumptions[0]] + result.assumptions[start_id_test:]
                result.set_c = [result.assumptions[i] for i in range(step, start_id_config, step)]
            else:
                if has_negated_forms:
                    # Redundancy detection: C = CF (PySATModel, no root), B = {}
                    result.set_c = result.assumptions[step:len(result.assumptions):step]
                else:
                    # C = FM constraints, B = root only
                    result.set_b = [result.assumptions[0]]
                    result.set_c = [result.assumptions[i] for i in range(step, len(result.assumptions), step)]


# === TEST CASE STRATEGY ===

def prepare_testsuite_with_negation(result: TestCaseTask,
                                    provider: DescriptionProvider,
                                    variables: Dict[str, int],
                                    testsuite: TestSuite,
                                    id_assumption: int,
                                    is_negative: bool) -> int:
    """Prepare test cases with assumptions and their negated forms.

    Each test case gets two assumption IDs: original and negated.
    The negated form is a single clause with all literals negated.
    """
    for testcase in testsuite.testcases:
        # --- Original form ---
        original_id = id_assumption
        desc_parts = []
        literals = []

        for assignment in testcase.assignments:
            if assignment.feature not in variables:
                raise KeyError(f'Feature {assignment.feature} is not in the model.')

            desc_parts.append(f'{assignment.feature}={"true" if assignment.value else "false"}')
            var = variables[assignment.feature] if assignment.value else -variables[assignment.feature]
            literals.append(var)
            result.set_kb.append([var, -original_id])

        result.assumptions.append(original_id)
        desc = ' & '.join(desc_parts)
        provider.add_test_case_description(original_id, desc)
        id_assumption += 1

        # --- Negated form ---
        negated_id = id_assumption
        negated_clause = [-lit for lit in literals]
        negated_clause.append(-negated_id)
        result.set_kb.append(negated_clause)

        result.assumptions.append(negated_id)
        provider.add_test_case_description(negated_id, f"NOT({' & '.join(desc_parts)})")

        if is_negative:
            result.set_neg_tv.append(negated_id)
        else:
            result.set_neg_tc.append(negated_id)

        result.negation_map[original_id] = negated_id
        id_assumption += 1

    return id_assumption


class TestCaseTaskPreparation(TestCaseTaskPreparationStrategy):
    """Prepare test case task using assumptions.

    Prepares model for KBDiag algorithm with positive/negative test cases.
    Prepares model for WipeOutR_T for test case redundancy detection.

    Supported task types:
    1. Debugging task - Diagnosis with positive and negative
        C = FM constraints (excluding root), B = root constraint
        TC = positive test cases, TV = negative test cases
    2. WipeOutR_T - Redundancy detection for test cases
        TC = positive test cases
    """

    def __init__(self, mode_name: str = "testcase"):
        self._mode_name = mode_name

    @property
    def mode_name(self) -> str:
        return self._mode_name

    def prepare(self, model: 'DiagnosisModel') -> PreparationOutput:
        result = TestCaseTask()
        provider = DescriptionProvider()

        task_input = model.task_input

        # Start assumption IDs after Tseitin variables
        id_assumption = model.next_available_id

        # Prepare KB (no negated forms needed for TestCaseTask)
        id_assumption = prepare_kb(
            result, provider, model.constraint_map, id_assumption, negated_constraint_map=None)

        # Prepare positive test cases with negated forms
        start_id_tc = len(result.assumptions)
        id_assumption = prepare_testsuite_with_negation(
            result, provider, model.variables, task_input.positive_test_cases, id_assumption, is_negative=False)

        # Prepare negative test cases with negated forms if provided
        start_id_tv = len(result.assumptions)
        if task_input.negative_test_cases is not None:
            prepare_testsuite_with_negation(
                result, provider, model.variables, task_input.negative_test_cases, id_assumption, is_negative=True)

        self._assign_sets(result, start_id_tc, start_id_tv, task_input.negative_test_cases is not None)

        return PreparationOutput(result, provider)

    def _assign_sets(self, result: TestCaseTask,
                     start_id_tc: int, start_id_tv: int,
                     has_negative_test_cases: bool) -> None:
        """Assign sets from assumptions.

        Each test case has two assumptions (original + negated),
        so extract only the original assumptions for set_tc and set_tv.
        """
        result.set_b = [result.assumptions[0]]
        result.set_c = result.assumptions[1:start_id_tc]

        tc_tv_assumptions = result.assumptions[start_id_tc:]
        original_tc_tv = [tc_tv_assumptions[i] for i in range(0, len(tc_tv_assumptions), _ASSUMPTION_PAIR_STRIDE)]

        num_tc_original = (start_id_tv - start_id_tc) // _ASSUMPTION_PAIR_STRIDE
        result.set_tc = original_tc_tv[:num_tc_original]
        result.set_tv = original_tc_tv[num_tc_original:] if has_negative_test_cases else []


# === FORMATTER ===

class DiagnosisFormatter:
    """Formats diagnosis results for display."""

    @staticmethod
    def format(diagnoses: List[List], provider: DescriptionProvider) -> str:
        """Format diagnoses as human-readable string."""
        diagnoses_str = []
        for diag in diagnoses:
            diag_str = [provider.get_description(item) for item in diag]
            diagnoses_str.append(f"[{', '.join(diag_str)}]")
        return ','.join(diagnoses_str)


# === FACTORY ===

class TaskPreparationFactory:
    """Factory for creating task preparation strategies.

    Uses single cached instances since incremental/non-incremental
    distinction only affects the checker, not preparation.
    """

    _diagnosis: DiagnosisTaskPreparation = None
    _testcase: TestCaseTaskPreparation = None

    @classmethod
    def create_diagnosis(cls, is_incremental: bool) -> DiagnosisTaskPreparationStrategy:
        """Create diagnosis task preparation strategy.

        Args:
            is_incremental: Kept for API compatibility (does not affect preparation)
        """
        if cls._diagnosis is None:
            cls._diagnosis = DiagnosisTaskPreparation()
        return cls._diagnosis

    @classmethod
    def create_testcase(cls, is_incremental: bool = True) -> TestCaseTaskPreparationStrategy:
        """Create test case task preparation strategy.

        Args:
            is_incremental: Kept for API compatibility (does not affect preparation)
        """
        if cls._testcase is None:
            cls._testcase = TestCaseTaskPreparation()
        return cls._testcase
