from pathlib import Path


PATCH = "batch_projects.patches.backfill_execution_metadata"


def test_execution_metadata_backfill_is_registered():
    patches_file = Path(__file__).resolve().parents[1] / "patches.txt"
    lines = {
        line.strip()
        for line in patches_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert PATCH in lines, (
        "Historical execution metadata backfill exists but is not registered "
        "in patches.txt, so existing Automation/Workflow Run rows will never "
        "receive their intended source/attempt/timestamp normalization."
    )
