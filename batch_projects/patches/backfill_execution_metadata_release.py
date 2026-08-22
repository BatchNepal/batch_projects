"""Final release-fence normalization for execution-source metadata.

The older ``backfill_execution_metadata`` patch is idempotent, but some
pre-release sites already logged that patch identity before all activity/audit
write paths enforced a nonblank source. Those sites can therefore accumulate
new blank-source rows that Frappe will never revisit under the old patch name.

Use a fresh one-time identity for the release and delegate to the original,
conservative backfill implementation. It only fills blank/derivable metadata
and does not fabricate correlation or execution IDs.
"""

from batch_projects.patches.backfill_execution_metadata import execute as _backfill


def execute():
    _backfill()
