import unittest

from textkit import slugify, truncate, word_count


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_punctuation_is_removed(self):
        self.assertEqual(slugify("Hello, World! It's 2026"), "hello-world-its-2026")


class TruncateTests(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(truncate("hi", 5), "hi")

    def test_total_length_respects_limit(self):
        self.assertEqual(len(truncate("abcdefghij", 6)), 6)
        self.assertEqual(truncate("abcdefghij", 6), "abc...")


class WordCountTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(word_count("a b c"), 3)

    def test_multiple_spaces_and_empty(self):
        self.assertEqual(word_count("a   b  c"), 3)
        self.assertEqual(word_count("   "), 0)


if __name__ == "__main__":
    unittest.main()
