"""
QuickXPlainWithTestCasesLabeler

HSLabeler for QuickXPlainWithTestCases algorithm.
Integrates QuickXPlainWithTestCases with HSDAG for diagnosis computation.

Based on Java implementation:
at.tugraz.ist.ase.kbdiag.debugging.algorithms.hsdag.labeler.QuickXPlainWithTestCasesLabeler

Author: Viet-Man Le (Python port)
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

import logging
from dataclasses import dataclass, field
from typing import List, Any, Optional

from .labeler import IHSLabelable, LabelerType, AbstractHSParameters
from ...checker import ConsistencyChecker
from ...quickxplain_with_testcases import QuickXPlainWithTestCases


@dataclass
class QuickXPlainWithTestCasesParameters(AbstractHSParameters):
    set_b: List
    set_tc: List
    set_neg_tv: List

    test_case: Optional[List] = field(default=None)  # The specific test case causing conflict

    def __str__(self) -> str:
        """String representation of parameters."""
        return (f"QuickXPlainWithTestCasesParameters{{"
                f"C={self.set_c}, "
                f"B={self.set_b},"
                f"TC={self.set_tc},"
                f"TV={self.set_neg_tv},"
                f"test_case={'set' if self.test_case else 'None'}}}")


class QuickXPlainWithTestCasesLabeler(QuickXPlainWithTestCases, IHSLabelable):
    """
    HSLabeler for QuickXPlainWithTestCases algorithm.

    This labeler integrates QuickXPlainWithTestCases into the HSDAG framework,
    allowing it to find diagnoses by iteratively identifying conflicts that
    violate test cases.
    """

    def __init__(self, checker: ConsistencyChecker, parameters: QuickXPlainWithTestCasesParameters):
        """
        Initialize QuickXPlainWithTestCasesLabeler.

        Args:
            checker: ConsistencyChecker instance for checking consistency
            parameters: Initial parameters containing C, B, and test cases
        """
        super().__init__(checker)
        self.initial_parameters = parameters

    def get_type(self) -> LabelerType:
        """
        Get the type of this labeler.

        Returns:
            LabelerType.CONFLICT (this labeler finds conflicts)
        """
        return LabelerType.CONFLICT

    def get_initial_parameters(self) -> AbstractHSParameters:
        """
        Get the initial parameters for HSDAG root node.

        Returns:
            Initial QuickXPlainWithTestCasesParameters
        """
        return self.initial_parameters

    def get_label(self, parameters: AbstractHSParameters) -> List[List]:
        """
        Identify a conflict set (label) for the current node.

        This method is called by HSDAG to label a node with a conflict set.
        If test cases are empty, returns empty list (no conflicts).
        Otherwise, finds one conflict set using QuickXPlainWithTestCases.

        Args:
            parameters: Current node's parameters (must be QuickXPlainWithTestCasesParameters)

        Returns:
            List containing one conflict set, or empty list if no conflicts found.
            The conflict set is reversed for better HSDAG performance.
        """
        assert isinstance(parameters, QuickXPlainWithTestCasesParameters), \
            "parameter must be an instance of QuickXPlainWithTestCasesParameters"

        logging.debug('>>> QuickXPlainWithTestCasesLabeler.get_label [params=%s]', parameters)

        # If no test cases left, no conflicts possible
        if not parameters.set_tc:
            logging.debug('No test cases left - no conflicts')
            return []

        # Find conflict set
        test_case, conflict_set = self.find_conflict_set(
            parameters.set_c,
            parameters.set_b,
            parameters.set_tc,
            parameters.set_neg_tv
        )

        # Update parameters with the test case that caused the conflict
        # This will be used by child nodes
        parameters.test_case = test_case.copy()

        if conflict_set:
            # Reverse the order of the conflict set
            # This often improves HSDAG performance by exploring promising branches first
            conflict_set_reversed = list(reversed(conflict_set))
            logging.debug('<<< Found conflict: %s (reversed)', conflict_set_reversed)
            return [conflict_set_reversed]

        logging.debug('<<< No conflict found')
        return []

    def identify_new_node_parameters(self, param_parent_node: AbstractHSParameters,
                                     arc_label: Any) -> AbstractHSParameters:
        """
        Create parameters for a new child node in HSDAG.

        When HSDAG creates a child node by removing a constraint (arc_label),
        this method creates the new node's parameters.

        Args:
            param_parent_node: Parent node's parameters
            arc_label: The constraint being removed (diagnosis element)

        Returns:
            New QuickXPlainWithTestCasesParameters for the child node
        """
        assert isinstance(param_parent_node, QuickXPlainWithTestCasesParameters), \
            "parameter must be an instance of QuickXPlainWithTestCasesParameters"

        logging.debug('Creating new node parameters: removing %s', arc_label)

        # Create new C by removing arc_label
        new_c = param_parent_node.set_c.copy()
        new_c.remove(arc_label)

        # Copy B (background knowledge doesn't change)
        new_b = param_parent_node.set_b.copy()

        # Filter test cases: remove test cases before the current one
        # This prevents re-checking already satisfied test cases
        test_case = param_parent_node.test_case
        new_tc = self._copy_tc_without_testcases_before(param_parent_node.set_tc, test_case)

        return QuickXPlainWithTestCasesParameters(
            set_c=new_c,
            set_b=new_b,
            set_tc=new_tc,
            set_neg_tv=param_parent_node.set_neg_tv
        )

    def _copy_tc_without_testcases_before(self, set_tc: List,
                                          current_testcase: Optional[List]) -> List:
        """
        Copy test cases, removing those before the current test case.

        This optimization prevents re-checking test cases that have already been
        satisfied in parent nodes.

        Args:
            set_tc: Original list of test cases
            current_testcase: The test case that caused the conflict in parent node

        Returns:
            List of test cases starting from current_testcase onwards
        """
        if not current_testcase:
            return set_tc.copy()

        # Unwrap single-element list from find_conflict_set return value
        # find_conflict_set wraps integer test cases as [tc] for consistency,
        # but set_tc contains bare integers
        search_key = (current_testcase[0]
                      if isinstance(current_testcase, list) and len(current_testcase) == 1
                      else current_testcase)

        try:
            index = set_tc.index(search_key)
            # Return from current testcase onwards (including it)
            return set_tc[index:]
        except ValueError:
            # Current testcase not found in list, return all test cases
            logging.warning("Test case not found in set_tc, returning all test cases")
            return set_tc.copy()

    def get_instance(self, checker: ConsistencyChecker) -> 'IHSLabelable':
        """
        Create a new instance of this labeler with a different checker.

        This is used when HSDAG needs multiple labeler instances (e.g., for parallelization).

        Args:
            checker: New ConsistencyChecker instance

        Returns:
            New QuickXPlainWithTestCasesLabeler instance
        """
        return QuickXPlainWithTestCasesLabeler(checker, self.initial_parameters)
