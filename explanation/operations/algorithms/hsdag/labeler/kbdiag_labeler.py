#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from dataclasses import dataclass
from typing import List

from .labeler import IHSLabelable, LabelerType, AbstractHSParameters
from ...checker import ConsistencyChecker
from ...kbdiag import KBDiag


@dataclass
class KBDiagParameters(AbstractHSParameters):
    set_b: List
    set_tc: List
    set_neg_tv: List

    set_tcp: List = None

    def __str__(self) -> str:
        return (f"KBDiagParameters{{C={self.set_c}, "
                f"B={self.set_b},"
                f"TC={self.set_tc},"
                f"TV={self.set_neg_tv},"
                f"TCP={self.set_tcp}}}")


class KBDiagLabeler(KBDiag, IHSLabelable):
    """
    HSLabeler for KBDiag algorithm
    """

    def __init__(self, checker: ConsistencyChecker, m: int, parameters: KBDiagParameters):
        super().__init__(checker, m)
        self.initial_parameters = parameters

    def get_type(self) -> LabelerType:
        return LabelerType.DIAGNOSIS

    def get_initial_parameters(self) -> AbstractHSParameters:
        return self.initial_parameters

    def get_label(self, parameters: AbstractHSParameters) -> List[List]:
        """
        Identifies a diagnosis
        """
        assert isinstance(parameters, KBDiagParameters), \
            "parameter must be an instance of KBDiagParameters"
        # assert len(parameters.set_tc) > 0, "set of test cases must not be empty"

        if len(parameters.set_tc) >= 1 \
                and len(parameters.set_c) > 1 \
                and (len(parameters.set_b) == 0
                     or len(self.checker.is_consistent_test_cases(parameters.set_b, parameters.set_tc, True)) == 0):

            set_tcp, diag = self.find_diagnosis(parameters.set_c, parameters.set_b, parameters.set_tc,
                                                parameters.set_neg_tv)

            # update the parameters, which will be used by the children's nodes
            # set_tcp
            parameters.set_tcp = set_tcp.copy()

            if len(diag) != 0:
                return [diag]
        return []

    def identify_new_node_parameters(self, param_parent_node: AbstractHSParameters,
                                     arc_label: int) -> AbstractHSParameters:
        """
        Identifies the new node's parameters on the basis of the parent node's parameters.
        """
        assert isinstance(param_parent_node, KBDiagParameters),\
            "parameter must be an instance of KBDiagParameters"

        new_c = param_parent_node.set_c.copy()
        new_c.remove(arc_label)
        new_b = param_parent_node.set_b.copy()
        new_b.append(arc_label)

        if param_parent_node.set_tcp is None:
            new_tc = []
        else:
            new_tc = param_parent_node.set_tcp.copy()

        return KBDiagParameters(new_c, new_b, new_tc, param_parent_node.set_neg_tv)

    def get_instance(self, checker: ConsistencyChecker) -> IHSLabelable:
        return KBDiagLabeler(checker, self.m, self.initial_parameters)
