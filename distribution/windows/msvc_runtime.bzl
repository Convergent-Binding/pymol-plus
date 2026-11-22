"""msvc_runtime: the Microsoft C++ runtime DLLs and license as one tree.

Runs //distribution/windows:unpack_vc_redist on the pinned vc_redist.x64.exe
into two trees: the output group `dlls` (<name>/dlls, the runtime DLLs) and
the output group `license` (<name>/license, LICENSE.RTF and LICENSE.txt).
"""

def _msvc_runtime_impl(ctx):
    dlls = ctx.actions.declare_directory(ctx.label.name + "/dlls")
    license = ctx.actions.declare_directory(ctx.label.name + "/license")
    args = ctx.actions.args()
    args.add("--exe", ctx.file.vc_redist)
    args.add("--dlls", dlls.path)
    args.add("--license", license.path)
    ctx.actions.run(
        outputs = [dlls, license],
        inputs = [ctx.file.vc_redist],
        executable = ctx.executable._tool,
        arguments = [args],
        # freeze-core derives its download cache from the home folder when
        # it is imported; unpack_exe never writes there.
        env = {
            "HOME": ".",
            "USERPROFILE": ".",
        },
        mnemonic = "UnpackVcRedist",
        progress_message = "Unpacking the Microsoft C++ runtime into %{output}",
    )
    return [
        DefaultInfo(files = depset([dlls, license])),
        OutputGroupInfo(
            dlls = depset([dlls]),
            license = depset([license]),
        ),
    ]

msvc_runtime = rule(
    implementation = _msvc_runtime_impl,
    attrs = {
        "vc_redist": attr.label(
            allow_single_file = [".exe"],
            mandatory = True,
            doc = "The Visual C++ Redistributable, @vc_redist//file.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/windows:unpack_vc_redist"),
            executable = True,
            cfg = "exec",
        ),
    },
)
