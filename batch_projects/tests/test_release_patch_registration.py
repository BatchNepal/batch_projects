import unittest
from pathlib import Path


PATCH = "batch_projects.patches.backfill_execution_metadata_release"


class TestReleasePatchRegistration(unittest.TestCase):
    def test_execution_metadata_release_backfill_is_registered(self):
        patches_file = Path(__file__).resolve().parents[1] / "patches.txt"
        lines = {
            line.strip()
            for line in patches_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn(
            PATCH,
            lines,
            "The final execution-metadata release backfill must use a fresh "
            "patch identity so pre-release sites that already logged the older "
            "backfill still normalize rows created afterward.",
        )
