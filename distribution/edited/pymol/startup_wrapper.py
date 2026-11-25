import os
import sys

# System certificate files (CA bundles), in the order they are tried
CA_BUNDLE_FILEPATHS = {
  "darwin": ("/etc/ssl/cert.pem",),
  "linux": (
    "/etc/ssl/certs/ca-certificates.crt",                 # Debian, Ubuntu, Arch, Fedora
    "/etc/pki/tls/certs/ca-bundle.crt",                   # Fedora, RHEL, Rocky, Alma
    "/etc/ssl/ca-bundle.pem",                             # openSUSE
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # RHEL, CentOS
    "/etc/ssl/cert.pem",                                  # Alpine, others
  ),
}


def _use_system_ca_certificates() -> None:
  """Lets HTTPS (e.g. fetching structures from the PDB) use the system's certificates.

  The OpenSSL of the bundled Python runtime looks for certificates in paths
  of its build environment that exist on no real system, so on Linux and
  macOS every HTTPS connection fails with CERTIFICATE_VERIFY_FAILED. Windows
  uses the Windows certificate store instead.

  Nothing is changed if the user already set SSL_CERT_FILE or SSL_CERT_DIR.
  """
  if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
    return
  for tmp_filepath in CA_BUNDLE_FILEPATHS.get(sys.platform, ()):
    if os.path.isfile(tmp_filepath):
      os.environ["SSL_CERT_FILE"] = tmp_filepath
      os.environ.setdefault("REQUESTS_CA_BUNDLE", tmp_filepath)
      return


def _use_pyside6() -> None:
  """Selects PySide6 for PyMOL's Qt layer (pymol.Qt), the only Qt binding of the app.

  Overrides a QT_API the user set for another binding (e.g. pyqt5), which
  the app does not contain and pymol.Qt would then fail to import.
  """
  os.environ["QT_API"] = "pyside6"


def _use_whole_scale_on_wayland() -> None:
  """Gives the window a whole-number scale on native Wayland (e.g. 2 at 150 %).

  With fractional scaling, Qt first gives a Wayland window the screen's scale
  (2) and switches to the fractional one (1.5) after it is shown. PyMOL then
  discards the splash screen (black view), and at fractional scales it draws
  its own panel text smaller. Rounding up keeps one scale from the start; the
  compositor scales the window down sharply. X11, Windows and macOS keep
  their scales. Nothing is changed if the user set the rounding policy.
  """
  if (not sys.platform.startswith("linux") or not os.environ.get("WAYLAND_DISPLAY")
      or os.environ.get("QT_SCALE_FACTOR_ROUNDING_POLICY")):
    return
  if os.environ.get("QT_QPA_PLATFORM", "wayland").startswith("wayland"):
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "Ceil"


def _use_app_user_model_id() -> None:
  """Gives the Windows process the app's taskbar identity.

  The window belongs to the bundled pythonw.exe, so without an explicit
  AppUserModelID the taskbar shows Python's icon in a group of its own. The
  installer's shortcuts carry the same ID (setup.iss), so the running app
  joins their group and shows their icon.
  """
  if sys.platform != "win32":
    return
  import ctypes
  ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
    "io.github.kullik01.pymol-open-source"
  )


GUI_OPTIONS = {"--new-gui": "new", "--classic-gui": "classic"}
"""The app's command-line options for the GUI and the style each selects."""

GUI_VARIABLE = "PYMOL_PLUS_GUI"
"""The environment variable through which pymol3.app reads the style.

The same name as pymol3.app.ENVIRONMENT_VARIABLE; this module runs before
pymol3 may be imported.
"""

PYMOL_LONG_OPTIONS = frozenset(
  ("--version", "--help", "--retina", "--nospnav", "--gldebug", "--testing",
   "--diagnostics")
)
"""The long options PyMOL reads itself (pymol.invocation.parse_args)."""


def _take_gui_option(argv: list[str]) -> list[str]:
  """Turns --new-gui and --classic-gui into PYMOL_PLUS_GUI.

  PyMOL ends its own arguments at any other long option and hands the rest
  to a Python script, so an option left in place would cut off every
  argument after it. The last option wins, also over a PYMOL_PLUS_GUI the
  user set. Like PyMOL, the search ends at "--" or another long option
  PyMOL does not know: what follows belongs to a script.

  Args:
    argv: The command line, the program first.

  Returns:
    The command line without the two options.
  """
  tmp_arguments = list(argv[:1])
  tmp_rest = list(argv[1:])
  while tmp_rest:
    tmp_argument = tmp_rest.pop(0)
    if tmp_argument in GUI_OPTIONS:
      os.environ[GUI_VARIABLE] = GUI_OPTIONS[tmp_argument]
      continue
    tmp_arguments.append(tmp_argument)
    if (tmp_argument.startswith("--")
        and tmp_argument not in PYMOL_LONG_OPTIONS):
      tmp_arguments.extend(tmp_rest)
      break
  return tmp_arguments


if __name__ == '__main__':
  _use_app_user_model_id()
  _use_system_ca_certificates()
  _use_pyside6()
  _use_whole_scale_on_wayland()
  sys.argv[:] = _take_gui_option(sys.argv)

  import pymol  # only after the environment is set up (imports ssl)
  pymol.launch(sys.argv)
