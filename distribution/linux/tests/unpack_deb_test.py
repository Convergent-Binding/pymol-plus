"""unpack_deb extracts one file from a .deb package, following its links.

The fixture .deb is built here: an `ar` archive with debian-binary,
control.tar.xz and data.tar.xz, whose data holds a library and the usual
.so.0 link to it.
"""

import contextlib
import io
import pathlib
import tarfile
import tempfile
import unittest

import unpack_deb


def _ar_member(name: str, data: bytes) -> bytes:
  """Builds one member of an `ar` archive.

  Args:
    name: The member's name.
    data: Its bytes.

  Returns:
    The 60-byte header, the data and the padding to an even length.
  """
  tmp_header = (
    f"{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n".encode()
  )
  return tmp_header + data + (b"\n" if len(data) % 2 else b"")


def _tar_xz(members: dict[str, bytes], links: dict[str, str]) -> bytes:
  """Builds an xz-compressed tar archive.

  Args:
    members: File paths and their bytes.
    links: Symbolic link paths and their targets.

  Returns:
    The archive's bytes.
  """
  tmp_buffer = io.BytesIO()
  with tarfile.open(fileobj=tmp_buffer, mode="w:xz") as tmp_tar:
    for tmp_name, tmp_data in members.items():
      tmp_member = tarfile.TarInfo(tmp_name)
      tmp_member.size = len(tmp_data)
      tmp_tar.addfile(tmp_member, io.BytesIO(tmp_data))
    for tmp_name, tmp_target in links.items():
      tmp_member = tarfile.TarInfo(tmp_name)
      tmp_member.type = tarfile.SYMTYPE
      tmp_member.linkname = tmp_target
      tmp_tar.addfile(tmp_member)
  return tmp_buffer.getvalue()


class UnpackDebTest(unittest.TestCase):
  """Extracts from a fixture .deb in a temporary folder."""

  def setUp(self) -> None:
    """Writes the fixture .deb."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    tmp_lib = "./usr/lib/x86_64-linux-gnu/"
    tmp_data = _tar_xz(
      {tmp_lib + "libxcb-cursor.so.0.0.0": b"library"},
      {tmp_lib + "libxcb-cursor.so.0": "libxcb-cursor.so.0.0.0"},
    )
    self.deb = self.root / "libxcb-cursor0.deb"
    self.deb.write_bytes(
      b"!<arch>\n"
      + _ar_member("debian-binary", b"2.0\n")
      + _ar_member("control.tar.xz", _tar_xz({"./control": b"x"}, {}))
      + _ar_member("data.tar.xz", tmp_data)
    )

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def test_member_extracted(self) -> None:
    """A link in the package gives the file it points to."""
    tmp_out = self.root / "libxcb-cursor.so.0"

    tmp_status = unpack_deb.main(
      [
        "--deb",
        str(self.deb),
        "--member",
        "usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0",
        "--out",
        str(tmp_out),
      ]
    )

    self.assertEqual(tmp_status, 0)
    self.assertEqual(tmp_out.read_bytes(), b"library")

  def test_missing_member_fails(self) -> None:
    """A path the package lacks fails, naming it."""
    tmp_stderr = io.StringIO()
    with contextlib.redirect_stderr(tmp_stderr):
      tmp_status = unpack_deb.main(
        [
          "--deb",
          str(self.deb),
          "--member",
          "usr/lib/missing.so",
          "--out",
          str(self.root / "missing.so"),
        ]
      )

    self.assertNotEqual(tmp_status, 0)
    self.assertIn("usr/lib/missing.so", tmp_stderr.getvalue())


if __name__ == "__main__":
  unittest.main()
