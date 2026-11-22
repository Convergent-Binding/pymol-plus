"""inno_setup: Inno Setup 7's compiler on this machine, as @inno_setup.

A local repository rule that finds ISCC.exe where Inno Setup 7 installs it
(for all users, 64- and 32-bit, or per user), then on PATH. Bazel does not
fetch Inno Setup, whose installer documents no portable mode; CI installs a
pinned copy. `@inno_setup//:defs.bzl` says whether it was found, so a
machine without it can still load //distribution/windows.
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
    if found == None:
        rctx.file("BUILD.bazel", "")
        rctx.file("defs.bzl", "ISCC_FOUND = False\n")
        return
    rctx.symlink(found, "ISCC.exe")
    rctx.file("BUILD.bazel", 'exports_files(["ISCC.exe"], visibility = ["//visibility:public"])\n')
    rctx.file("defs.bzl", "ISCC_FOUND = True\n")

inno_setup = repository_rule(
    implementation = _inno_setup_impl,
    environ = ["LOCALAPPDATA", "PATH"],
    local = True,
)
