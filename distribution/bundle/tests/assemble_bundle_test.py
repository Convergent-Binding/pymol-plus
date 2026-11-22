"""assemble_bundle lays out the app from a runtime, packages and a PyMOL wheel.

The inputs are small fakes: a runtime with the Linux/macOS layout, one
package in the merged site-packages, and a wheel with two PyMOL files.
"""

import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
import zipfile

import assemble_bundle


_METADATA = (
  "Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\nLicense-Expression: MIT\n"
)
"""A distribution's METADATA, for the name filled in."""


def _write(path: pathlib.Path, text: str = "x") -> pathlib.Path:
  """Writes a text file, with its folders.

  Args:
    path: The file.
    text: Its contents.

  Returns:
    The path.
  """
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path


def _add_distribution(
  site_packages: pathlib.Path,
  name: str,
  license_text: bool,
  extra_licenses: tuple[str, ...] = (),
) -> None:
  """Installs a fake distribution: a package and its dist-info.

  Args:
    site_packages: Where it goes.
    name: Its name, also the package's.
    license_text: Whether its dist-info holds a LICENSE.
    extra_licenses: More license files, relative to the dist-info folder.
  """
  tmp_dist_info = site_packages / f"{name}-1.0.dist-info"
  _write(tmp_dist_info / "METADATA", _METADATA.format(name=name))
  tmp_record = [f"{name}/__init__.py,,", f"{tmp_dist_info.name}/METADATA,,"]
  if license_text:
    _write(tmp_dist_info / "LICENSE", "license")
    tmp_record.append(f"{tmp_dist_info.name}/LICENSE,,")
  for tmp_relative in extra_licenses:
    _write(tmp_dist_info / tmp_relative, tmp_relative)
    tmp_record.append(f"{tmp_dist_info.name}/{tmp_relative},,")
  _write(tmp_dist_info / "RECORD", "\n".join(tmp_record) + "\n")
  _write(site_packages / name / "__init__.py")


class AssembleBundleTest(unittest.TestCase):
  """Runs assemble_bundle.main on fake inputs in a temporary folder."""

  def setUp(self) -> None:
    """Writes the fake runtime, site-packages, wheel and other inputs."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.runtime = self.root / "runtime_repo"
    self.runtime_files = [
      _write(self.runtime / "bin" / "python3.13", "python"),
      _write(self.runtime / "lib" / "python3.13" / "os.py", "os"),
      # The runtime's own pip, which the app does not ship.
      _write(self.runtime / "bin" / "pip3", "pip"),
      _write(
        self.runtime
        / "lib"
        / "python3.13"
        / "site-packages"
        / "pip"
        / "__init__.py",
        "pip",
      ),
    ]
    # python-build-standalone's bin/python3 is a symlink on Linux and macOS.
    tmp_python3 = self.runtime / "bin" / "python3"
    try:
      tmp_python3.symlink_to("python3.13")
    except OSError:
      # Windows without the privilege to create symlinks
      _write(tmp_python3, "python")
    self.runtime_files.append(tmp_python3)
    self.site_packages = self.root / "merged" / "site-packages"
    _add_distribution(self.site_packages, "fakepkg", license_text=True)
    # Bytecode a test wrote into the merged tree; it records build paths.
    _write(
      self.site_packages
      / "fakepkg"
      / "__pycache__"
      / "__init__.cpython-313.pyc",
      "pyc",
    )
    self.wheel = (
      self.root / "pymol_open_source_whl-3.2.0.3-cp313-cp313-linux_x86_64.whl"
    )
    with zipfile.ZipFile(self.wheel, "w") as tmp_wheel:
      tmp_wheel.writestr("pymol/__init__.py", "pymol")
      tmp_wheel.writestr("pmg_qt/pymol_qt_gui.py", "original")
      tmp_dist_info = "pymol_open_source_whl-3.2.0.3.dist-info"
      tmp_wheel.writestr(
        f"{tmp_dist_info}/METADATA",
        _METADATA.format(name="pymol-open-source-whl"),
      )
      tmp_wheel.writestr(f"{tmp_dist_info}/LICENSE", "pymol license")
      tmp_wheel.writestr(
        f"{tmp_dist_info}/RECORD",
        f"pymol/__init__.py,,\n{tmp_dist_info}/METADATA,,\n"
        f"{tmp_dist_info}/LICENSE,,\n",
      )
    self.overlay = _write(self.root / "edited" / "pymol_qt_gui.py", "edited")
    self.launcher = _write(self.root / "PyMOL-Open-Source", "launcher")
    tmp_licenses = self.root / "licenses"
    self.license_files = {
      tmp_name: _write(tmp_licenses / tmp_name, tmp_name)
      for tmp_name in ("THIRD-PARTY-NOTICES.txt", "GPL-3.0.txt", "LGPL-3.0.txt")
    }
    self.project_license = _write(self.root / "LICENSE", "bsd")
    self.python_license = _write(
      self.root / "python_license" / "LICENSE.txt", "psf"
    )
    self.pyproject = _write(
      self.root / "pyproject.toml", '[project]\nversion = "3.2.0.3+1"\n'
    )
    self.lock = _write(self.root / "requirements_lock.txt", "fakepkg==1.0\n")
    self.status = _write(
      self.root / "stable-status.txt",
      "STABLE_GIT_SHA abc123\nSTABLE_BUILD_DATE 0\n",
    )

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _assemble(self, out: pathlib.Path, *extra: str) -> tuple[int, str]:
    """Assembles the fake inputs.

    Args:
      out: The app folder to write.
      *extra: More arguments.

    Returns:
      main's exit status and what it wrote to stderr.
    """
    tmp_argv = [
      "--out",
      str(out),
      "--runtime-root",
      str(self.runtime),
      *[
        tmp_arg
        for tmp_path in self.runtime_files
        for tmp_arg in ("--runtime-file", str(tmp_path))
      ],
      "--site-packages",
      str(self.site_packages),
      "--wheel",
      str(self.wheel),
      "--overlay",
      f"{self.overlay}=pmg_qt/pymol_qt_gui.py",
      "--launcher",
      str(self.launcher),
      *[
        tmp_arg
        for tmp_name, tmp_path in self.license_files.items()
        for tmp_arg in ("--license", f"{tmp_path}={tmp_name}")
      ],
      "--project-license",
      str(self.project_license),
      "--python-license",
      str(self.python_license),
      "--distribution",
      "pymol-open-source-whl",
      "--distribution",
      "fakepkg",
      "--pyproject",
      str(self.pyproject),
      "--lock",
      str(self.lock),
      "--status-file",
      str(self.status),
      "--target",
      "linux-x86_64",
      "--python-version",
      "3.13",
      *extra,
    ]
    tmp_stderr = io.StringIO()
    with contextlib.redirect_stderr(tmp_stderr):
      tmp_status = assemble_bundle.main(tmp_argv)
    return tmp_status, tmp_stderr.getvalue()

  def test_layout(self) -> None:
    """The launcher, runtime, packages, licenses and manifest are in place."""
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(tmp_out)

    self.assertEqual(tmp_status, 0, tmp_stderr)
    tmp_site_packages = (
      tmp_out / "runtime" / "lib" / "python3.13" / "site-packages"
    )
    for tmp_path in (
      tmp_out / "PyMOL-Open-Source",
      tmp_out / "runtime" / "bin" / "python3",
      tmp_site_packages / "fakepkg" / "__init__.py",
      tmp_site_packages / "pymol" / "__init__.py",
      tmp_out / "licenses" / "README.txt",
      tmp_out / "licenses" / "pymol-open-source-whl" / "LICENSE",
      tmp_out / "licenses" / "Python" / "LICENSE.txt",
      tmp_out / "licenses" / "PyMOL-Open-Source-setup" / "LICENSE",
      tmp_out / "manifest.json",
    ):
      self.assertTrue(tmp_path.is_file(), tmp_path)
    tmp_manifest = json.loads(
      (tmp_out / "manifest.json").read_text(encoding="utf-8")
    )
    self.assertEqual(tmp_manifest["app_version"], "3.2.0.3+1")
    self.assertEqual(tmp_manifest["git_commit"], "abc123")
    self.assertEqual(tmp_manifest["pymol_wheel"], self.wheel.name)

  def test_overlay_replaces_wheel_file(self) -> None:
    """An overlay wins over the wheel's file of the same path."""
    tmp_out = self.root / "out"

    self._assemble(tmp_out)

    tmp_gui = (
      tmp_out
      / "runtime"
      / "lib"
      / "python3.13"
      / "site-packages"
      / "pmg_qt"
      / "pymol_qt_gui.py"
    )
    self.assertEqual(tmp_gui.read_text(encoding="utf-8"), "edited")

  def test_missing_license_fails(self) -> None:
    """A bundled distribution without a license text stops the build."""
    _add_distribution(self.site_packages, "nolicense", license_text=False)
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(
      tmp_out, "--distribution", "nolicense"
    )

    self.assertNotEqual(tmp_status, 0)
    self.assertIn("nolicense", tmp_stderr)

  def test_license_files_with_same_name_kept(self) -> None:
    """License files of one name in different folders all survive.

    PEP 639 puts license files under dist-info/licenses/, keeping the
    source tree's folders; numpy ships several LICENSE.txt files there.
    """
    _add_distribution(
      self.site_packages,
      "manylicenses",
      license_text=False,
      extra_licenses=(
        "licenses/LICENSE.txt",
        "licenses/vendored/lib/LICENSE.txt",
      ),
    )
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(
      tmp_out, "--distribution", "manylicenses"
    )

    self.assertEqual(tmp_status, 0, tmp_stderr)
    tmp_licenses = tmp_out / "licenses" / "manylicenses"
    self.assertEqual(
      (tmp_licenses / "LICENSE.txt").read_text(encoding="utf-8"),
      "licenses/LICENSE.txt",
    )
    self.assertEqual(
      (tmp_licenses / "vendored" / "lib" / "LICENSE.txt").read_text(
        encoding="utf-8"
      ),
      "licenses/vendored/lib/LICENSE.txt",
    )

  def test_read_only_inputs(self) -> None:
    """Read-only inputs, as Bazel's are, still assemble."""
    for tmp_path in self.license_files.values():
      tmp_path.chmod(0o444)
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(tmp_out)

    self.assertEqual(tmp_status, 0, tmp_stderr)

  def test_manifest_is_deterministic(self) -> None:
    """Equal inputs give a byte-identical manifest.json."""
    tmp_first, tmp_second = self.root / "first", self.root / "second"

    self._assemble(tmp_first)
    self._assemble(tmp_second)

    self.assertEqual(
      (tmp_first / "manifest.json").read_bytes(),
      (tmp_second / "manifest.json").read_bytes(),
    )

  def test_bytecode_and_pip_left_out(self) -> None:
    """Neither bytecode nor the runtime's own pip reaches the app."""
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(tmp_out)

    self.assertEqual(tmp_status, 0, tmp_stderr)
    self.assertEqual(list(tmp_out.rglob("__pycache__")), [])
    self.assertEqual(list(tmp_out.rglob("*.pyc")), [])
    self.assertFalse((tmp_out / "runtime" / "bin" / "pip3").exists())
    self.assertFalse(
      (
        tmp_out / "runtime" / "lib" / "python3.13" / "site-packages" / "pip"
      ).exists()
    )

  def test_runtime_and_license_trees(self) -> None:
    """Extra runtime files and license folders land where Windows needs them.

    The C++ runtime goes beside the interpreter, its license into its own
    folder of licenses/, and a file of site-packages can be copied into the
    runtime folder too (Qt's software OpenGL beside pythonw.exe).
    """
    tmp_dlls = self.root / "msvc" / "dlls"
    _write(tmp_dlls / "msvcp140.dll", "dll")
    tmp_license = self.root / "msvc" / "license"
    _write(tmp_license / "LICENSE.txt", "eula")
    _write(self.site_packages / "PySide6" / "opengl32sw.dll", "mesa")
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(
      tmp_out,
      "--runtime-tree",
      str(tmp_dlls),
      "--license-tree",
      f"{tmp_license}=vc_redist",
      "--runtime-from-site-packages",
      "PySide6/opengl32sw.dll=opengl32sw.dll",
    )

    self.assertEqual(tmp_status, 0, tmp_stderr)
    tmp_runtime = tmp_out / "runtime"
    self.assertTrue((tmp_runtime / "msvcp140.dll").is_file())
    self.assertTrue((tmp_runtime / "opengl32sw.dll").is_file())
    tmp_vc_license = tmp_out / "licenses" / "vc_redist" / "LICENSE.txt"
    self.assertEqual(tmp_vc_license.read_text(encoding="utf-8"), "eula")

  def test_bundle_files(self) -> None:
    """Extra files land at their paths in the app folder.

    Linux: libgomp beside the runtime's libraries, libxcb-cursor beside Qt's.
    """
    tmp_gomp = _write(self.root / "gomp" / "libgomp.so.1", "gomp")
    tmp_cursor = _write(self.root / "deb" / "libxcb-cursor.so.0", "cursor")
    tmp_out = self.root / "out"

    tmp_status, tmp_stderr = self._assemble(
      tmp_out,
      "--bundle-file",
      f"{tmp_gomp}=runtime/lib/libgomp.so.1",
      "--bundle-file",
      f"{tmp_cursor}=runtime/lib/python3.13/site-packages/PySide6/Qt/lib/"
      "libxcb-cursor.so.0",
    )

    self.assertEqual(tmp_status, 0, tmp_stderr)
    self.assertEqual(
      (tmp_out / "runtime" / "lib" / "libgomp.so.1").read_text(), "gomp"
    )
    tmp_qt_lib = tmp_out / "runtime" / "lib" / "python3.13" / "site-packages"
    self.assertEqual(
      (tmp_qt_lib / "PySide6" / "Qt" / "lib" / "libxcb-cursor.so.0").read_text(),
      "cursor",
    )

  def test_missing_site_packages_file_fails(self) -> None:
    """Copying a file that site-packages lacks stops the build, naming it."""
    tmp_status, tmp_stderr = self._assemble(
      self.root / "out",
      "--runtime-from-site-packages",
      "PySide6/opengl32sw.dll=opengl32sw.dll",
    )

    self.assertNotEqual(tmp_status, 0)
    self.assertIn("PySide6/opengl32sw.dll", tmp_stderr)

  def test_no_symlinks(self) -> None:
    """The app holds no symlinks, though the runtime's bin/python3 is one."""
    tmp_out = self.root / "out"

    self._assemble(tmp_out)

    for tmp_directory, tmp_subdirectories, tmp_files in os.walk(tmp_out):
      for tmp_name in tmp_subdirectories + tmp_files:
        self.assertFalse(
          os.path.islink(os.path.join(tmp_directory, tmp_name)), tmp_name
        )


if __name__ == "__main__":
  unittest.main()
