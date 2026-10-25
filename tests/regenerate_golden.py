"""Regenerate the golden report snapshots.

Run from the repository root:

    PYTHONPATH=src python tests/regenerate_golden.py

Review the resulting diff before committing. The fixture lives in
``tests/test_golden_reports.py`` so the generator and the test cannot disagree about it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_golden_reports import GOLDEN, FORMATS, normalise, render_format  # noqa: E402


def main() -> int:
    """Write one snapshot per format.

    Returns:
        int: 0 on success.
    """
    GOLDEN.mkdir(exist_ok=True)
    for fmt in FORMATS:
        target = GOLDEN / f"{fmt}.txt"
        text = normalise(render_format(fmt))
        target.write_bytes(text.encode("utf-8"))
        print(f"wrote {target} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
