#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import Any

from flamapy.metamodels.fm_metamodel.models.feature_model import (
    FeatureModel,
    Constraint,
    Feature,
    Relation,
)
from flamapy.metamodels.pysat_metamodel.transformations.fm_to_pysat import FmToPysat

from explanation.models.pysat_diagnosis_model import DiagnosisModel
from explanation.operations.algorithms.utils import negate_cnf_tseitin


class FmToDiagPysat(FmToPysat):
    @staticmethod
    def get_source_extension() -> str:
        return 'fm'

    @staticmethod
    def get_destination_extension() -> str:
        return 'pysat_diagnosis'

    def __init__(self, source_model: FeatureModel, create_negation: bool = True) -> None:
        """Initialize feature model to DiagnosisModel transformer.

        Args:
            source_model: FeatureModel to transform.
            create_negation: If True, create negated forms for all constraints
                (needed for redundancy detection). Default is True for backward compatibility.
        """
        super().__init__(source_model)
        self.destination_model = DiagnosisModel()
        self.create_negation = create_negation

    def add_root(self, feature: Feature) -> None:
        var = self.destination_model.variables.get(feature.name)
        if var is None:
            raise KeyError(f'Feature {feature.name} not found in the model')

        self.destination_model.add_clause([var])
        self.destination_model.add_clause_to_map(str(feature), [[var]])

    def add_relation(self, relation: Relation) -> None:
        if relation.is_mandatory():
            clauses = self._add_mandatory_relation(relation)
        elif relation.is_optional():
            clauses = self._add_optional_relation(relation)
        elif relation.is_or():
            clauses = self._add_or_relation(relation)
        elif relation.is_alternative():
            clauses = self._add_alternative_relation(relation)
        else:
            clauses = self._add_constraint_relation(relation)
        self._store_constraint_clauses(clauses)
        self.destination_model.add_clause_to_map(str(relation), clauses)

    def add_constraint(self, ctc: Constraint) -> None:
        def get_term_variable(term: Any) -> int:
            negated = False
            if term.startswith('-'):
                term = term[1:]
                negated = True

            var = self.destination_model.get_variable(term)

            if negated:
                return -var
            return var

        ctc_clauses = []
        clauses = ctc.ast.get_clauses()
        for clause in clauses:
            clause_variables = list(map(get_term_variable, clause))
            ctc_clauses.append(clause_variables)
            self.destination_model.add_clause(clause_variables)

        self.destination_model.add_clause_to_map(str(ctc), ctc_clauses)

    def transform(self) -> DiagnosisModel:
        """Transform feature model to DiagnosisModel.

        This override calls the parent transform and optionally creates negated forms
        for all constraints using Tseitin transformation (if create_negation=True).
        """
        # Call parent transform to create variables and clauses
        super().transform()

        # Create negated forms for all constraints if requested
        if self.create_negation:
            self._create_negated_forms()
        else:
            # Set next_available_id for task preparation
            self.destination_model.next_available_id = len(self.destination_model.variables) + 1

        return self.destination_model

    def _create_negated_forms(self) -> None:
        """Create negated forms for all constraints in constraint_map.

        Uses Tseitin transformation for multi-clause constraints.
        Negated forms are stored in negated_constraint_map.
        """
        # Start Tseitin variables after all feature variables
        tseitin_var = len(self.destination_model.variables) + 1

        for description, clauses in self.destination_model.constraint_map.items():
            negated_clauses, tseitin_var = negate_cnf_tseitin(clauses, tseitin_var)
            self.destination_model.add_negated_clause_to_map(
                f"NOT({description})", negated_clauses)

        # Store next available Tseitin var for TaskPreparation
        self.destination_model.next_available_id = tseitin_var