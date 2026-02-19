#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List, Tuple, Dict

from flamapy.core.exceptions import FlamaException
from flamapy.metamodels.pysat_metamodel.transformations import DimacsReader

from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.utils import negate_cnf_tseitin


class DimacsToDiagPysat(DimacsReader):

    @staticmethod
    def get_source_extension() -> str:
        return 'dimacs'

    def __init__(self, path: str, create_negation: bool = False) -> None:
        """Initialize DIMACS to DiagnosisModel transformer.

        Args:
            path: Path to DIMACS file.
            create_negation: If True, create negated forms for all constraints.
                Default is False (DIMACS files typically don't need negation).
        """
        super().__init__(path)
        self.create_negation = create_negation

    def transform(self) -> DiagnosisModel:
        with open(self.path, 'r', encoding='utf-8') as file:
            lines = file.read().splitlines()
            features_lines = [line for line in lines if line.startswith('c')]
            problem = next((line for line in lines if line.startswith('p')), None)
            clauses_lines = [line for line in lines if line and not line.startswith(('c', 'p'))]

        if problem is None:
            raise FlamaException(f'Incorrect Dimacs format of {self.path}. No problem statement.')

        problem_list = problem.split()
        n_clauses = int(problem_list[3])
        if n_clauses != len(clauses_lines):
            raise FlamaException(f'Incorrect Dimacs format of {self.path}. Inconsistent number of clauses.')

        features, variables = self._parse_features_variables(features_lines)

        model = DiagnosisModel()
        model.features = features
        model.variables = variables

        self._parse_clauses(model, clauses_lines)

        # Create negated forms if requested
        if self.create_negation:
            self._create_negated_forms(model)
        else:
            # Set next_available_id for task preparation (no Tseitin vars in DIMACS)
            model.next_available_id = len(variables) + 1

        return model

    def _create_negated_forms(self, model: DiagnosisModel) -> None:
        """Create negated forms for all constraints in constraint_map.

        Uses Tseitin transformation for multi-clause constraints.
        """
        tseitin_var = len(model.variables) + 1

        for description, clauses in model.constraint_map.items():
            negated_clauses, tseitin_var = negate_cnf_tseitin(clauses, tseitin_var)
            model.add_negated_clause_to_map(f"NOT({description})", negated_clauses)

        model.next_available_id = tseitin_var

    def _parse_features_variables(self, lines: List[str]) -> Tuple[Dict[int, str], Dict[str, int]]:
        features = {int(line.split()[1]): line.split()[2] for line in lines}
        variables = {line.split()[2]: int(line.split()[1]) for line in lines}
        return features, variables

    def _parse_clauses(self, model: DiagnosisModel, lines: List[str]) -> None:
        for line in lines:
            clause = [int(c) for c in line.split() if c != '0']
            model.add_clause(clause)
            model.add_clause_to_map(line, [clause])
