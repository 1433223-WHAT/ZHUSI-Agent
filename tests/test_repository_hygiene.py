from pathlib import Path
from fnmatch import fnmatch
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SECRET_TOKEN_RE = re.compile(r"(?:sk|dataset)-[A-Za-z0-9_-]{20,}")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".html", ".js"}
SKIP_DIRS = {".git", "__pycache__", "_backup_20260819_design_output", "output", "downloads"}
SKIP_FILES = {"_test_callai_*.py"}


class RepositoryHygieneTests(unittest.TestCase):
    def test_source_files_do_not_contain_hardcoded_service_tokens(self):
        offenders = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.name == ".env" or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                continue
            if any(fnmatch(path.name, pattern) for pattern in SKIP_FILES):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if SECRET_TOKEN_RE.search(text):
                offenders.append(str(path.relative_to(ROOT)))

        self.assertEqual([], offenders, f"hardcoded service tokens: {offenders}")

    def test_gitignore_excludes_secrets_logs_caches_backups_and_user_outputs(self):
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8-sig").splitlines()
        required = {
            ".env",
            "*.key",
            "*.log",
            "*.py[cod]",
            "__pycache__/",
            "_backup_*/",
            "output/",
            "downloads/",
            "server_check.*",
            "_test_callai_*.py",
        }
        self.assertTrue(required.issubset(set(patterns)), sorted(required - set(patterns)))


if __name__ == "__main__":
    unittest.main()
