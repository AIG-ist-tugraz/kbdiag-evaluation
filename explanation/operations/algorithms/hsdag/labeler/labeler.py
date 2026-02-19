"""
A Java version of this implementation is available at:
https://github.com/HiConfiT/hiconfit-core/tree/main/ca-cdr-package/src/main/java/at/tugraz/ist/ase/cacdr/algorithms/hs
"""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Any

from ...checker import ConsistencyChecker


class LabelerType(Enum):
    CONFLICT = 1
    DIAGNOSIS = 2


@dataclass
class AbstractHSParameters:
    set_c: List


class IHSLabelable(ABC):
    """
    Interface for the HSDAG's labeler
    """

    @abstractmethod
    def get_type(self) -> LabelerType:
        pass

    @abstractmethod
    def get_initial_parameters(self) -> AbstractHSParameters:
        pass

    @abstractmethod
    def get_label(self, parameters: AbstractHSParameters) -> List[List]:
        pass

    @abstractmethod
    def identify_new_node_parameters(self, param_parent_node: AbstractHSParameters,
                                     arc_label: Any) -> AbstractHSParameters:
        pass

    @abstractmethod
    def get_instance(self, checker: ConsistencyChecker) -> 'IHSLabelable':
        pass
