#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import Iterator, Any

from flamapy.core.models import VariabilityModel


class Assignment(VariabilityModel):

    @staticmethod
    def get_extension() -> str:
        return 'assignment'

    def __init__(self, feature: str, value: bool) -> None:
        self.feature = feature
        self.value = value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Assignment):
            return self.feature == other.feature
        return False

    def __hash__(self) -> int:
        return hash(self.feature)

    def __str__(self) -> str:
        return ' = '.join([self.feature, str(self.value)])

    def __repr__(self) -> str:
        return f"Assignment({self.feature}, {self.value})"


class TestCase(VariabilityModel):
    """
    A test case is an ordered list of assignments
    """

    # isViolated: bool = False

    @staticmethod
    def get_extension() -> str:
        return 'testcase'

    def __init__(self, assignments: list[Assignment]) -> None:
        self.assignments = assignments

    # def get_selected_elements(self) -> list[Any]:
    #     return [e for e in self.assignments if self.assignments[e]]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TestCase):
            return self.assignments == other.assignments
        return False

    def __hash__(self) -> int:
        return hash(frozenset(self.assignments))

    def __str__(self) -> str:
        return ', '.join([str(e) for e in self.assignments])

    def __repr__(self) -> str:
        return f"TestCase({self.assignments})"

    def __iter__(self) -> Iterator[Any]:
        return iter(self.assignments)


class TestSuite(VariabilityModel):

    @staticmethod
    def get_extension() -> str:
        return 'testsuite'

    def __init__(self, testcases: list[TestCase]) -> None:
        self.testcases = testcases

    # def get_selected_elements(self) -> list[Any]:
    #     return [e for e in self.examples if self.examples[e]]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TestSuite):
            return self.testcases == other.testcases
        return False

    def __hash__(self) -> int:
        return hash(frozenset(self.testcases))

    def __str__(self) -> str:
        return ', '.join([str(e) for e in self.testcases])

    def __repr__(self) -> str:
        return f"TestSuite({self.testcases})"

    def __iter__(self) -> Iterator[Any]:
        return iter(self.testcases)