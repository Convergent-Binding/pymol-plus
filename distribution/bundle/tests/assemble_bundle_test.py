"""assemble_bundle lays out the app from a runtime, packages and the PyMOL wheel.

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


_METADATA = "Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\nLicense-Expression: MIT\n"


def _write(path: pathlib.Path, text: str = "x") -> pathlib.Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path


def _add_distribution(
    site_packages: pathlib.Path, name: str, license_text: bool, extra_licenses: tuple[str, ...] = ()
) -> None:
  dist_info = site_packages / f"{name}-1.0.dist-info"
  _write(dist_info / "METADATA", _METADATA.format(name=name))
  record = [f"{name}/__init__.py,,", f"{dist_info.name}/METADATA,,"]
  if license_text:
    _write(dist_info / "LICENSE", "license")
    record.append(f"{dist_info.name}/LICENSE,,")
  for relative in extra_licenses:
    _write(dist_info / relative, relative)
    record.append(f"{dist_info.name}/{relative},,")
  _write(dist_info / "RECORD", "\n".join(record) + "\n")
  _write(site_packages / name / "__init__.py")


class AssembleBundleTest(unittest.TestCase):

  def setUp(self) -> None:
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    self.runtime = self.root / "runtime_repo"
    self.runtime_files = [
        _write(self.runtime / "bin" / "python3", "python"),
        _write(self.runtime / "lib" / "python3.13" / "os.py", "os"),
    ]
    self.site_packages = self.root / "merged" / "site-packages"
    _add_distribution(self.site_packages, "fakepkg", license_text=True)
    self.wheel = self.root / "pymol_open_source_whl-3.2.0.3-cp313-cp313-linux_x86_64.whl"
    with zipfile.ZipFile(self.wheel, "w") as wheel:
      wheel.writestr("pymol/__init__.py", "pymol")
      wheel.writestr("pmg_qt/pymol_qt_gui.py", "original")
      dist_info = "pymol_open_source_whl-3.2.0.3.dist-info"
      wheel.writestr(f"{dist_info}/METADATA", _METADATA.format(name="pymol-open-source-whl"))
      wheel.writestr(f"{dist_info}/LICENSE", "pymol license")
      wheel.writestr(
          f"{dist_info}/RECORD",
          f"pymol/__init__.py,,\n{dist_info}/METADATA,,\n{dist_info}/LICENSE,,\n",
      )
    self.overlay = _write(self.root / "edited" / "pymol_qt_gui.py", "edited")
    self.launcher = _write(self.root / "PyMOL-Open-Source", "launcher")
    licenses = self.root / "licenses"
    self.license_files = {
        name: _write(licenses / name, name)
        for name in ("THIRD-PARTY-NOTICES.txt", "GPL-3.0.txt", "LGPL-3.0.txt")
    }
    self.project_license = _write(self.root / "LICENSE", "bsd")
    self.python_license = _write(self.root / "python_license" / "LICENSE.txt", "psf")
    self.pyproject = _write(self.root / "pyproject.toml", '[project]\nversion = "3.2.0.3+1"\n')
    self.lock = _write(self.root / "requirements_lock.txt", "fakepkg==1.0\n")
    self.status = _write(self.root / "stable-status.txt", "STABLE_GIT_SHA abc123\nSTABLE_BUILD_DATE 0\n")

  def tearDown(self) -> None:
    self._dir.cleanup()

  def _assemble(self, out: pathlib.Path, *extra: str) -> tuple[int, str]:
    argv = [
        "--out", str(out),
        "--runtime-root", str(self.runtime),
        *[arg for path in self.runtime_files for arg in ("--runtime-file", str(path))],
        "--site-packages", str(self.site_packages),
        "--wheel", str(self.wheel),
        "--overlay", f"{self.overlay}=pmg_qt/pymol_qt_gui.py",
        "--launcher", str(self.launcher),
        *[arg for name, path in self.license_files.items() for arg in ("--license", f"{path}={name}")],
        "--project-license", str(self.project_license),
        "--python-license", str(self.python_license),
        "--distribution", "pymol-open-source-whl",
        "--distribution", "fakepkg",
        "--pyproject", str(self.pyproject),
        "--lock", str(self.lock),
        "--status-file", str(self.status),
        "--target", "linux-x86_64",
        "--python-version", "3.13",
        *extra,
    ]
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
      status = assemble_bundle.main(argv)
    return status, stderr.getvalue()

  def test_layout(self) -> None:
    out = self.root / "out"

    status, stderr = self._assemble(out)

    self.assertEqual(status, 0, stderr)
    site_packages = out / "runtime" / "lib" / "python3.13" / "site-packages"
    for path in (
        out / "PyMOL-Open-Source",
        out / "runtime" / "bin" / "python3",
        site_packages / "fakepkg" / "__init__.py",
        site_packages / "pymol" / "__init__.py",
        out / "licenses" / "README.txt",
        out / "licenses" / "pymol-open-source-whl" / "LICENSE",
        out / "licenses" / "Python" / "LICENSE.txt",
        out / "licenses" / "PyMOL-Open-Source-setup" / "LICENSE",
        out / "manifest.json",
    ):
      self.assertTrue(path.is_file(), path)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    self.assertEqual(manifest["app_version"], "3.2.0.3+1")
    self.assertEqual(manifest["git_commit"], "abc123")
    self.assertEqual(manifest["pymol_wheel"], self.wheel.name)

  def test_overlay_replaces_wheel_file(self) -> None:
    out = self.root / "out"

    self._assemble(out)

    gui = out / "runtime" / "lib" / "python3.13" / "site-packages" / "pmg_qt" / "pymol_qt_gui.py"
    self.assertEqual(gui.read_text(encoding="utf-8"), "edited")

  def test_missing_license_fails(self) -> None:
    _add_distribution(self.site_packages, "nolicense", license_text=False)
    out = self.root / "out"

    status, stderr = self._assemble(out, "--distribution", "nolicense")

    self.assertNotEqual(status, 0)
    self.assertIn("nolicense", stderr)

  def test_license_files_with_same_name_kept(self) -> None:
    # PEP 639 puts license files under dist-info/licenses/, keeping the
    # source tree's folders; numpy ships several LICENSE.txt files there.
    _add_distribution(
        self.site_packages,
        "manylicenses",
        license_text=False,
        extra_licenses=("licenses/LICENSE.txt", "licenses/vendored/lib/LICENSE.txt"),
    )
    out = self.root / "out"

    status, stderr = self._assemble(out, "--distribution", "manylicenses")

    self.assertEqual(status, 0, stderr)
    licenses = out / "licenses" / "manylicenses"
    self.assertEqual((licenses / "LICENSE.txt").read_text(encoding="utf-8"), "licenses/LICENSE.txt")
    self.assertEqual(
        (licenses / "vendored" / "lib" / "LICENSE.txt").read_text(encoding="utf-8"),
        "licenses/vendored/lib/LICENSE.txt",
    )

  def test_read_only_inputs(self) -> None:
    # Bazel's inputs are read-only; the copies must stay writable to Bazel.
    for path in self.license_files.values():
      path.chmod(0o444)
    out = self.root / "out"

    status, stderr = self._assemble(out)

    self.assertEqual(status, 0, stderr)

  def test_manifest_is_deterministic(self) -> None:
    first, second = self.root / "first", self.root / "second"

    self._assemble(first)
    self._assemble(second)

    self.assertEqual(
        (first / "manifest.json").read_bytes(), (second / "manifest.json").read_bytes()
    )

  def test_no_symlinks(self) -> None:
    out = self.root / "out"

    self._assemble(out)

    for directory, subdirectories, files in os.walk(out):
      for name in subdirectories + files:
        self.assertFalse(os.path.islink(os.path.join(directory, name)), name)


if __name__ == "__main__":
  unittest.main()
