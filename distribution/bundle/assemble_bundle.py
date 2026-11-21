"""Lays out the PyMOL-Open-Source app folder; the action tool of app_bundle.

The app is a python-build-standalone runtime with the app's packages and the
in-repo PyMOL in its site-packages, beside a native launcher:

  PyMOL-Open-Source/
    PyMOL-Open-Source[.exe]   the launcher (//distribution/launcher)
    runtime/                  CPython; site-packages in runtime/Lib (Windows)
                              or runtime/lib/python3.X (Linux, macOS)
    licenses/                 README.txt index and one folder per package
    manifest.json             what the app was built from

Every file is a real copy, never a symlink, so the folder can be moved,
archived and installed as it is.
"""

import argparse
import hashlib
import importlib.metadata
import json
import pathlib
import re
import shutil
import stat
import sys
import tomllib
import zipfile


_QT_FOR_PYTHON_LICENSES = ("LGPL-3.0.txt", "GPL-3.0.txt")
"""Qt for Python's license texts, which its wheels do not contain."""

_EXTRA_LICENSE_FILES = {
  "PySide6-Essentials": _QT_FOR_PYTHON_LICENSES,
  "shiboken6": _QT_FOR_PYTHON_LICENSES,
}
"""Distributions without a license text in their metadata: --license names."""

_EXTRA_LICENSE_PATTERNS = {"Pmw": "Pmw/Pmw_*/doc/copyright.html"}
"""Like _EXTRA_LICENSE_FILES, as globs in site-packages that survive updates."""

_LICENSE_FILENAME = re.compile(
  r"^(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE
)
"""The names of the license files a dist-info folder may hold."""

_THIRD_PARTY_NOTE = (
  "Further components (Qt, OpenSSL, system libraries): THIRD-PARTY-NOTICES.txt"
)
"""The last line of licenses/README.txt."""


class BundleError(Exception):
  """The inputs cannot make a complete app."""


def _copy(source: pathlib.Path, destination: pathlib.Path) -> None:
  """Copies a file's contents and mode, following symlinks.

  The copy stays writable to its owner: Bazel's inputs are read-only, and a
  read-only copy could be neither replaced by an overlay nor cleaned up.

  Args:
    source: The file to copy.
    destination: The copy's path; missing folders are created.
  """
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(source, destination, follow_symlinks=True)
  destination.chmod(source.stat().st_mode | stat.S_IWUSR)


def _is_bytecode(relative: pathlib.Path) -> bool:
  """Tells whether a path is compiled bytecode.

  Python writes __pycache__ wherever a test imported from, with that run's
  absolute paths in it; the app compiles its own on first use.

  Args:
    relative: A path inside the runtime or site-packages.

  Returns:
    Whether it lies in __pycache__ or is a .pyc file.
  """
  return "__pycache__" in relative.parts or relative.suffix == ".pyc"


def _is_runtime_pip(relative: pathlib.Path) -> bool:
  """Tells whether a runtime file belongs to the runtime's own pip.

  The app installs nothing at run time, and pip would be a bundled
  distribution without an entry in licenses/.

  Args:
    relative: A path inside the runtime.

  Returns:
    Whether it lies in the runtime's site-packages (which holds only pip) or
    is a pip script.
  """
  if "site-packages" in relative.parts:
    return True
  tmp_in_scripts = relative.parent.name in ("bin", "Scripts")
  return tmp_in_scripts and relative.name.startswith("pip")


def _copy_tree(source: pathlib.Path, destination: pathlib.Path) -> None:
  """Copies a folder's files, without bytecode, into another folder.

  Args:
    source: The folder to copy.
    destination: The folder the files go into, keeping their paths.
  """
  for tmp_path in sorted(source.rglob("*")):
    tmp_relative = tmp_path.relative_to(source)
    if tmp_path.is_file() and not _is_bytecode(tmp_relative):
      _copy(tmp_path, destination / tmp_relative)


def _site_packages(runtime: pathlib.Path, python_version: str) -> pathlib.Path:
  """Finds the runtime's site-packages for its layout.

  Args:
    runtime: The runtime folder in the app.
    python_version: The runtime's version, such as "3.13".

  Returns:
    runtime/Lib/site-packages beside a python.exe (Windows), otherwise
    runtime/lib/python<version>/site-packages.
  """
  if (runtime / "python.exe").is_file():
    return runtime / "Lib" / "site-packages"
  return runtime / "lib" / f"python{python_version}" / "site-packages"


def _license_path(record_path: importlib.metadata.PackagePath) -> str:
  """Gives a dist-info license file's path below the dist-info folder.

  The PEP 639 folder `licenses/` itself is left out, so the common
  `<dist-info>/licenses/LICENSE.txt` becomes `LICENSE.txt`.

  Args:
    record_path: The file's path as the distribution's RECORD lists it.

  Returns:
    The path for the distribution's folder in licenses/.
  """
  tmp_parts = record_path.parts[1:]
  if len(tmp_parts) > 1 and tmp_parts[0] == "licenses":
    tmp_parts = tmp_parts[1:]
  return "/".join(tmp_parts)


def _license_name(distribution: importlib.metadata.Distribution) -> str:
  """Gives a short license name from a distribution's metadata.

  Args:
    distribution: An installed distribution.

  Returns:
    Its License-Expression, else its license classifiers, else its License
    field, cut to one line of 80 characters, or "see license files".
  """
  tmp_metadata = distribution.metadata
  tmp_classifiers = [
    tmp_classifier.split(" :: ")[-1]
    for tmp_classifier in tmp_metadata.get_all("Classifier") or []
    if tmp_classifier.startswith("License ::")
  ]
  tmp_name = (
    tmp_metadata.get("License-Expression")
    or ", ".join(tmp_classifiers)
    or tmp_metadata.get("License")
    or ""
  ).strip()
  return tmp_name.splitlines()[0][:80] if tmp_name else "see license files"


def _normalized(name: str) -> str:
  """Normalizes a distribution name as PEP 503 does.

  Args:
    name: A distribution name, such as "PySide6_Essentials".

  Returns:
    The name in lower case with runs of "-", "_" and "." as one "-".
  """
  return re.sub(r"[-_.]+", "-", name).lower()


def _distribution_licenses(
  distribution: importlib.metadata.Distribution,
  name: str,
  site_packages: pathlib.Path,
  license_files: dict[str, pathlib.Path],
) -> list[tuple[pathlib.Path, str]]:
  """Finds a distribution's license texts.

  The dist-info files keep their folders, as several may share a name
  (numpy's LICENSE.txt).

  Args:
    distribution: The installed distribution.
    name: Its name as the bundle's distribution list gives it.
    site_packages: The site-packages it is installed in.
    license_files: The --license texts by name.

  Returns:
    Each text and its path in the distribution's folder in licenses/.
  """
  tmp_sources = [
    (pathlib.Path(distribution.locate_file(tmp_file)), _license_path(tmp_file))
    for tmp_file in distribution.files or []
    if ".dist-info" in str(tmp_file) and _LICENSE_FILENAME.match(tmp_file.name)
  ]
  tmp_sources += [
    (license_files[tmp_extra], tmp_extra)
    for tmp_extra in _EXTRA_LICENSE_FILES.get(name, ())
  ]
  if name in _EXTRA_LICENSE_PATTERNS:
    tmp_pattern = _EXTRA_LICENSE_PATTERNS[name]
    tmp_sources += [
      (tmp_path, tmp_path.name)
      for tmp_path in sorted(site_packages.glob(tmp_pattern))
    ]
  return [
    (tmp_source, tmp_target)
    for tmp_source, tmp_target in tmp_sources
    if tmp_source.is_file()
  ]


def _write_licenses(
  out: pathlib.Path,
  site_packages: pathlib.Path,
  distributions: list[str],
  license_files: dict[str, pathlib.Path],
  project_license: pathlib.Path,
  python_license: pathlib.Path,
  app_version: str,
  python_version: str,
) -> None:
  """Writes licenses/: the fixed texts, one folder per distribution, an index.

  Args:
    out: The app folder.
    site_packages: The app's site-packages.
    distributions: The bundled distributions whose licenses go in.
    license_files: The --license texts by name, copied as they are.
    project_license: This project's license.
    python_license: The runtime's license.
    app_version: The app's version.
    python_version: The runtime's version.

  Raises:
    BundleError: A bundled distribution is missing or has no license text.
  """
  tmp_licenses = out / "licenses"
  for tmp_name, tmp_path in sorted(license_files.items()):
    _copy(tmp_path, tmp_licenses / tmp_name)
  _copy(project_license, tmp_licenses / "PyMOL-Open-Source-setup" / "LICENSE")
  _copy(python_license, tmp_licenses / "Python" / "LICENSE.txt")
  tmp_index = [
    "Licenses of the components of this application",
    "",
    (
      f"PyMOL-Open-Source-setup {app_version}: BSD-3-Clause "
      "(PyMOL-Open-Source-setup/LICENSE)"
    ),
    f"Python {python_version}: PSF License (Python/LICENSE.txt)",
  ]
  tmp_installed = {
    _normalized(tmp_distribution.metadata["Name"]): tmp_distribution
    for tmp_distribution in importlib.metadata.distributions(
      path=[str(site_packages)]
    )
  }
  for tmp_name in distributions:
    tmp_distribution = tmp_installed.get(_normalized(tmp_name))
    if tmp_distribution is None:
      raise BundleError(
        f"The bundled package {tmp_name} is not in site-packages."
      )
    tmp_dist_name = tmp_distribution.metadata["Name"]
    tmp_sources = _distribution_licenses(
      tmp_distribution, tmp_name, site_packages, license_files
    )
    if not tmp_sources:
      raise BundleError(
        f"No license text found for the bundled package {tmp_dist_name}; "
        "add one to _EXTRA_LICENSE_FILES in assemble_bundle.py."
      )
    for tmp_source, tmp_target in tmp_sources:
      _copy(tmp_source, tmp_licenses / tmp_dist_name / tmp_target)
    tmp_index.append(
      f"{tmp_dist_name} {tmp_distribution.version}: "
      f"{_license_name(tmp_distribution)} ({tmp_dist_name}/)"
    )
  tmp_index += ["", _THIRD_PARTY_NOTE]
  (tmp_licenses / "README.txt").write_text(
    "\n".join(tmp_index) + "\n", encoding="utf-8"
  )


def _stable_status(path: pathlib.Path) -> dict[str, str]:
  """Reads Bazel's stable workspace status file.

  Args:
    path: The status file, one "KEY value" line per entry.

  Returns:
    The values by key.
  """
  tmp_status = {}
  for tmp_line in path.read_text(encoding="utf-8").splitlines():
    tmp_key, _, tmp_value = tmp_line.partition(" ")
    tmp_status[tmp_key] = tmp_value.strip()
  return tmp_status


def _lf_sha256(path: pathlib.Path) -> str:
  """Hashes a text file the same on every checkout.

  Args:
    path: The file.

  Returns:
    The hexadecimal SHA-256 of its bytes with CRLF line endings as LF.
  """
  return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _pairs(values: list[str]) -> list[tuple[pathlib.Path, str]]:
  """Splits SOURCE=DESTINATION arguments at their last "=".

  Args:
    values: The arguments.

  Returns:
    Each source path and destination.

  Raises:
    BundleError: An argument has no "=".
  """
  tmp_pairs = []
  for tmp_value in values:
    tmp_source, tmp_separator, tmp_destination = tmp_value.rpartition("=")
    if not tmp_separator:
      raise BundleError(f"Expected SOURCE=DESTINATION, got {tmp_value}")
    tmp_pairs.append((pathlib.Path(tmp_source), tmp_destination))
  return tmp_pairs


def assemble(args: argparse.Namespace) -> None:
  """Writes the app folder described by the parsed arguments.

  Args:
    args: The command line, as main() parses it.

  Raises:
    BundleError: The inputs cannot make a complete app.
  """
  tmp_out = pathlib.Path(args.out)
  if tmp_out.exists():
    shutil.rmtree(tmp_out)
  tmp_runtime_root = pathlib.Path(args.runtime_root)
  tmp_runtime = tmp_out / "runtime"
  for tmp_path in args.runtime_file:
    tmp_relative = pathlib.Path(tmp_path).relative_to(tmp_runtime_root)
    if not _is_bytecode(tmp_relative) and not _is_runtime_pip(tmp_relative):
      _copy(pathlib.Path(tmp_path), tmp_runtime / tmp_relative)

  tmp_site_packages = _site_packages(tmp_runtime, args.python_version)
  tmp_merged = pathlib.Path(args.site_packages)
  if not any(tmp_merged.iterdir()):
    raise BundleError(f"The merged site-packages {tmp_merged} is empty.")
  _copy_tree(tmp_merged, tmp_site_packages)
  with zipfile.ZipFile(args.wheel) as tmp_wheel:
    tmp_wheel.extractall(tmp_site_packages)
  for tmp_source, tmp_destination in _pairs(args.overlay):
    _copy(tmp_source, tmp_site_packages / tmp_destination)

  tmp_launcher = pathlib.Path(args.launcher)
  _copy(tmp_launcher, tmp_out / tmp_launcher.name)

  with open(args.pyproject, "rb") as tmp_handle:
    tmp_app_version = tomllib.load(tmp_handle)["project"]["version"]
  _write_licenses(
    tmp_out,
    tmp_site_packages,
    args.distribution,
    {
      tmp_destination: tmp_source
      for tmp_source, tmp_destination in _pairs(args.license)
    },
    pathlib.Path(args.project_license),
    pathlib.Path(args.python_license),
    tmp_app_version,
    args.python_version,
  )

  tmp_status = _stable_status(pathlib.Path(args.status_file))
  tmp_manifest = {
    "app_version": tmp_app_version,
    "git_commit": tmp_status.get("STABLE_GIT_SHA", "unknown"),
    "pymol_wheel": pathlib.Path(args.wheel).name,
    "python_version": args.python_version,
    "requirements_lock_sha256": _lf_sha256(pathlib.Path(args.lock)),
    "target": args.target,
  }
  (tmp_out / "manifest.json").write_text(
    json.dumps(tmp_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
  )


def main(argv: list[str]) -> int:
  """Assembles the app from the command line.

  Args:
    argv: The arguments after the program name; `@file` reads them from a
      parameter file.

  Returns:
    0 on success, 1 with a message on stderr when the inputs cannot make a
    complete app.
  """
  tmp_parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
  tmp_parser.add_argument("--out", required=True)
  tmp_parser.add_argument("--runtime-root", required=True)
  tmp_parser.add_argument("--runtime-file", action="append", default=[])
  tmp_parser.add_argument("--site-packages", required=True)
  tmp_parser.add_argument("--wheel", required=True)
  tmp_parser.add_argument(
    "--overlay", action="append", default=[], help="SOURCE=site-packages path"
  )
  tmp_parser.add_argument("--launcher", required=True)
  tmp_parser.add_argument(
    "--license", action="append", default=[], help="SOURCE=licenses/ name"
  )
  tmp_parser.add_argument("--project-license", required=True)
  tmp_parser.add_argument(
    "--python-license", required=True, help="the runtime's LICENSE.txt"
  )
  tmp_parser.add_argument("--distribution", action="append", default=[])
  tmp_parser.add_argument("--pyproject", required=True)
  tmp_parser.add_argument("--lock", required=True)
  tmp_parser.add_argument("--status-file", required=True)
  tmp_parser.add_argument("--target", required=True)
  tmp_parser.add_argument("--python-version", required=True)
  try:
    assemble(tmp_parser.parse_args(argv))
  except BundleError as exception:
    print(f"assemble_bundle: {exception}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
