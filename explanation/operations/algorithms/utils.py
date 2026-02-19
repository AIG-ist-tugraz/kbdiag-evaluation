#!/usr/bin/env python
"""Provides utility functions."""
#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from typing import List, Tuple


def split(clauses: List) -> Tuple[List, List]:
    """
    Splits the given list of constraints/clauses into two parts.
    clauses could be a list of integers or a list of lists.
    :param clauses: a list of clauses
    :return: a tuple of two lists
    """
    half_size = len(clauses) // 2
    return clauses[:half_size], clauses[half_size:]


def diff(list_x: List, list_y: List) -> List:
    """
    Returns the difference of two lists.
    list_x and list_y could be a list of integers or a list of lists.
    :param list_x: list
    :param list_y: list
    :return: list
    """
    return [item for item in list_x if item not in list_y]


def get_hashcode(clauses: List) -> str:
    """
    Returns the hashcode of the given CNF formula.
    :param clauses: a list of clauses
    :return: the hashcode of the given CNF formula
    """
    # clauses = sorted(clauses, key=lambda x: x[0])
    clauses = sorted(clauses)
    return str(clauses)


def has_intersection(list1: List, list2: List) -> bool:
    """
    Check if two lists have at least one common element.
    Ex: has_intersection([[1, 2], [3, 4], [5, 6]], [[1, 2], [5, 6]]) returns True
    has_intersection([[1, 2], [3, 4], [5, 6]], [[7, 8], [9, 10]]) returns False
    :param list1:
    :param list2:
    :return:
    """
    return any(i in list1 for i in list2)


def contains(list_of_lists: List[List], a_list: List) -> bool:
    """
    Check if a list of lists contains a specific list.
    Ex: contains([[1, 2], [3, 4]], [1, 2]) returns True
    """
    return any(a_list == x for x in list_of_lists)


def contains_all(greater: List, smaller: List) -> bool:
    """
    Check if a list contains all elements of another list.
    Ex: contains_all([1, 2, 3, 4, 5], [1, 2]) returns True
    :param greater:
    :param smaller:
    :return:
    """
    return all(i in greater for i in smaller)


def negate_cnf_tseitin(clauses: List[List[int]],
                       tseitin_start: int) -> Tuple[List[List[int]], int]:
    """
    Create negated form of CNF formula using Tseitin transformation.

    Original: c1 ∧ c2 ∧ ... ∧ cm
    Negated:  ¬c1 ∨ ¬c2 ∨ ... ∨ ¬cm (converted back to CNF)

    For single clause (l1 ∨ l2 ∨ ... ∨ ln):
        Negation = (¬l1) ∧ (¬l2) ∧ ... ∧ (¬ln)

    For multiple clauses, Tseitin transformation is used:
        - Create auxiliary variable ti for each ¬ci
        - ti ↔ (¬l1 ∧ ¬l2 ∧ ... ∧ ¬ln)
        - At least one ti must be true: (t1 ∨ t2 ∨ ... ∨ tm)

    Args:
        clauses: Original CNF clauses (list of lists of integers)
        tseitin_start: Starting ID for Tseitin auxiliary variables

    Returns:
        Tuple of (negated CNF clauses, next available Tseitin variable ID)
    """
    if len(clauses) == 0:
        # Empty formula - negation is unsatisfiable (represented as [[]])
        return [[]], tseitin_start

    if len(clauses) == 1:
        # Single clause: ¬(l1 ∨ l2 ∨ ... ∨ ln) = (¬l1) ∧ (¬l2) ∧ ... ∧ (¬ln)
        negated_clauses = [[-lit] for lit in clauses[0]]
        return negated_clauses, tseitin_start

    # Multi-clause: use Tseitin transformation
    # ¬(c1 ∧ c2 ∧ ... ∧ cm) = ¬c1 ∨ ¬c2 ∨ ... ∨ ¬cm
    result_clauses = []
    tseitin_vars = []
    next_tseitin_var = tseitin_start

    for clause in clauses:
        # Create Tseitin variable ti representing ¬ci
        ti = next_tseitin_var
        tseitin_vars.append(ti)
        next_tseitin_var += 1

        # ti → (¬l1 ∧ ¬l2 ∧ ... ∧ ¬ln)
        # CNF: (¬ti ∨ ¬l1) ∧ (¬ti ∨ ¬l2) ∧ ... ∧ (¬ti ∨ ¬ln)
        for lit in clause:
            result_clauses.append([-ti, -lit])

        # (¬l1 ∧ ¬l2 ∧ ... ∧ ¬ln) → ti
        # CNF: (l1 ∨ l2 ∨ ... ∨ ln ∨ ti)
        result_clauses.append(clause + [ti])

    # ¬c ↔ (t1 ∨ t2 ∨ ... ∨ tm)
    # At least one ti must be true
    result_clauses.append(tseitin_vars)

    return result_clauses, next_tseitin_var
