"""The app's overlays still match the in-repo PyMOL they were made from.

distribution/edited/ holds copies of PyMOL files with marked edits
("BEGIN EDITED CODE SEGMENT"), which replace the originals in the app bundle.
distribution/edited/upstream.sha256 records the SHA-256 of each original in
modules/ at the time the copy was made (with LF line endings), so a change
to an original fails here instead of being overwritten silently in the app.
"""

import hashlib
import pathlib
import unittest


_EDITED = pathlib.Path("distribution/edited")
"""The edited copies, relative to the runfiles root the test runs in."""

_MODULES = pathlib.Path("modules")
"""The in-repo PyMOL sources the copies were made from."""


def _sha256(path: pathlib.Path) -> str:
  """Hashes a text file the same on every checkout.

  A Windows checkout with core.autocrlf has CRLF where Linux has LF.

  Args:
    path: The file.

  Returns:
    The hexadecimal SHA-256 of its bytes with CRLF line endings as LF.
  """
  return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _recorded() -> dict[str, str]:
  """Reads upstream.sha256.

  Returns:
    The SHA-256 of each recorded original by its path below modules/.
  """
  tmp_hashes = {}
  for tmp_line in (
    (_EDITED / "upstream.sha256").read_text(encoding="utf-8").splitlines()
  ):
    if tmp_line.strip() and not tmp_line.startswith("#"):
      tmp_digest, tmp_path = tmp_line.split(maxsplit=1)
      tmp_hashes[tmp_path.lstrip("*")] = tmp_digest
  return tmp_hashes


class EditedBaseTest(unittest.TestCase):
  """Compares upstream.sha256 with modules/ and with the edited copies."""

  def test_listed_files_unchanged(self) -> None:
    """Every recorded original still has its recorded SHA-256."""
    for tmp_path, tmp_digest in _recorded().items():
      with self.subTest(path=tmp_path):
        tmp_actual = _sha256(_MODULES / tmp_path)
        self.assertEqual(
          tmp_actual,
          tmp_digest,
          f"modules/{tmp_path} changed since distribution/edited/{tmp_path} "
          "was made from it. Port the 'BEGIN EDITED CODE SEGMENT' blocks into "
          f"a new copy of modules/{tmp_path}, then record its SHA-256 in "
          "distribution/edited/upstream.sha256.",
        )

  def test_every_edited_copy_listed(self) -> None:
    """Every edited copy of an upstream file has a recorded original."""
    tmp_recorded = _recorded()
    for tmp_copy in sorted((_EDITED / "pmg_qt").glob("*.py")):
      tmp_path = tmp_copy.relative_to(_EDITED).as_posix()
      with self.subTest(path=tmp_path):
        self.assertIn(
          tmp_path, tmp_recorded, f"{tmp_path} has no line in upstream.sha256"
        )


if __name__ == "__main__":
  unittest.main()
