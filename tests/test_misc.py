import re
from pathlib import Path

import pymmcore_widgets

ISINSTANCE_RE = re.compile(r"isinstance\s*\(\s*[^,]+,\s*CMMCore", re.MULTILINE)


def test_no_direct_isinstance() -> None:
    # grep the entire codebase for `isinstance(obj, CMMCorePlus)`
    # and ensure that it is not used directly.
    ROOT = Path(pymmcore_widgets.__file__).parent
    for path in ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if match := ISINSTANCE_RE.search(content):
            line_no = content.count("\n", 0, match.start()) + 1
            raise AssertionError(
                f"Direct isinstance check for CMMCore[Plus] found in {path} at line "
                f"{line_no}.\n Use structural checks instead... or open an issue to "
                "discuss."
            )
