"""Hermetic shader-cache and build-info header generation for `_cmd`.

Wraps //tools/bazel:generate_headers in a Bazel action, so ShaderText.h,
ShaderText.cpp and PyMOLBuildInfo.h are produced under bazel-bin -- never in
the source tree -- from declared inputs: the shader sources and Bazel's stable
workspace-status file, which carries the git SHA and the commit time.
"""

load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
load("@rules_cc//cc/common:cc_info.bzl", "CcInfo")

def _pymol_generated_headers_impl(ctx):
    shader_header = ctx.actions.declare_file("ShaderText.h")
    shader_cpp = ctx.actions.declare_file("ShaderText.cpp")
    build_info_header = ctx.actions.declare_file("PyMOLBuildInfo.h")
    outputs = [shader_header, shader_cpp, build_info_header]

    args = ctx.actions.args()
    args.add("--shader-dir", ctx.files.shader_srcs[0].dirname)
    args.add("--shader-header-out", shader_header)
    args.add("--shader-cpp-out", shader_cpp)
    args.add("--build-info-out", build_info_header)
    args.add("--info-file", ctx.info_file)

    ctx.actions.run(
        executable = ctx.executable._generator,
        arguments = [args],
        inputs = depset(ctx.files.shader_srcs + [ctx.info_file]),
        outputs = outputs,
        mnemonic = "PymolGenHeaders",
        progress_message = "Generating PyMOL shader-cache and build-info headers",
    )

    compilation_context = cc_common.create_compilation_context(
        headers = depset(outputs),
        includes = depset([shader_header.dirname]),
    )
    return [
        DefaultInfo(files = depset(outputs)),
        CcInfo(compilation_context = compilation_context),
    ]

pymol_generated_headers = rule(
    implementation = _pymol_generated_headers_impl,
    attrs = {
        "shader_srcs": attr.label_list(allow_files = True, mandatory = True),
        "_generator": attr.label(
            default = "//tools/bazel:generate_headers",
            executable = True,
            cfg = "exec",
        ),
    },
)
