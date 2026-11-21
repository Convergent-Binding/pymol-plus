@echo off
REM Windows counterpart to workspace_status.sh -- see .bazelrc for why this
REM needs to be a native cmd.exe script rather than the same bash script used
REM on Linux and macOS. It must not depend on bash or MSYS2.
set SHA=unknown
for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set SHA=%%i
echo STABLE_GIT_SHA %SHA%
set DATE=0
for /f "delims=" %%i in ('git log -1 --format^=%%ct 2^>nul') do set DATE=%%i
echo STABLE_BUILD_DATE %DATE%
