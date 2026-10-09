@echo off
chcp 65001 >nul
rem ---------------------------------------------------------------------
rem  Build the standalone single-file exe (double-click me).
rem
rem  NOTE: everything in this file is ASCII on purpose. cmd reads batch
rem  files line by line at byte offsets, so mixing code pages with CJK
rem  text corrupts parsing (calling chcp in a file that also contains
rem  Chinese makes cmd lose its place). Chinese messages are printed by
rem  _build_exe.py instead, which is Unicode-safe.
rem
rem  Options:  pass --clean to rebuild from scratch
rem ---------------------------------------------------------------------
cd /d "%~dp0"

rem  Keep Python's own output UTF-8 as well, so Chinese stays readable even
rem  when this window's output is piped or redirected to a log file.
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (set "PY=python")

%PY% "%~dp0_build_exe.py" %*
if errorlevel 1 goto fail

echo.
echo Done. The exe is in the dist folder.
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo [FAILED] Packaging aborted - see the messages above.
if not defined NO_PAUSE pause
exit /b 1
