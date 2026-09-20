import unittest

import marketspec
from marketspec.cli import build_parser


class BootstrapTest(unittest.TestCase):
    def test_version_and_cli_import(self) -> None:
        self.assertEqual(marketspec.__version__, "0.1.0")
        self.assertEqual(build_parser().prog, "marketspec")


if __name__ == "__main__":
    unittest.main()
