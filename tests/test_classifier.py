"""Tests for the test case classifier."""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

import os
import tempfile
import unittest
from flamapy.metamodels.configuration_metamodel.models import Configuration
from flamapy.metamodels.fm_metamodel.models import Feature
from flamapy.metamodels.fm_metamodel.transformations import UVLReader

from apps.testcases_classifier import (
    TestCasesClassifier,
    read_testsuite,
)
from explanation.models.diagnosis_model_builder import DiagnosisModelBuilder
from explanation.models.testsuite import Assignment, TestCase, TestSuite

RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")
FM_10_1_PATH = os.path.join(RESOURCES_DIR, "FM_10_1.uvl")


def _load_fm(path: str):
    """Load a feature model from UVL file."""
    return UVLReader(path).transform()


def _make_tc(spec: str) -> TestCase:
    """Create TestCase from string like '~CBRec & SDC'."""
    assignments = []
    for part in spec.split("&"):
        part = part.strip()
        if part.startswith("~"):
            assignments.append(Assignment(part[1:], False))
        else:
            assignments.append(Assignment(part, True))
    return TestCase(assignments)


class TestClassifierConsistency(unittest.TestCase):
    """Test the fast-path consistency check classification."""

    @classmethod
    def setUpClass(cls):
        cls.fm = _load_fm(FM_10_1_PATH)

    def test_all_consistent_tcs_are_non_violated(self):
        """TCs that don't violate any constraint → non-violated."""
        tc1 = _make_tc("UBRec & ~CBRec")
        tc2 = _make_tc("MulChoice")
        ts = TestSuite([tc1, tc2])

        clf = TestCasesClassifier(self.fm, "test", max_conflict_sets=3)
        clf.classify(ts)

        self.assertEqual(len(clf._non_violated), 2)
        self.assertEqual(len(clf._violated), 0)
        self.assertEqual(clf._ignored, 0)

    def test_violated_tc_detected(self):
        """TC that violates constraint !CBRec | !SDC → violated."""
        tc = _make_tc("CBRec & SDC")
        ts = TestSuite([tc])

        clf = TestCasesClassifier(self.fm, "test", max_conflict_sets=3)
        clf.classify(ts)

        self.assertEqual(len(clf._violated), 1)
        self.assertEqual(len(clf._non_violated), 0)
        num_conflicts, fingerprint, tc_str = clf._violated[0]
        self.assertIn("CBRec & SDC", tc_str)
        self.assertGreaterEqual(num_conflicts, 1)
        self.assertTrue(fingerprint.startswith("{"), "Fingerprint should contain conflict set IDs")

    def test_mixed_classification(self):
        """Mix of consistent and inconsistent TCs."""
        tc_ok = _make_tc("UBRec & ~CBRec")
        tc_bad1 = _make_tc("CBRec & SDC")       # violates !CBRec | !SDC
        tc_bad2 = _make_tc("SDC & ~Stat")        # violates !SDC | Stat
        ts = TestSuite([tc_ok, tc_bad1, tc_bad2])

        clf = TestCasesClassifier(self.fm, "test", max_conflict_sets=3)
        clf.classify(ts)

        self.assertEqual(len(clf._non_violated), 1)
        self.assertEqual(len(clf._violated), 2)

    def test_empty_testsuite(self):
        """Empty testsuite → no classifications."""
        ts = TestSuite([])
        clf = TestCasesClassifier(self.fm, "test", max_conflict_sets=3)
        clf.classify(ts)

        self.assertEqual(len(clf._non_violated), 0)
        self.assertEqual(len(clf._violated), 0)
        self.assertEqual(clf._ignored, 0)


class TestClassifierOutput(unittest.TestCase):
    """Test .classifiedts output format."""

    @classmethod
    def setUpClass(cls):
        cls.fm = _load_fm(FM_10_1_PATH)

    def test_output_format(self):
        """Verify .classifiedts file format: violated_count, violated, non_violated_count, non_violated."""
        tc_ok = _make_tc("UBRec & ~CBRec")
        tc_bad = _make_tc("CBRec & SDC")
        ts = TestSuite([tc_ok, tc_bad])

        clf = TestCasesClassifier(self.fm, "test_fm", max_conflict_sets=3)
        clf.classify(ts)

        with tempfile.TemporaryDirectory() as tmpdir:
            clf.write_to_file(tmpdir)
            outfile = os.path.join(tmpdir, "test_fm.classifiedts")

            self.assertTrue(os.path.exists(outfile))

            with open(outfile) as f:
                lines = [line.rstrip("\n") for line in f.readlines()]

            # violated_count
            violated_count = int(lines[0])
            self.assertEqual(violated_count, 1)

            # violated TCs — verify count|fingerprint|tc format
            violated_tcs = lines[1 : 1 + violated_count]
            self.assertEqual(len(violated_tcs), 1)
            parts = violated_tcs[0].split("|")
            self.assertEqual(len(parts), 3, "Expected count|fingerprint|tc format")
            self.assertTrue(parts[0].isdigit())
            self.assertGreaterEqual(int(parts[0]), 1)
            self.assertTrue(parts[1].startswith("{"), "Fingerprint should start with '{'")
            self.assertIn("&", parts[2])  # tc string has assignments

            # non_violated_count
            nv_idx = 1 + violated_count
            non_violated_count = int(lines[nv_idx])
            self.assertEqual(non_violated_count, 1)

            # non_violated TCs
            non_violated_tcs = lines[nv_idx + 1 : nv_idx + 1 + non_violated_count]
            self.assertEqual(len(non_violated_tcs), 1)


class TestTcToString(unittest.TestCase):
    """Test TC string formatting."""

    def test_positive_assignment(self):
        tc = _make_tc("FeatureA")
        result = TestCasesClassifier._tc_to_string(tc)
        self.assertEqual(result, "FeatureA")

    def test_negated_assignment(self):
        tc = _make_tc("~FeatureA")
        result = TestCasesClassifier._tc_to_string(tc)
        self.assertEqual(result, "~FeatureA")

    def test_mixed_assignments(self):
        tc = _make_tc("~FeatureA & FeatureB & ~FeatureC")
        result = TestCasesClassifier._tc_to_string(tc)
        self.assertEqual(result, "~FeatureA & FeatureB & ~FeatureC")


class TestReadTestsuite(unittest.TestCase):
    """Test testsuite file reading with 6-line header skip."""

    def test_read_testsuite_skips_header(self):
        """Verify 6 header lines are skipped when reading .testsuite files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".testsuite", delete=False) as f:
            f.write("3\n")     # total
            f.write("1\n")     # dead
            f.write("0\n")     # false_opt
            f.write("1\n")     # full_mand
            f.write("0\n")     # false_mand
            f.write("1\n")     # partial
            f.write("FeatureA\n")
            f.write("~FeatureB\n")
            f.write("FeatureA & ~FeatureB\n")
            tmppath = f.name

        try:
            from pathlib import Path
            ts = read_testsuite(Path(tmppath))
            self.assertEqual(len(ts.testcases), 3)

            # First TC: FeatureA (positive)
            self.assertEqual(ts.testcases[0].assignments[0].feature, "FeatureA")
            self.assertTrue(ts.testcases[0].assignments[0].value)

            # Second TC: ~FeatureB (negative)
            self.assertEqual(ts.testcases[1].assignments[0].feature, "FeatureB")
            self.assertFalse(ts.testcases[1].assignments[0].value)

            # Third TC: FeatureA & ~FeatureB
            self.assertEqual(len(ts.testcases[2].assignments), 2)
        finally:
            os.unlink(tmppath)


class TestAssumptionIdStability(unittest.TestCase):
    """Verify FM constraint IDs are stable across per-TC model builds."""

    @classmethod
    def setUpClass(cls):
        cls.fm = _load_fm(FM_10_1_PATH)

    def test_ids_stable_across_different_test_cases(self):
        """Same FM → same constraint assumption IDs regardless of TC."""
        tc1 = Configuration({Feature("CBRec"): False})
        tc2 = Configuration({Feature("SDC"): False})

        model1 = (DiagnosisModelBuilder.from_feature_model(self.fm)
                  .with_test_case(tc1).use_incremental().build())
        model2 = (DiagnosisModelBuilder.from_feature_model(self.fm)
                  .with_test_case(tc2).use_incremental().build())

        self.assertEqual(set(model1.get_c()), set(model2.get_c()),
                         "FM constraint IDs must be identical across TC builds")


if __name__ == "__main__":
    unittest.main()
