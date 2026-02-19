#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List, Dict

from flamapy.core.exceptions import ConfigurationNotFound, FlamaException
from flamapy.core.utils import file_exists
from flamapy.metamodels.configuration_metamodel.transformations import ConfigurationBasicReader


class DimacsToConfiguration(ConfigurationBasicReader):
    @staticmethod
    def get_source_extension() -> str:
        return 'dimacs'

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.features: Dict[int, str] = {}
        self.variables: Dict[str, int] = {}

    def get_configuration_from_csv(self, path: str) -> List[List[str]]:
        # Returns a list of list
        if not file_exists(path):
            raise ConfigurationNotFound

        with open(self._path, 'r', encoding='utf-8') as file:
            lines = file.read().splitlines()
            features_lines = [line for line in lines if line.startswith('c')]
            problem = next((line for line in lines if line.startswith('p')), None)
            clauses_lines = [line for line in lines if line and not line.startswith(('c', 'p'))]

        if problem is None:
            raise FlamaException(f'Incorrect Dimacs format of {self._path}. No problem statement.')

        self._parse_features_variables(features_lines)

        return self._parse_clauses(clauses_lines)

    def _parse_features_variables(self, lines: List[str]) -> None:
        for line in lines:
            items = line.split()
            var = int(items[1])
            feature = items[2]

            self.features[var] = feature
            self.variables[feature] = var

    def _parse_clauses(self, lines: List[str]) -> List[List[str]]:
        csvreader = []
        for line in lines:
            clause = [c for c in line.split() if c != '0']

            if len(clause) != 1:
                raise FlamaException(f'Incorrect Dimacs format of {self._path}. '
                                     f'Incorrect clause format.')
            else:
                literal = clause[0]
                row = [self.features[int(literal[1:])], 'false'] if literal[0] == '-' \
                    else [self.features[int(literal)], 'true']
                csvreader.append(row)

        return csvreader