"""The Windows app ships every C++ and OpenMP runtime DLL its binaries import.

A PC without the VC++ Redistributable finds these DLLs only in the folder of
the process (runtime/, beside pythonw.exe) or beside the importing file. The
CI runners have the Redistributable installed, so the smoke test cannot
catch a missing one; this test reads every binary's import table instead.
"""

import pathlib
import sys
import unittest

import pe_imports


_BUNDLE = pathlib.Path(sys.argv[1]).resolve()
"""The built app folder."""

_BINARY_SUFFIXES = {".dll", ".exe", ".pyd"}
"""The files whose import tables are read."""


class MsvcRuntimeTest(unittest.TestCase):
  """Checks the bundle's runtime DLLs, their license and the OpenGL fallback."""

  def test_every_imported_runtime_dll_is_shipped(self) -> None:
    """Each imported runtime DLL is in runtime/ or beside its importer."""
    tmp_runtime = _BUNDLE / "runtime"
    tmp_missing = []
    for tmp_binary in sorted(_BUNDLE.rglob("*")):
      if tmp_binary.suffix.lower() not in _BINARY_SUFFIXES:
        continue
      for tmp_name in pe_imports.imported_dlls(tmp_binary):
        if not pe_imports.RUNTIME_DLL.match(tmp_name):
          continue
        tmp_shipped = (tmp_runtime / tmp_name).exists() or (
          tmp_binary.parent / tmp_name
        ).exists()
        if not tmp_shipped:
          tmp_importer = tmp_binary.relative_to(_BUNDLE).as_posix()
          tmp_missing.append(f"{tmp_name} (imported by {tmp_importer})")

    self.assertEqual(tmp_missing, [])

  def test_runtime_license_shipped(self) -> None:
    """The VC++ runtime's license is in licenses/vc_redist/."""
    for tmp_name in ("LICENSE.txt", "LICENSE.RTF"):
      with self.subTest(name=tmp_name):
        tmp_license = _BUNDLE / "licenses" / "vc_redist" / tmp_name
        self.assertTrue(tmp_license.is_file())

  def test_software_opengl_beside_pythonw(self) -> None:
    """Qt's software OpenGL sits where pythonw.exe loads opengl32.dll from."""
    self.assertTrue((_BUNDLE / "runtime" / "opengl32sw.dll").is_file())


if __name__ == "__main__":
  unittest.main(argv=sys.argv[:1])
