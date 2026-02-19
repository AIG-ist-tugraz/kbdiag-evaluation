#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (vietman.le@ist.tugraz.at)

from unittest import TestCase

from explanation.operations.algorithms.utils import diff, has_intersection, contains, contains_all


class TestUtils(TestCase):
    def test_diff_list_of_ints(self):
        list_x = [1, 2, 3, 4, 5]
        list_y = [1, 2]
        x_without_y = diff(list_x, list_y)

        self.assertEqual([3, 4, 5], x_without_y)

    def test_diff_list_of_list_of_ints(self):
        list_x = [[1, 2], [3, 4], [5, 6]]
        list_y = [[1, 2], [5, 6]]
        x_without_y = diff(list_x, list_y)

        self.assertEqual([[3, 4]], x_without_y)

    def test_diff_list_of_list_of_list_of_ints(self):
        list_x = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
        list_y = [[[1, 2], [3, 4]]]
        x_without_y = diff(list_x, list_y)

        self.assertEqual([[[5, 6], [7, 8]]], x_without_y)

    def test_has_intersection_true(self):
        list_x = [[1, 2], [3, 4], [5, 6]]
        list_y = [[1, 2], [5, 6]]

        self.assertEqual(True, has_intersection(list_x, list_y))

    def test_has_intersection_false(self):
        list_x = [[1, 2], [3, 4], [5, 6]]
        list_y = [[7, 8], [9, 10]]

        self.assertEqual(False, has_intersection(list_x, list_y))

    def test_contains(self):
        list_x = [[1, 2], [3, 4], [5, 6]]
        list_y = [1, 2]

        self.assertEqual(True, contains(list_x, list_y))

    def test_contains_all(self):
        list_x = [1, 2, 3, 4, 5]
        list_y = [1, 2]

        self.assertEqual(True, contains_all(list_x, list_y))

    def test_contains_all_false(self):
        list_x = [1, 2, 3, 4, 5]
        list_y = [1, 2, 6]

        self.assertEqual(False, contains_all(list_x, list_y))
        self.assertEqual([3, 4, 5], diff(list_x, list_y))