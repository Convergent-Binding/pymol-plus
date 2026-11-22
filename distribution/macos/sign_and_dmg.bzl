"""The signed macOS app and its DMG, built with Apple's own tools.

Both rules run local, uncached actions: `codesign` and `hdiutil` (through
create-dmg) are programs of the Mac that builds, outside Bazel's inputs.
The DMG carries its release name,
PyMOL-Open-Source_v<version>_macOS_<AppleSilicon|Intel>.dmg.
"""

load("@app_project_metadata//:metadata.bzl", "VERSION")

_LOCAL = {
    "local": "1",
    "no-cache": "1",
}

def _macos_signed_app_impl(ctx):
    out = ctx.actions.declare_directory(ctx.label.name + "/PyMOL-Open-Source.app")
    args = ctx.actions.args()
    args.add("--app", ctx.file.app.path)
    args.add("--out", out.path)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.app],
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "CodesignApp",
        progress_message = "Signing %{output} ad hoc",
        execution_requirements = _LOCAL,
    )
    return [DefaultInfo(files = depset([out]))]

macos_signed_app = rule(
    implementation = _macos_signed_app_impl,
    attrs = {
        "app": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The unsigned app, //distribution/macos:app.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/macos:sign_app"),
            executable = True,
            cfg = "exec",
        ),
    },
)

def _macos_dmg_impl(ctx):
    out = ctx.actions.declare_file(
        "PyMOL-Open-Source_v{}_macOS_{}.dmg".format(VERSION, ctx.attr.label_name),
    )
    args = ctx.actions.args()
    args.add("--app", ctx.file.app.path)
    args.add("--create-dmg", ctx.file.create_dmg)
    args.add("--background", ctx.file.background)
    args.add("--label", ctx.attr.label_name)
    args.add("--out", out)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.app, ctx.file.background] + ctx.files.create_dmg_files,
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "CreateDmg",
        progress_message = "Writing %{output}",
        execution_requirements = _LOCAL,
    )
    return [DefaultInfo(files = depset([out]))]

macos_dmg = rule(
    implementation = _macos_dmg_impl,
    attrs = {
        "app": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The signed app, //distribution/macos:signed_app.",
        ),
        "background": attr.label(allow_single_file = True, mandatory = True),
        "create_dmg": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "create-dmg's script, @create_dmg//:create-dmg.",
        ),
        "create_dmg_files": attr.label_list(
            allow_files = True,
            doc = "create-dmg's support files, which it reads beside itself.",
        ),
        "label_name": attr.string(
            mandatory = True,
            values = ["AppleSilicon", "Intel"],
            doc = "The architecture label of the DMG's name.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/macos:make_dmg"),
            executable = True,
            cfg = "exec",
        ),
    },
)
