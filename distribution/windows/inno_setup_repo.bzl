"""inno_setup: Inno Setup 7's compiler on this machine, as @inno_setup.

A local repository rule that finds ISCC.exe where Inno Setup 7 installs it
(for all users, 64- and 32-bit, or per user), then on PATH. Bazel does not
fetch Inno Setup, whose installer documents no portable mode; CI installs a
pinned copy. `@inno_setup//:defs.bzl` holds ISCC_PATH, the absolute path
of ISCC.exe, or "" where it is missing, so such a machine can still load
//distribution/windows. The path is used in place: ISCC loads its compiler
DLLs and its `compiler:` files from its own folder, which a link or copy
of ISCC.exe elsewhere would not have.
"""

_INSTALL_FOLDERS = [
    "C:/Program Files/Inno Setup 7",
    "C:/Program Files (x86)/Inno Setup 7",
]

def _inno_setup_impl(rctx):
    candidates = [folder + "/ISCC.exe" for folder in _INSTALL_FOLDERS]
    local_app_data = rctx.getenv("LOCALAPPDATA")
    if local_app_data:
        candidates.append(local_app_data.replace("\\", "/") + "/Programs/Inno Setup 7/ISCC.exe")
    found = None
    for candidate in candidates:
        if rctx.path(candidate).exists:
            found = rctx.path(candidate)
            break
    if found == None:
        found = rctx.which("ISCC")
    rctx.file("BUILD.bazel", "")
    rctx.file("defs.bzl", 'ISCC_PATH = "{}"\n'.format(str(found).replace("\\", "/") if found else ""))

inno_setup = repository_rule(
    implementation = _inno_setup_impl,
    environ = ["LOCALAPPDATA", "PATH"],
    local = True,
)
