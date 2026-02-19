#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List

from flamapy.core.exceptions import ConfigurationNotFound
from flamapy.core.transformations import TextToModel
from flamapy.core.utils import file_exists

from explanation.models.testsuite import TestSuite, TestCase, Assignment


class TestSuiteReader(TextToModel):
    @staticmethod
    def get_source_extension() -> str:
        return 'testsuite'

    def __init__(self, path: str) -> None:
        self._path = path

    def transform(self) -> TestSuite:
        file_reader = self.get_testsuite_from_textfile(self._path)

        testcases = [
            TestCase([
                Assignment(element.lstrip('~'), not element.startswith('~'))
                for element in row
            ])
            for row in file_reader
        ]

        return TestSuite(testcases)

    def get_testsuite_from_textfile(self, path: str) -> List[List[str]]:
        # Returns a list of list of strings, where each inner list represents a test case
        if not file_exists(path):
            raise ConfigurationNotFound

        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[1:] # skip the first line

            return [
                [part.strip() for part in line.split('&')]
                for line in lines
            ]