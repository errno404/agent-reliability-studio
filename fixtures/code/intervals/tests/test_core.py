import unittest

from intervals import merge


class MergeTests(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(merge([(1, 3), (2, 5)]), [(1, 5)])

    def test_touching_closed_intervals_merge(self):
        self.assertEqual(merge([(1, 3), (3, 4)]), [(1, 4)])

    def test_disjoint(self):
        self.assertEqual(merge([(5, 6), (1, 2)]), [(1, 2), (5, 6)])


if __name__ == "__main__":
    unittest.main()
