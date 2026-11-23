"""The Windows packages' rules: the portable ZIP and the Inno Setup installer.

Both write their file under the release name, which carries the app's
version from distribution/pyproject.toml (@app_project_metadata).
"""

load("@app_project_metadata//:metadata.bzl", "VERSION")

def _portable_zip_impl(ctx):
    out = ctx.actions.declare_file(
        "PyMOL-Open-Source_v{}_x64_portable.zip".format(VERSION),
    )
    args = ctx.actions.args()
    args.add("--folder", ctx.file.app.path)
    args.add("--out", out)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.app],
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "PortableZip",
        progress_message = "Writing the portable ZIP %{output}",
    )
    return [DefaultInfo(files = depset([out]))]

portable_zip = rule(
    implementation = _portable_zip_impl,
    attrs = {
        "app": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The app folder, //distribution/bundle.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/windows:make_zip"),
            executable = True,
            cfg = "exec",
        ),
    },
)

def _inno_setup_installer_impl(ctx):
    if not ctx.attr.iscc_path:
        fail("Inno Setup 7 (ISCC.exe) was not found. Install it from " +
             "https://jrsoftware.org/isdl.php and build again.")
    out = ctx.actions.declare_file(
        "PyMOL-Open-Source_v{}_x64_setup.exe".format(VERSION),
    )
    args = ctx.actions.args()
    args.add("--iscc", ctx.attr.iscc_path)
    args.add("--script", ctx.file.script)
    args.add("--app", ctx.file.app.path)
    args.add("--version", VERSION)
    args.add("--out", out)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.script, ctx.file.app] + ctx.files.script_files,
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "InnoSetup",
        progress_message = "Compiling the installer %{output}",
        # ISCC is a program of this machine, run from its install folder,
        # outside Bazel's inputs.
        execution_requirements = {
            "local": "1",
            "no-cache": "1",
        },
    )
    return [DefaultInfo(files = depset([out]))]

inno_setup_installer = rule(
    implementation = _inno_setup_installer_impl,
    attrs = {
        "app": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The app folder, //distribution/bundle.",
        ),
        "iscc_path": attr.string(
            doc = "ISCC.exe's absolute path (@inno_setup); empty where Inno " +
                  "Setup is missing.",
        ),
        "script": attr.label(allow_single_file = [".iss"], mandatory = True),
        "script_files": attr.label_list(
            allow_files = True,
            doc = "The files setup.iss reads, relative to its folder.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/windows:run_iscc"),
            executable = True,
            cfg = "exec",
        ),
    },
)
