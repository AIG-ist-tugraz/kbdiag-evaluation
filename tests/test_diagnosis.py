"""
Diagnosis Test Suite
====================

This module tests various diagnosis algorithms with different configurations.

To enable/disable specific tests, modify the ENABLED_TESTS dictionary below.
To enable/disable specific parameter combinations, modify ENABLED_PARAMS.
"""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

import os
import unittest

from flamapy.metamodels.configuration_metamodel.transformations import ConfigurationBasicReader
from parameterized import parameterized

from explanation.models import DiagnosisModelBuilder
from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.checker import CheckerFactory
from explanation.operations.algorithms.fastdiag import FastDiag
from explanation.operations.algorithms.fastdiagp import FastDiagP
from explanation.operations.algorithms.kbdiag import KBDiag
from explanation.operations.algorithms.profiler import ProfilerMode, ProfilerPreset, profiler_session
from explanation.operations.algorithms.quickxplain import QuickXPlain
from explanation.operations.algorithms.quickxplain_with_testcases import QuickXPlainWithTestCases
from explanation.operations.pysat_abstract_explanation import _format_results
from explanation.operations.pysat_explanation_builder import (
    PySATDiagnosisBuilder, PySATTestcaseBuilder,
    PySATRedundancyTestCasesBuilder, PySATRedundancyConstraintsBuilder, PySATTestcaseQuickXplainBuilder
)
from explanation.transformations.testsuite_reader import TestSuiteReader

# =============================================================================
# TEST CONFIGURATION - Enable/Disable Tests Here
# =============================================================================

ENABLED_TESTS = {
    # Single algorithm tests
    'fastdiag_1diag': True,
    'quickxplain_1cs': True,
    'fastdiagp_1diag': True,
    'kbdiag_1diag_1': True,
    'kbdiag_1diag_1_neg': True,
    'kbdiag_1diag_2': True,
    'kbdiag_1diag_2_neg': True,
    'quickxplainwithtestcases_1cs_1': True,
    'quickxplainwithtestcases_1diag_1_neg': True,

    # HSDAG with FastDiag
    'hsdag_fastdiag_1diag': True,
    'hsdag_fastdiag_2diag': True,
    'hsdag_fastdiag_all': True,

    # HSDAG with QuickXPlain
    'hsdag_quickxplain_1cs': True,
    'hsdag_quickxplain_dfs': True,
    'hsdag_quickxplain_2cs': True,
    'hsdag_quickxplain_all': True,

    # With configuration/test case
    'hsdag_fastdiag_configuration': True,
    'hsdag_quickxplain_configuration': True,
    'hsdag_fastdiag_testcase': True,
    'hsdag_quickxplain_testcase': True,

    # KBDiag tests
    'hsdag_kbdiag_1diag_1': True,
    'hsdag_kbdiag_1diag_1_neg': True,
    'hsdag_kbdiag_all_1': True,
    'hsdag_kbdiag_all_1_neg': True,
    'hsdag_kbdiag_1diag_2': True,
    'hsdag_kbdiag_1diag_2_neg': True,
    'hsdag_kbdiag_all_2': True,
    'hsdag_kbdiag_all_2_neg': True,

    # HSDAG+QuickXPlainWithTestCases tests
    'hsdag_quickxplainwithtestcases_1cs_1': True,
    'hsdag_quickxplainwithtestcases_1cs_1_neg': True,
    'hsdag_quickxplainwithtestcases_all_1': True,
    'hsdag_quickxplainwithtestcases_all_1_neg': True,

    # WipeOutR_FM tests
    'wipeoutr_fm_redundancy': True,
    'pysat_redundancy_constraints': True,

    # WipeOutR_T tests
    'wipeoutr_t_redundancy': True,
}

# =============================================================================
# PARAMETER CONFIGURATION - Enable/Disable Parameter Combinations Here
# =============================================================================

# Individual parameter toggles
ENABLED_PARAMS = {
    'incremental_with_profiling': True,
    'incremental_no_profiling': True,
    'nonincremental_with_profiling': True,
    'nonincremental_no_profiling': True,
    'sat4j_with_profiling': True,
    'sat4j_no_profiling': True,
}

# =============================================================================
# PARAMETER SETS
# =============================================================================

def _get_standard_params():
    """Get standard parameter combinations based on ENABLED_PARAMS config."""
    all_params = [
        ("incremental_with_profiling", True, 'glucose3', False, True),
        ("incremental_no_profiling", True, 'glucose3', False, False),
        ("nonincremental_with_profiling", False, 'glucose3', False, True),
        ("nonincremental_no_profiling", False, 'glucose3', False, False),
        ("sat4j_with_profiling", False, None, True, True),
        ("sat4j_no_profiling", False, None, True, False),
    ]
    return [p for p in all_params if ENABLED_PARAMS.get(p[0], True)]

def _get_sat4j_only_params():
    """Get SAT4J-only parameter combinations."""
    all_params = [
        ("sat4j_with_profiling", False, None, True, True),
        ("sat4j_no_profiling", False, None, True, False),
    ]
    return [p for p in all_params if ENABLED_PARAMS.get(p[0], True)]

def _get_no_sat4j_params():
    """Get standard parameter combinations based on ENABLED_PARAMS config."""
    all_params = [
        ("incremental_with_profiling", True, 'glucose3', False, True),
        ("incremental_no_profiling", True, 'glucose3', False, False),
        ("nonincremental_with_profiling", False, 'glucose3', False, True),
        ("nonincremental_no_profiling", False, 'glucose3', False, False),
        # ("sat4j_with_profiling", False, None, True, True),
        # ("sat4j_no_profiling", False, None, True, False),
    ]
    return [p for p in all_params if ENABLED_PARAMS.get(p[0], True)]

STANDARD_PARAMS = _get_standard_params()
SAT4J_ONLY_PARAMS = _get_sat4j_only_params()
NO_SAT4J_PARAMS = _get_no_sat4j_params()

# =============================================================================
# TEST RESOURCES
# =============================================================================

# Get the directory of this test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(TEST_DIR, 'resources')


class Resources:
    FM_INCONSISTENT = os.path.join(RESOURCES_DIR, "smartwatch_inconsistent.fide")
    FM_CONSISTENT = os.path.join(RESOURCES_DIR, "smartwatch_consistent.fide")
    FM_DEADFEATURE = os.path.join(RESOURCES_DIR, "smartwatch_deadfeature.fide")
    CONF_NONVALID = os.path.join(RESOURCES_DIR, "smartwatch_nonvalid.csvconf")
    CONF_TESTCASE = os.path.join(RESOURCES_DIR, "smartwatch_testcase.csvconf")
    # for test cases
    FM_10_1 = os.path.join(RESOURCES_DIR, "FM_10_1.uvl")
    FM_10_1_POSITIVE_TESTCASES = os.path.join(RESOURCES_DIR, "FM_10_1.positive.testcases")
    FM_10_1_NEGATIVE_TESTCASES = os.path.join(RESOURCES_DIR, "FM_10_1.negative.testcases")
    FM_10_2 = os.path.join(RESOURCES_DIR, "FM_10_2.uvl")
    FM_10_2_POSITIVE_TESTCASES = os.path.join(RESOURCES_DIR, "FM_10_2.positive.testcases")
    FM_10_2_NEGATIVE_TESTCASES = os.path.join(RESOURCES_DIR, "FM_10_2.negative.testcases")
    # For WipeOutR_FM tests
    FM_REDUNDANT = os.path.join(RESOURCES_DIR, "redundant_fm.uvl")
    # For WipeOutR_T tests
    REDUNDANT_TESTSUITE = os.path.join(RESOURCES_DIR, "redundant_testsuite.testcases")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _profiler_preset(enable_profiling: bool) -> ProfilerPreset:
    """Map enable_profiling flag to ProfilerPreset."""
    return ProfilerPreset.BENCHMARK if enable_profiling else ProfilerPreset.DISABLED

def print_test_header(name: str, is_incremental: bool, solver_name: str,
                      use_sat4j: bool, enable_profiling: bool):
    """Print standardized test header."""
    print("\n" + "=" * 70)
    print(f"Running test: {name} | is_incremental: {is_incremental} | "
          f"solver_name: {solver_name} | use_sat4j: {use_sat4j} | enable_profiling: {enable_profiling}")

def print_profiler_status(profiler):
    """Print profiler status."""
    status = "ENABLED" if profiler.is_profiling else "DISABLED"
    print(f"Profiler {status}.")

def create_checker(use_sat4j: bool, model: DiagnosisModel):
    """Create appropriate checker based on configuration."""
    if use_sat4j:
        return CheckerFactory.create_sat4jchecker(
            set_kb=model.get_kb(), assumptions=model.get_assumptions())
    return CheckerFactory.create_from_model(model)

def _skip_disabled(test_name: str):
    """Create unittest.skipIf decorator for disabled tests."""
    return unittest.skipIf(not ENABLED_TESTS.get(test_name, True), f'{test_name} disabled in ENABLED_TESTS')


class DiagnosisTest(unittest.TestCase):
    """Test suite for diagnosis algorithms with parameterized configurations."""

    # =============================================================================
    # SINGLE ALGORITHM TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('fastdiag_1diag')
    def test_fastdiag_1diag(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test FastDiag with different checker implementations and profiling modes."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            checker = create_checker(use_sat4j, model)
            fastdiag = FastDiag(checker)
            diagnosis = fastdiag.find_diagnosis(model.get_c(), model.get_b())

            profiler.print_summary(include_raw_timers=True)

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)
            print(f"{diag_mess}")
            assert diag_mess == 'Diagnosis: [(5) IMPLIES[Smartwatch][Analog]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('quickxplain_1cs')
    def test_quickxplain_1cs(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test QuickXPlain to find one conflict."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            checker = create_checker(use_sat4j, model)
            quickxplain = QuickXPlain(checker)
            conflict = quickxplain.find_conflict(model.get_c(), model.get_b())

            profiler.print_summary(include_raw_timers=True)

            cs_mess = _format_results("Conflict", "Conflicts", [conflict], model)
            print(f"{cs_mess}")
            assert cs_mess == 'Conflict: [(3) OR[NOT[Analog][]][NOT[Cellular][]], (4) IMPLIES[Smartwatch][Cellular], (5) IMPLIES[Smartwatch][Analog]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('fastdiagp_1diag')
    def test_fastdiagp_1diag(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test FastDiagP (parallel) to find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling), ProfilerMode.MULTI_PROCESS) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            checker = create_checker(use_sat4j, model)
            fastdiagp = FastDiagP(checker)
            diagnosis = fastdiagp.find_diagnosis(model.get_c(), model.get_b())

            profiler.print_summary(include_raw_timers=True)

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)
            print(diag_mess)
            assert diag_mess == 'Diagnosis: [(5) IMPLIES[Smartwatch][Analog]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('kbdiag_1diag_1')
    def test_kbdiag_1diag_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            kbdiag = KBDiag(checker)
            _, diagnosis = kbdiag.find_diagnosis(model.get_c(), model.get_b(), model.get_tc())

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)

            profiler.print_summary(include_raw_timers=True)
            print(diag_mess)
            assert diag_mess == 'Diagnosis: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('kbdiag_1diag_1_neg')
    def test_kbdiag_1diag_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            kbdiag = KBDiag(checker)
            _, diagnosis = kbdiag.find_diagnosis(model.get_c(), model.get_b(), model.get_tc(), model.get_neg_tv())

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)

            profiler.print_summary(include_raw_timers=True)
            print(diag_mess)
            assert diag_mess == 'Diagnosis: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]QType ]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('kbdiag_1diag_2')
    def test_kbdiag_1diag_2(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_2_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            kbdiag = KBDiag(checker)
            _, diagnosis = kbdiag.find_diagnosis(model.get_c(), model.get_b(), model.get_tc(), model.get_neg_tv())

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)

            profiler.print_summary(include_raw_timers=True)
            print(diag_mess)
            assert diag_mess == 'Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('kbdiag_1diag_2_neg')
    def test_kbdiag_1diag_2_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_2_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            kbdiag = KBDiag(checker)
            _, diagnosis = kbdiag.find_diagnosis(model.get_c(), model.get_b(), model.get_tc(), model.get_neg_tv())

            diag_mess = _format_results("Diagnosis", "Diagnoses", [diagnosis], model)

            profiler.print_summary(include_raw_timers=True)
            print(diag_mess)
            assert diag_mess == 'Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('quickxplainwithtestcases_1cs_1')
    def test_quickxplainwithtestcases_1cs_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            quickxplain = QuickXPlainWithTestCases(checker)
            _, cs = quickxplain.find_conflict_set(model.get_c(), model.get_b(), model.get_tc())

            cs_mess = _format_results("Conflict", "Conflicts", [cs], model)

            profiler.print_summary(include_raw_timers=True)
            print(cs_mess)
            assert cs_mess == 'Conflict: [(mandatory) CheckR[1,1]SDC , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('quickxplainwithtestcases_1diag_1_neg')
    def test_quickxplainwithtestcases_1diag_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .use_incremental(is_incremental)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .build())

            checker = create_checker(use_sat4j, model)
            quickxplain = QuickXPlainWithTestCases(checker)
            _, cs = quickxplain.find_conflict_set(model.get_c(), model.get_b(), model.get_tc(), model.get_neg_tv())

            diag_mess = _format_results("Conflict", "Conflicts", [cs], model)

            profiler.print_summary(include_raw_timers=True)
            print(diag_mess)
            assert diag_mess == 'Conflict: [(mandatory) CheckR[1,1]SDC ]'

    # =============================================================================
    # HSDAG WITH FASTDIAG TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_fastdiag_1diag')
    def test_hsdag_fastdiag_1diag(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with FastDiag: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = (PySATDiagnosisBuilder.for_diagnosis_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_diagnosis())
            hsdag = builder.with_max_diagnoses(1).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == ['Diagnosis: [(5) IMPLIES[Smartwatch][Analog]]', 'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_fastdiag_2diag')
    def test_hsdag_fastdiag_2diag(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with FastDiag: find two diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_diagnosis_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_diagnosis()
            hsdag = builder.with_max_diagnoses(2).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == ['Diagnoses: [(5) IMPLIES[Smartwatch][Analog]],[(4) IMPLIES[Smartwatch][Cellular]]',
                              'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_fastdiag_all')
    def test_hsdag_fastdiag_all(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with FastDiag: find all diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_diagnosis_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_diagnosis()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnoses: [(5) IMPLIES[Smartwatch][Analog]],[(4) IMPLIES[Smartwatch][Cellular]],[(3) OR[NOT[Analog][]][NOT[Cellular][]]]',
                'Conflict: [(5) IMPLIES[Smartwatch][Analog], (4) IMPLIES[Smartwatch][Cellular], (3) OR[NOT[Analog][]][NOT[Cellular][]]]']

    # =============================================================================
    # HSDAG WITH QUICKXPLAIN TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplain_1cs')
    def test_hsdag_quickxplain_1cs(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find one conflict."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.with_max_conflicts(1).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Conflict: [(5) IMPLIES[Smartwatch][Analog], (4) IMPLIES[Smartwatch][Cellular], (3) OR[NOT[Analog][]][NOT[Cellular][]]]',
                'No diagnosis found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplain_dfs')
    def test_hsdag_quickxplain_one_depth_first_search(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find one conflict using depth-first search."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.with_max_diagnoses(1).with_depth_first_search(True).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Conflict: [(5) IMPLIES[Smartwatch][Analog], (4) IMPLIES[Smartwatch][Cellular], (3) OR[NOT[Analog][]][NOT[Cellular][]]]',
                'Diagnosis: [(5) IMPLIES[Smartwatch][Analog]]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplain_2cs')
    def test_hsdag_quickxplain_2cs(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find two conflicts."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.with_max_conflicts(2).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Conflict: [(5) IMPLIES[Smartwatch][Analog], (4) IMPLIES[Smartwatch][Cellular], (3) OR[NOT[Analog][]][NOT[Cellular][]]]',
                'Diagnoses: [(5) IMPLIES[Smartwatch][Analog]],[(4) IMPLIES[Smartwatch][Cellular]],[(3) OR[NOT[Analog][]][NOT[Cellular][]]]']

    @parameterized.expand(SAT4J_ONLY_PARAMS)
    @_skip_disabled('hsdag_quickxplain_all')
    def test_hsdag_quickxplain_all(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find all conflicts."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_INCONSISTENT)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Conflict: [(5) IMPLIES[Smartwatch][Analog], (4) IMPLIES[Smartwatch][Cellular], (3) OR[NOT[Analog][]][NOT[Cellular][]]]',
                'Diagnoses: [(5) IMPLIES[Smartwatch][Analog]],[(4) IMPLIES[Smartwatch][Cellular]],[(3) OR[NOT[Analog][]][NOT[Cellular][]]]']

    # =============================================================================
    # CONFIGURATION AND TEST CASE TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_fastdiag_configuration')
    def test_hsdag_fastdiag_with_configuration(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with FastDiag: diagnose with configuration."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            configuration = ConfigurationBasicReader(Resources.CONF_NONVALID).transform()
            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_CONSISTENT)
                     .with_configuration(configuration)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_diagnosis_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_diagnosis()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            assert result == ['Diagnoses: [E-ink = true],[Analog = true]',
                              'Conflict: [E-ink = true, Analog = true]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplain_configuration')
    def test_hsdag_quickxplain_with_configuration(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find conflicts with configuration."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            configuration = ConfigurationBasicReader(Resources.CONF_NONVALID).transform()
            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_CONSISTENT)
                     .with_configuration(configuration)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == ['Conflict: [E-ink = true, Analog = true]',
                              'Diagnoses: [E-ink = true],[Analog = true]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_fastdiag_testcase')
    def test_hsdag_fastdiag_with_test_case(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with FastDiag: diagnose with test case."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            test_case = ConfigurationBasicReader(Resources.CONF_TESTCASE).transform()
            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_DEADFEATURE)
                     .with_test_case(test_case)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_diagnosis_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_diagnosis()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == ['Diagnoses: [(4) IMPLIES[Smartwatch][Analog]],'
                              '[(alternative) Screen[1,1]Analog High Resolution E-ink ]',
                              'Conflict: [(4) IMPLIES[Smartwatch][Analog], '
                              '(alternative) Screen[1,1]Analog High Resolution E-ink ]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplain_testcase')
    def test_hsdag_quickxplain_with_testcase(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with QuickXPlain: find conflicts with test case."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            test_case = ConfigurationBasicReader(Resources.CONF_TESTCASE).transform()
            model = (DiagnosisModelBuilder
                     .from_fide(Resources.FM_DEADFEATURE)
                     .with_test_case(test_case)
                     .use_incremental(is_incremental)
                     .build())

            builder = PySATDiagnosisBuilder.for_conflict_sat4j() if use_sat4j else PySATDiagnosisBuilder.for_conflict()
            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            print(result)
            assert result == ['Conflict: [(4) IMPLIES[Smartwatch][Analog], '
                              '(alternative) Screen[1,1]Analog High Resolution E-ink ]',
                              'Diagnoses: [(4) IMPLIES[Smartwatch][Analog]],'
                              '[(alternative) Screen[1,1]Analog High Resolution E-ink ]']

    # =============================================================================
    # HSDAG + KBDIAG TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_1diag_1')
    def test_hsdag_kbdiag_1diag_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = builder.with_max_diagnoses(1).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]]',
                'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_1diag_1_neg')
    def test_hsdag_kbdiag_1diag_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .with_max_diagnoses(1)
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]QType ]',
                'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_all_1')
    def test_hsdag_kbdiag_all_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: all diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == ('Diagnoses: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType , '
                                 '(Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], '
                                 '(Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , '
                                 '(mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]QType ]')

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_all_1_neg')
    def test_hsdag_kbdiag_all_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: all diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == 'Diagnoses: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]QType ],[(mandatory) CheckR[1,1]RecEng , (alternative) RecEng[1,1]UBRec CBRec , (optional) CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (optional) CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (alternative) RecEng[1,1]UBRec CBRec , (mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (alternative) RecEng[1,1]UBRec CBRec , (optional) CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (optional) CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]]'

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_1diag_2')
    def test_hsdag_kbdiag_1diag_2(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = builder.with_max_diagnoses(1).build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]',
                'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_1diag_2_neg')
    def test_hsdag_kbdiag_1diag_2_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: find one diagnosis."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_2_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .with_max_diagnoses(1)
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]',
                'No conflict found']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_all_2')
    def test_hsdag_kbdiag_all_2(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: all diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == ('Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]')

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_kbdiag_all_2_neg')
    def test_hsdag_kbdiag_all_2_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """HSDAG with KBDIAG: all diagnoses."""
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_2_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_2_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_2)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == ('Diagnosis: [(mandatory) jplug[1,1]interface , (alternative) interface[1,1]sdi mdi , (optional) diagram_builder[0,1]uml , (Constraint 0) OR[NOT[gui_builder][]][NOT[sdi][]]]')

    # =============================================================================
    # HSDAG + QUICKXPLAINWITHTESTCASES TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplainwithtestcases_1diag_1')
    def test_hsdag_quickxplainwithtestcases_1diag_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseQuickXplainBuilder.for_debugging()
            if builder is None:
                return

            op = builder.with_max_diagnoses(1).build()
            op.execute(model)
            result = op.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType ]',
                'Conflicts: [(Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (mandatory) '
                'CheckR[1,1]SDC ],[(Constraint 1) OR[NOT[SDC][]][Stat], (mandatory) '
                'CheckR[1,1]SDC ],[(mandatory) CheckR[1,1]RecEng ],[(mandatory) '
                'CheckR[1,1]QType ]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplainwithtestcases_1diag_1_neg')
    def test_hsdag_quickxplainwithtestcases_1diag_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseQuickXplainBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .with_max_diagnoses(1)
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result)
            assert result == [
                'Diagnosis: [(mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]QType ]',
                'Conflicts: [(mandatory) CheckR[1,1]SDC ],[(mandatory) CheckR[1,1]RecEng ],[(mandatory) CheckR[1,1]QType ]']

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplainwithtestcases_all_1')
    def test_hsdag_quickxplainwithtestcases_all_1(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseQuickXplainBuilder.for_debugging()
            if builder is None:
                return

            hsdag = builder.build()
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == ('Diagnoses: [(mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]RecEng , '
                                 '(mandatory) CheckR[1,1]QType ],[(Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], '
                                 '(Constraint 1) OR[NOT[SDC][]][Stat], (mandatory) CheckR[1,1]RecEng , '
                                 '(mandatory) CheckR[1,1]QType ],[(Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], '
                                 '(mandatory) CheckR[1,1]SDC , (mandatory) CheckR[1,1]RecEng , (mandatory) '
                                 'CheckR[1,1]QType ]')

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('hsdag_quickxplainwithtestcases_all_1_neg')
    def test_hsdag_quickxplainwithtestcases_all_1_neg(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with (profiler_session(_profiler_preset(enable_profiling)) as profiler):
            print_profiler_status(profiler)

            positive_testcases = TestSuiteReader(Resources.FM_10_1_POSITIVE_TESTCASES).transform()
            negative_testcases = TestSuiteReader(Resources.FM_10_1_NEGATIVE_TESTCASES).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_10_1)
                     .with_positive_testcases(positive_testcases)
                     .with_negative_testcases(negative_testcases)
                     .use_incremental(is_incremental)
                     .build())

            builder = None if use_sat4j else PySATTestcaseBuilder.for_debugging()
            if builder is None:
                return

            hsdag = (builder
                     .build())
            hsdag.execute(model)
            result = hsdag.get_result()

            profiler.print_summary(include_raw_timers=True)
            print(result[0])
            assert result[0] == ('Diagnoses: [(mandatory) CheckR[1,1]RecEng , (mandatory) CheckR[1,1]SDC , '
                                 '(mandatory) CheckR[1,1]QType ],[(mandatory) CheckR[1,1]RecEng , '
                                 '(alternative) RecEng[1,1]UBRec CBRec , (optional) CheckR[0,1]Stat , '
                                 '(mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , '
                                 '(Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) '
                                 'OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (optional) '
                                 'CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (or) QType[1,2]MulChoice '
                                 'ImgAnaTask , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) '
                                 'OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (alternative) '
                                 'RecEng[1,1]UBRec CBRec , (mandatory) CheckR[1,1]QType , (or) '
                                 'QType[1,2]MulChoice ImgAnaTask , (Constraint 0) '
                                 'OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) '
                                 'OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (alternative) '
                                 'RecEng[1,1]UBRec CBRec , (optional) CheckR[0,1]Stat , (mandatory) '
                                 'CheckR[1,1]QType , (Constraint 0) OR[NOT[CBRec][]][NOT[SDC][]], (Constraint '
                                 '1) OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (mandatory) '
                                 'CheckR[1,1]QType , (or) QType[1,2]MulChoice ImgAnaTask , (Constraint 0) '
                                 'OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) '
                                 'OR[NOT[SDC][]][Stat]],[(mandatory) CheckR[1,1]RecEng , (optional) '
                                 'CheckR[0,1]Stat , (mandatory) CheckR[1,1]QType , (Constraint 0) '
                                 'OR[NOT[CBRec][]][NOT[SDC][]], (Constraint 1) OR[NOT[SDC][]][Stat]]')

    # =============================================================================
    # WIPEOUTR_FM TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('wipeoutr_fm_redundancy')
    def test_wipeoutr_fm_redundancy(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test WipeOutR_FM: detect redundant constraints in feature model.

        Uses a feature model with a redundant constraint:
        - RedundantFM (root)
          - FeatureA (mandatory)
          - FeatureB (mandatory)
          - FeatureC (optional)
        - Constraint 0: RedundantFM => FeatureA (REDUNDANT - FeatureA is already mandatory)
        - Constraint 1: FeatureC <=> FeatureB (NOT redundant)
        """
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            # Load model with negated forms created during transformation
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_REDUNDANT)
                     .for_redundancy(True)
                     .use_incremental(is_incremental)
                     .build())

            # Verify negated constraint map is populated
            print(f"Constraint map: {list(model.constraint_map.keys())}")
            print(f"Negated constraint map: {list(model.negated_constraint_map.keys())}")
            assert len(model.negated_constraint_map) > 0, "Negated constraint map should be populated"

            # Get constraint IDs and negation map
            set_cf = model.get_cf()
            negation_map = model.get_negation_map()

            print(f"CF (constraint IDs): {set_cf}")
            print(f"negation_map: {negation_map}")
            assert len(set_cf) > 0, "Should have constraints"
            assert len(negation_map) > 0, "Should have negated forms"

            builder = None if use_sat4j else PySATRedundancyConstraintsBuilder.for_redundancy_constraints(profiler)
            if builder is None:
                return

            operation = builder.build()
            operation.execute(model)

            # Get results
            result = operation.get_result()

            print(result)

            profiler.print_summary(include_raw_timers=True)

            assert len(result) == 2, f"Expected 2 lists (redundant and non-redundant), got {len(result)}"
            assert result[0] == 'Redundant constraints: [(Constraint 0) IMPLIES[RedundantFM][FeatureA]]'
            assert result[1] == 'Non-redundant constraints: [(Constraint 1) OR[NOT[FeatureC][]][NOT[FeatureB][]], (optional) RedundantFM[0,1]FeatureC , (mandatory) RedundantFM[1,1]FeatureB , (mandatory) RedundantFM[1,1]FeatureA ]'


    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('pysat_redundancy_constraints')
    def test_pysat_redundancy_constraints(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test PySATRedundancyConstraints operation using WipeOutR_FM algorithm.

        Uses a feature model with a redundant constraint:
        - RedundantFM (root)
          - FeatureA (mandatory)
          - FeatureB (mandatory)
          - FeatureC (optional)
        - Constraint 0: RedundantFM => FeatureA (REDUNDANT - FeatureA is already mandatory)
        - Constraint 1: FeatureC <=> FeatureB (NOT redundant)

        This test verifies the PySATRedundancyConstraints operation wrapper.
        """
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            # Load model with negated forms created during transformation
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_REDUNDANT)
                     .for_redundancy(True)
                     .use_incremental(is_incremental)
                     .build())

            # Verify negated constraint map is populated
            print(f"Constraint map: {list(model.constraint_map.keys())}")
            print(f"Negated constraint map: {list(model.negated_constraint_map.keys())}")
            assert len(model.negated_constraint_map) > 0, "Negated constraint map should be populated"

            # Create and configure the operation using builder
            builder = None if use_sat4j else PySATRedundancyConstraintsBuilder.for_redundancy_constraints(profiler)
            if builder is None:
                return
            operation = builder.build()

            # Execute the operation
            operation.execute(model)

            # Get results
            redundant = operation.get_redundant()
            non_redundant = operation.get_non_redundant()

            # Print formatted messages
            for msg in operation.get_result():
                print(msg)

            profiler.print_summary(include_raw_timers=True)

            # Verify results
            print(f"Found {len(redundant)} redundant and {len(non_redundant)} non-redundant constraints")

            # The constraint "RedundantFM => FeatureA" should be detected as redundant
            assert len(redundant) >= 1, f"Expected at least 1 redundant constraint, got {len(redundant)}"

            # Verify total count matches
            assert len(redundant) + len(non_redundant) == len(model.get_c()), \
                "Total redundant + non-redundant should equal all constraints"

            assert operation.get_result()[0] == 'Redundant constraints: [(Constraint 0) IMPLIES[RedundantFM][FeatureA]]'
            assert operation.get_result()[1] == 'Non-redundant constraints: [(Constraint 1) OR[NOT[FeatureC][]][NOT[FeatureB][]], (optional) RedundantFM[0,1]FeatureC , (mandatory) RedundantFM[1,1]FeatureB , (mandatory) RedundantFM[1,1]FeatureA ]'


    # =============================================================================
    # WIPEOUTR_T TESTS
    # =============================================================================

    @parameterized.expand(STANDARD_PARAMS)
    @_skip_disabled('wipeoutr_t_redundancy')
    def test_wipeoutr_t_redundancy(self, name, is_incremental, solver_name, use_sat4j, enable_profiling):
        """Test PySATRedundancyTestCases operation using WipeOutR_T algorithm.

        Uses the same test suite as test_wipeoutr_t_redundancy:
        - t1: FeatureA = true (REDUNDANT - covered by t3)
        - t2: FeatureC = false (NOT redundant)
        - t3: FeatureA = true, FeatureB = true (more specific than t1)

        This test verifies the PySATRedundancyTestCases operation wrapper.
        """
        print_test_header(name, is_incremental, solver_name, use_sat4j, enable_profiling)

        with profiler_session(_profiler_preset(enable_profiling)) as profiler:
            print_profiler_status(profiler)

            testsuite = TestSuiteReader(Resources.REDUNDANT_TESTSUITE).transform()
            model = (DiagnosisModelBuilder
                     .from_uvl(Resources.FM_REDUNDANT)
                     .with_testcases(testsuite)
                     .use_incremental(is_incremental)
                     .build())

            print(f"Test suite has {len(testsuite.testcases)} test cases")
            for i, tc in enumerate(testsuite.testcases):
                print(f"  t{i + 1}: {tc}")

            builder = None if use_sat4j else PySATRedundancyTestCasesBuilder.for_redundancy_test_cases(profiler)
            if builder is None:
                return

            operation = (builder
                         .build())
            operation.execute(model)

            # Get results
            result = operation.get_result()

            print(result)
            profiler.print_summary(include_raw_timers=True)

            assert len(result) == 2, f"Expected 2 lists (redundant and non-redundant), got {len(result)}"
            assert result[0] == 'Redundant test cases: [FeatureA=true]', "Expected 'FeatureA = true' to be redundant"
            assert result[1] == 'Non-redundant test cases: [FeatureC=false, FeatureA=true & FeatureB=true]', \
                "Expected 'FeatureC = false' and 'FeatureA = true & FeatureB = true' to be non-redundant"



if __name__ == '__main__':
    unittest.main()
