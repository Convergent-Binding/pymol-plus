"""Lays out the PyMOL-Open-Source app folder; the action tool of app_bundle.bzl.

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

# Distributions whose metadata contains no license text, and where it is.
# The Qt for Python texts are among the --license files; Pmw's is a pattern
# relative to its installed package, so a Pmw update keeps working.
_QT_FOR_PYTHON_LICENSES = ("LGPL-3.0.txt", "GPL-3.0.txt")
_EXTRA_LICENSE_FILES = {
    "PySide6-Essentials": _QT_FOR_PYTHON_LICENSES,
    "shiboken6": _QT_FOR_PYTHON_LICENSES,
}
_EXTRA_LICENSE_PATTERNS = {"Pmw": "Pmw/Pmw_*/doc/copyright.html"}
_LICENSE_FILENAME = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)


class BundleError(Exception):
  """The inputs cannot make a complete app."""


def _copy(source: pathlib.Path, destination: pathlib.Path) -> None:
  """Copies a file's contents and mode, following symlinks.

  The copy stays writable to its owner: Bazel's inputs are read-only, and a
  read-only copy could be neither replaced by an overlay nor cleaned up.
  """
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(source, destination, follow_symlinks=True)
  destination.chmod(source.stat().st_mode | stat.S_IWUSR)


def _copy_tree(source: pathlib.Path, destination: pathlib.Path) -> None:
  for path in sorted(source.rglob("*")):
    if path.is_file():
      _copy(path, destination / path.relative_to(source))


def _site_packages(runtime: pathlib.Path, python_version: str) -> pathlib.Path:
  """Returns the runtime's site-packages for its layout."""
  if (runtime / "python.exe").is_file():
    return runtime / "Lib" / "site-packages"
  return runtime / "lib" / f"python{python_version}" / "site-packages"


def _license_path(record_path: importlib.metadata.PackagePath) -> str:
  """Returns a dist-info license file's path below the dist-info folder.

  The PEP 639 folder `licenses/` itself is left out, so the common
  `<dist-info>/licenses/LICENSE.txt` becomes `LICENSE.txt`.
  """
  parts = record_path.parts[1:]
  if len(parts) > 1 and parts[0] == "licenses":
    parts = parts[1:]
  return "/".join(parts)


def _license_name(distribution: importlib.metadata.Distribution) -> str:
  """Returns a short license name from a distribution's metadata."""
  metadata = distribution.metadata
  classifiers = [
      classifier.split(" :: ")[-1]
      for classifier in metadata.get_all("Classifier") or []
      if classifier.startswith("License ::")
  ]
  name = (
      metadata.get("License-Expression") or ", ".join(classifiers) or metadata.get("License") or ""
  ).strip()
  return name.splitlines()[0][:80] if name else "see license files"


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

  Raises:
    BundleError: A bundled distribution has no license text.
  """
  licenses = out / "licenses"
  for name, path in sorted(license_files.items()):
    _copy(path, licenses / name)
  _copy(project_license, licenses / "PyMOL-Open-Source-setup" / "LICENSE")
  _copy(python_license, licenses / "Python" / "LICENSE.txt")
  index = [
      "Licenses of the components of this application",
      "",
      f"PyMOL-Open-Source-setup {app_version}: BSD-3-Clause (PyMOL-Open-Source-setup/LICENSE)",
      f"Python {python_version}: PSF License (Python/LICENSE.txt)",
  ]
  installed = {
      re.sub(r"[-_.]+", "-", d.metadata["Name"]).lower(): d
      for d in importlib.metadata.distributions(path=[str(site_packages)])
  }
  for name in distributions:
    distribution = installed.get(re.sub(r"[-_.]+", "-", name).lower())
    if distribution is None:
      raise BundleError(f"The bundled package {name} is not in site-packages.")
    dist_name = distribution.metadata["Name"]
    # (source, path in the distribution's licenses folder); dist-info files
    # keep their folders, as several may share a name (numpy's LICENSE.txt).
    sources = [
        (pathlib.Path(distribution.locate_file(f)), _license_path(f))
        for f in distribution.files or []
        if ".dist-info" in str(f) and _LICENSE_FILENAME.match(f.name)
    ]
    sources += [
        (license_files[extra], extra) for extra in _EXTRA_LICENSE_FILES.get(name, ())
    ]
    if name in _EXTRA_LICENSE_PATTERNS:
      sources += [
          (path, path.name) for path in sorted(site_packages.glob(_EXTRA_LICENSE_PATTERNS[name]))
      ]
    sources = [(source, target) for source, target in sources if source.is_file()]
    if not sources:
      raise BundleError(
          f"No license text found for the bundled package {dist_name}; "
          "add one to _EXTRA_LICENSE_FILES in assemble_bundle.py."
      )
    for source, target in sources:
      _copy(source, licenses / dist_name / target)
    index.append(
        f"{dist_name} {distribution.version}: {_license_name(distribution)} ({dist_name}/)"
    )
  index += ["", "Further components (Qt, OpenSSL, system libraries): THIRD-PARTY-NOTICES.txt"]
  (licenses / "README.txt").write_text("\n".join(index) + "\n", encoding="utf-8")


def _stable_status(path: pathlib.Path) -> dict[str, str]:
  status = {}
  for line in path.read_text(encoding="utf-8").splitlines():
    key, _, value = line.partition(" ")
    status[key] = value.strip()
  return status


def _lf_sha256(path: pathlib.Path) -> str:
  """SHA-256 with LF line endings, the same on every checkout."""
  return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _pairs(values: list[str]) -> list[tuple[pathlib.Path, str]]:
  """Splits SOURCE=DESTINATION arguments."""
  pairs = []
  for value in values:
    source, separator, destination = value.rpartition("=")
    if not separator:
      raise BundleError(f"Expected SOURCE=DESTINATION, got {value}")
    pairs.append((pathlib.Path(source), destination))
  return pairs


def assemble(args: argparse.Namespace) -> None:
  """Writes the app folder described by the parsed arguments.

  Raises:
    BundleError: The inputs cannot make a complete app.
  """
  out = pathlib.Path(args.out)
  if out.exists():
    shutil.rmtree(out)
  runtime_root = pathlib.Path(args.runtime_root)
  runtime = out / "runtime"
  for path in args.runtime_file:
    path = pathlib.Path(path)
    _copy(path, runtime / path.relative_to(runtime_root))

  site_packages = _site_packages(runtime, args.python_version)
  merged = pathlib.Path(args.site_packages)
  if not any(merged.iterdir()):
    raise BundleError(f"The merged site-packages {merged} is empty.")
  _copy_tree(merged, site_packages)
  with zipfile.ZipFile(args.wheel) as wheel:
    wheel.extractall(site_packages)
  for source, destination in _pairs(args.overlay):
    _copy(source, site_packages / destination)

  launcher = pathlib.Path(args.launcher)
  _copy(launcher, out / launcher.name)

  with open(args.pyproject, "rb") as handle:
    app_version = tomllib.load(handle)["project"]["version"]
  _write_licenses(
      out,
      site_packages,
      args.distribution,
      {destination: source for source, destination in _pairs(args.license)},
      pathlib.Path(args.project_license),
      pathlib.Path(args.python_license),
      app_version,
      args.python_version,
  )

  manifest = {
      "app_version": app_version,
      "git_commit": _stable_status(pathlib.Path(args.status_file)).get("STABLE_GIT_SHA", "unknown"),
      "pymol_wheel": pathlib.Path(args.wheel).name,
      "python_version": args.python_version,
      "requirements_lock_sha256": _lf_sha256(pathlib.Path(args.lock)),
      "target": args.target,
  }
  (out / "manifest.json").write_text(
      json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
  )


def main(argv: list[str]) -> int:
  """Assembles the app; returns 0, or 1 with a message on stderr."""
  parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
  parser.add_argument("--out", required=True)
  parser.add_argument("--runtime-root", required=True)
  parser.add_argument("--runtime-file", action="append", default=[])
  parser.add_argument("--site-packages", required=True)
  parser.add_argument("--wheel", required=True)
  parser.add_argument("--overlay", action="append", default=[], help="SOURCE=site-packages path")
  parser.add_argument("--launcher", required=True)
  parser.add_argument("--license", action="append", default=[], help="SOURCE=licenses/ name")
  parser.add_argument("--project-license", required=True)
  parser.add_argument("--python-license", required=True, help="the runtime's LICENSE.txt")
  parser.add_argument("--distribution", action="append", default=[])
  parser.add_argument("--pyproject", required=True)
  parser.add_argument("--lock", required=True)
  parser.add_argument("--status-file", required=True)
  parser.add_argument("--target", required=True)
  parser.add_argument("--python-version", required=True)
  try:
    assemble(parser.parse_args(argv))
  except BundleError as error:
    print(f"assemble_bundle: {error}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
