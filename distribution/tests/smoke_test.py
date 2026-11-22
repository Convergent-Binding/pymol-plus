"""Smoke test for a frozen PyMOL-Open-Source application.

Run it with the frozen executable, use tests/run_smoke_test.sh:
  headless:          tests/run_smoke_test.sh <executable>
  with the Qt GUI:   tests/run_smoke_test.sh --gui <executable>   (needs a display, e.g. Xvfb)

With PYMOL_SMOKE_TEST_ONLINE=1 it also downloads a structure from the PDB (HTTPS).
Note: the certificate check fails if only SSL_CERT_DIR is set (lazily loaded).

Prints "SMOKE TEST OK" on success, otherwise exits with status 1.
"""
import ctypes
import faulthandler
import os
import pathlib
import ssl
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request


# On a crash (e.g. in the OpenGL driver) print the Python stacks of all threads.
# Enable it before importing PyMOL, which replaces sys.stderr with an object without fileno().
try:
  faulthandler.enable(file=sys.__stderr__)
except (AttributeError, ValueError, OSError):
  pass  # no usable stderr (e.g. a GUI executable without console)

import pymol
from pymol import cmd


def check_bundled_modules_and_data() -> None:
  # Modules that must be bundled explicitly or are loaded dynamically
  import ssl  # noqa: F401
  import uuid  # noqa: F401

  import Bio  # noqa: F401  (used by pymol.seqalign)
  import pymol.parser
  import pymol.povray
  import pymol.vfont
  import pymol.wizard.mutagenesis  # noqa: F401

  for tmp_path in ("data/startup", "data/pymol/splash.png", "data/pymol/icons/alt_logo.png"):
    tmp_full_path = os.path.join(os.environ["PYMOL_PATH"], tmp_path)
    assert os.path.exists(tmp_full_path), f"missing {tmp_full_path}"


def check_licenses() -> None:
  """The license texts must be shipped with the app.

  The Bazel-built app keeps them in the folder its launcher sets as
  PYMOL_APP_ROOT; the cx_Freeze app next to the executable (macOS: in
  Resources).
  """
  tmp_app_root = os.environ.get("PYMOL_APP_ROOT")
  tmp_exe_dir = pathlib.Path(os.path.realpath(sys.executable)).parent
  if tmp_app_root:
    tmp_candidates = (pathlib.Path(tmp_app_root) / "licenses",)
  else:
    tmp_candidates = (
      tmp_exe_dir / "licenses",
      tmp_exe_dir.parent / "Resources" / "licenses",
    )
  tmp_licenses_dir = next(
    (tmp_dir for tmp_dir in tmp_candidates if tmp_dir.is_dir()), None
  )
  tmp_where = tmp_candidates[0].parent
  assert tmp_licenses_dir is not None, f"licenses folder missing in {tmp_where}"
  for tmp_name in ("README.txt", "THIRD-PARTY-NOTICES.txt", "pymol-open-source-whl/LICENSE",
                   "LGPL-3.0.txt", "PySide6_Essentials/LGPL-3.0.txt", "Python/LICENSE.txt"):
    tmp_text = tmp_licenses_dir / tmp_name
    assert tmp_text.is_file(), f"license file missing: {tmp_name}"
  # The Windows app bundles the Microsoft C++ runtime with its license: the
  # Bazel-built app in licenses/, the cx_Freeze app in share/licenses/.
  if sys.platform == "win32":
    if tmp_app_root:
      tmp_vc_redist = tmp_licenses_dir / "vc_redist"
    else:
      tmp_vc_redist = tmp_exe_dir / "share" / "licenses" / "vc_redist"
    assert tmp_vc_redist.is_dir(), "license of the C++ runtime missing"


APP_USER_MODEL_ID = "io.github.kullik01.pymol-open-source"
"""The app's identity on the Windows taskbar, also its shortcuts'."""


def check_macos_bundle_executable() -> None:
  """Inside the macOS app the process is the bundle's own executable.

  The launcher runs Python in its own process there, so macOS shows the
  app with its name and icon; a process of runtime/bin/python3 would show
  as Python.
  """
  tmp_app_root = os.environ.get("PYMOL_APP_ROOT", "")
  tmp_in_bundle = tmp_app_root.endswith("/Contents/Resources")
  if sys.platform != "darwin" or not tmp_in_bundle:
    return
  tmp_executable = os.path.realpath(sys.executable)
  assert tmp_executable.endswith("/Contents/MacOS/PyMOL-Open-Source"), (
    f"the process runs {tmp_executable}"
  )


def check_macos_python_settings() -> None:
  """The macOS launcher runs Python in UTF-8 mode, bytecode outside the app.

  The app starts from the Finder without LANG, where Python would otherwise
  read files as ASCII; bytecode written into the signed app would break its
  signature.
  """
  if sys.platform != "darwin" or not os.environ.get("PYMOL_APP_ROOT"):
    return
  assert sys.flags.utf8_mode == 1, "Python runs without UTF-8 mode"
  tmp_prefix = sys.pycache_prefix or ""
  assert tmp_prefix.endswith("/Library/Caches/PyMOL-Open-Source/pycache"), (
    f"bytecode goes to {tmp_prefix!r}"
  )


def check_linux_settings() -> None:
  """On Linux bytecode goes to the user's cache, OpenMP comes from the app.

  The packages install into /opt, where users cannot write bytecode, and a
  minimal system has no libgomp, which _cmd needs.
  """
  tmp_app_root = os.environ.get("PYMOL_APP_ROOT")
  if not sys.platform.startswith("linux") or not tmp_app_root:
    return
  tmp_prefix = sys.pycache_prefix or ""
  assert tmp_prefix.endswith("/PyMOL-Open-Source/pycache"), (
    f"bytecode goes to {tmp_prefix!r}"
  )
  with open("/proc/self/maps", encoding="utf-8") as tmp_maps:
    tmp_gomp = {
      tmp_line.split()[-1]
      for tmp_line in tmp_maps
      if tmp_line.rstrip().endswith("/libgomp.so.1")
    }
  tmp_root = os.path.realpath(tmp_app_root)
  assert tmp_gomp and all(
    os.path.realpath(tmp_path).startswith(tmp_root) for tmp_path in tmp_gomp
  ), f"libgomp loaded from {tmp_gomp}"


def check_app_user_model_id() -> None:
  """The Windows process carries the app's AppUserModelID.

  The window belongs to pythonw.exe; without the ID the taskbar shows
  Python's icon in a group of its own instead of the pinned shortcut's.
  """
  if sys.platform != "win32":
    return
  tmp_id = ctypes.c_wchar_p()
  tmp_result = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID(
    ctypes.byref(tmp_id)
  )
  assert tmp_result == 0, f"no AppUserModelID set (HRESULT {tmp_result:#x})"
  tmp_value = tmp_id.value
  ctypes.windll.ole32.CoTaskMemFree(tmp_id)
  assert tmp_value == APP_USER_MODEL_ID, f"AppUserModelID is {tmp_value}"


def check_certificates() -> None:
  """HTTPS needs CA certificates: on Windows from the Windows store, otherwise from the file
  that startup_wrapper.py sets as SSL_CERT_FILE."""
  tmp_count = ssl.create_default_context().cert_store_stats()["x509_ca"]
  assert tmp_count > 0, f"no CA certificates loaded (SSL_CERT_FILE={os.environ.get('SSL_CERT_FILE')})"


def check_online(a_tmp_dir: str) -> bool:
  """Downloads a structure from the PDB. Returns False if the online check is switched off."""
  if os.environ.get("PYMOL_SMOKE_TEST_ONLINE") != "1":
    return False
  # cmd.fetch reports every error the same way, so check the HTTPS connection first:
  # a certificate error fails at once, network problems get retried
  for tmp_attempt in range(1, 4):
    try:
      with urllib.request.urlopen("https://files.rcsb.org/header/1UBQ.cif", timeout=30) as tmp_response:
        tmp_response.read(64)
      break
    except OSError as tmp_error:
      # URLError wraps the cause in "reason"; timeouts and resets while
      # reading arrive unwrapped
      tmp_reason = getattr(tmp_error, "reason", tmp_error)
      if isinstance(tmp_reason, ssl.SSLCertVerificationError) or tmp_attempt == 3:
        raise
      time.sleep(10)
  cmd.fetch("1ubq", path=a_tmp_dir, type="cif", quiet=1)
  assert cmd.count_atoms("1ubq") > 0, "fetch 1ubq loaded no atoms"
  return True


def check_commands(a_tmp_dir: str) -> None:
  cmd.fragment("ala")
  assert cmd.count_atoms() == 10, cmd.count_atoms()
  cmd.wizard("mutagenesis")
  cmd.set_wizard()
  tmp_png = os.path.join(a_tmp_dir, "ray.png")
  cmd.png(tmp_png, width=200, height=150, ray=1)
  assert os.path.getsize(tmp_png) > 1000, "ray-traced image is empty"


def check_gui(a_tmp_dir: str) -> str:
  """Checks the Qt GUI and OpenGL rendering. Returns a description of the mode."""
  if pymol.invocation.options.no_gui:
    return "headless"
  from pymol.Qt import PYQT_NAME, QtWidgets, utils
  tmp_app = QtWidgets.QApplication.instance()
  assert tmp_app is not None, "Qt GUI is not running"
  assert not tmp_app.windowIcon().isNull(), "window icon is missing"
  tmp_png = os.path.join(a_tmp_dir, "opengl.png")
  cmd.png(tmp_png, width=200, height=150, ray=0)
  assert os.path.getsize(tmp_png) > 1000, "OpenGL rendered image is empty"
  # PyMOL's dialogs are .ui forms, loaded like in pmg_qt/pymol_qt_gui.py
  import pmg_qt.pymol_qt_gui
  tmp_form = os.path.join(os.path.dirname(pmg_qt.pymol_qt_gui.__file__), "forms", "fetch.ui")
  tmp_widget = QtWidgets.QWidget()
  assert utils.loadUi(tmp_form, tmp_widget) is not None, "loading a .ui form failed"
  return f"GUI, {PYQT_NAME}, Qt platform {tmp_app.platformName()}"


try:
  check_bundled_modules_and_data()
  check_licenses()
  check_app_user_model_id()
  check_macos_bundle_executable()
  check_macos_python_settings()
  check_linux_settings()
  check_certificates()
  with tempfile.TemporaryDirectory() as tmp_dir:
    check_commands(tmp_dir)
    tmp_mode = check_gui(tmp_dir)
    if check_online(tmp_dir):
      tmp_mode += ", online"
except Exception:  # noqa: BLE001  (every failure must print the FAILED marker)
  traceback.print_exc()
  print("SMOKE TEST FAILED", flush=True)
  cmd.quit(1)
else:
  print(
    f"SMOKE TEST OK ({tmp_mode}, PyMOL {cmd.get_version()[0]}, Python {sys.version.split()[0]})",
    flush=True,
  )
  cmd.quit(0)
