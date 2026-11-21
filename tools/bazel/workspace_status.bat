@echo off
REM Windows counterpart to workspace_status.sh -- see .bazelrc for why this
REM needs to be a native cmd.exe script rather than the same bash script
REM used on Linux/macOS. Bazel invokes this directly as a subprocess (no
REM shell wrapping needed for a .bat file, unlike .sh), so this must not
REM depend on bash/MSYS2/Git-for-Windows being resolvable at all.
set SHA=unknown
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set SHA=%%i
echo STABLE_GIT_SHA %SHA%
