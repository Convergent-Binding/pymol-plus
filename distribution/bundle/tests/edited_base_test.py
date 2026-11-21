"""The app's overlays still match the in-repo PyMOL they were made from.

distribution/edited/ holds copies of PyMOL files with marked edits
("BEGIN EDITED CODE SEGMENT"), which replace the originals in the app bundle.
distribution/edited/upstream.sha256 records the SHA-256 of each original in
modules/ at the time the copy was made (with LF line endings), so a change to an original fails here
instead of being overwritten silently in the app.
"""

import hashlib
import pathlib
import unittest


_EDITED = pathlib.Path("distribution/edited")
_MODULES = pathlib.Path("modules")


def _sha256(path: pathlib.Path) -> str:
  """Returns the SHA-256 of a text file with LF line endings.

  A Windows checkout with core.autocrlf has CRLF where Linux has LF; the hash
  must not depend on the checkout.
  """
  return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _recorded() -> dict[str, str]:
  """Returns the modules/ path and SHA-256 of each recorded original."""
  hashes = {}
  for line in (_EDITED / "upstream.sha256").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
      digest, path = line.split(maxsplit=1)
      hashes[path.lstrip("*")] = digest
  return hashes


class EditedBaseTest(unittest.TestCase):

  def test_listed_files_unchanged(self) -> None:
    for path, digest in _recorded().items():
      with self.subTest(path=path):
        actual = _sha256(_MODULES / path)
        self.assertEqual(
            actual,
            digest,
            f"modules/{path} changed since distribution/edited/{path} was made "
            "from it. Port the 'BEGIN EDITED CODE SEGMENT' blocks into a new "
            f"copy of modules/{path}, then record its SHA-256 in "
            "distribution/edited/upstream.sha256.",
        )

  def test_every_edited_copy_listed(self) -> None:
    recorded = _recorded()
    for copy in sorted((_EDITED / "pmg_qt").glob("*.py")):
      path = copy.relative_to(_EDITED).as_posix()
      with self.subTest(path=path):
        self.assertIn(path, recorded, f"{path} has no line in upstream.sha256")


if __name__ == "__main__":
  unittest.main()
