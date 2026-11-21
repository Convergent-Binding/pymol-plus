"""Fail unless the one wheel in a directory has a member containing a text.

Release CI uses it to confirm a repair step bundled a runtime library, for
example `vcomp140` (delvewheel, Windows) or
`pymol_open_source_whl.libs/libgomp` (auditwheel, Linux).

Usage: python scripts/check_wheel_member.py WHEEL_DIR TEXT
"""

import pathlib
import sys
import zipfile


def main() -> None:
  """Checks the wheel in sys.argv[1] for a member containing sys.argv[2]."""
  wheel_dir, text = pathlib.Path(sys.argv[1]), sys.argv[2]
  wheels = sorted(wheel_dir.glob("*.whl"))
  if len(wheels) != 1:
    sys.exit(f"expected one wheel in {wheel_dir}, found {len(wheels)}")
  with zipfile.ZipFile(wheels[0]) as wheel:
    matches = [name for name in wheel.namelist() if text in name]
  if not matches:
    sys.exit(f"{wheels[0].name} has no member containing {text!r}")
  print(f"{wheels[0].name}: {', '.join(matches)}")


if __name__ == "__main__":
  main()
