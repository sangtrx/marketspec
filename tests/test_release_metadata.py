from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTest(unittest.TestCase):
    def project(self):
        with (ROOT / "pyproject.toml").open("rb") as handle:
            return tomllib.load(handle)["project"]

    def test_version_and_runtime_version_match(self):
        project = self.project()
        init_text = (ROOT / "src/marketspec/__init__.py").read_text()
        match = re.search(r'^__version__\s*=\s*"([^"]+)"$', init_text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(project["version"], match.group(1))
        self.assertRegex(project["version"], r"^0\.\d+\.\d+$")

    def test_license_and_discoverability_metadata_are_explicit(self):
        project = self.project()
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["license-files"], ["LICENSE"])
        self.assertTrue((ROOT / "LICENSE").is_file())

        urls = project["urls"]
        self.assertEqual(urls["Repository"], "https://github.com/sangtrx/marketspec")
        self.assertEqual(urls["Issues"], "https://github.com/sangtrx/marketspec/issues")
        self.assertTrue(urls["Changelog"].endswith("/CHANGELOG.md"))

        keywords = set(project["keywords"])
        self.assertTrue({"prediction-markets", "event-contracts", "settlement", "deterministic"} <= keywords)

    def test_release_docs_exist(self):
        changelog = (ROOT / "CHANGELOG.md").read_text()
        releasing = (ROOT / "docs/RELEASING.md").read_text()
        self.assertIn("## [Unreleased]", changelog)
        self.assertIn("exact verified candidate SHA", releasing)
        self.assertIn("PyPI availability", releasing)


if __name__ == "__main__":
    unittest.main()
