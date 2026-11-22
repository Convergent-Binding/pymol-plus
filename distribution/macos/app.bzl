"""macos_app: the app folder wrapped into PyMOL-Open-Source.app.

Runs //distribution/macos:make_app on Bazel's hermetic Python; the output is
one tree artifact, `<name>/PyMOL-Open-Source.app`, for one architecture,
with Info.plist stamped with the app's version (@app_project_metadata).
"""

load("@app_project_metadata//:metadata.bzl", "VERSION")

def _macos_app_impl(ctx):
    out = ctx.actions.declare_directory(ctx.label.name + "/PyMOL-Open-Source.app")
    args = ctx.actions.args()
    args.add("--app", ctx.file.app.path)
    args.add("--info-plist", ctx.file.info_plist)
    args.add("--icon", ctx.file.icon)
    args.add("--version", VERSION)
    args.add("--arch", ctx.attr.arch)
    args.add("--out", out.path)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.app, ctx.file.info_plist, ctx.file.icon],
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "MacosApp",
        progress_message = "Wrapping the app into %{output}",
    )
    return [DefaultInfo(files = depset([out]))]

macos_app = rule(
    implementation = _macos_app_impl,
    attrs = {
        "app": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The app folder, //distribution/bundle.",
        ),
        "arch": attr.string(
            mandatory = True,
            values = ["arm64", "x86_64"],
            doc = "The architecture the universal binaries are cut down to.",
        ),
        "icon": attr.label(allow_single_file = [".icns"], mandatory = True),
        "info_plist": attr.label(allow_single_file = True, mandatory = True),
        "_tool": attr.label(
            default = Label("//distribution/macos:make_app"),
            executable = True,
            cfg = "exec",
        ),
    },
)
