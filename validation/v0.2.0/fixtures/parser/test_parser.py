import unittest
from parser_demo import parse

class TestParser(unittest.TestCase):
    def test_valid_addition(self):
        self.assertEqual(parse('1+2'), 3)

    def test_rejects_trailing_operator(self):
        with self.assertRaises(ValueError):
            parse('1+')

if __name__ == '__main__':
    unittest.main()
