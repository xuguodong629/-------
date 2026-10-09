@echo off
rem ---------------------------------------------------------------------
rem  Run from source (needs Python 3.8+).  ASCII only on purpose:
rem  see the note inside the packaging bat - cmd reads batch files by byte
rem  offset, so any CJK text in here corrupts parsing once "chcp" runs.
rem  No Python? Just double-click the packaged exe in the dist folder.
rem
rem  Extra arguments are passed through, e.g.
rem     this-file.bat --selftest
rem  which runs headless once and writes the self-check report.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

rem  Pin UTF-8 twice: chcp for this console window, PYTHON* for Python's own
rem  stdout/stderr - so Chinese stays readable in a console AND when the
rem  output is piped or redirected to a log file.
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem  Pick a launcher: prefer "py" (the Windows launcher), else "python".
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY goto nopython

%PY% main.py %*
if errorlevel 1 goto failed
exit /b 0

:nopython
echo.
echo [FAILED] Python not found - neither "py" nor "python" is on PATH.
echo   1^) Install Python 3.8+ and tick "Add python.exe to PATH"
echo   2^) Or double-click the packaged exe inside the dist folder ^(no Python needed^)
goto hold

:failed
echo.
echo [FAILED] The program exited with an error - see the messages above.
echo   1^) Run "py main.py" in this folder to see the full traceback
echo   2^) Or double-click the packaged exe inside the dist folder

:hold
echo.
echo Press any key to close this window . . .
pause >nul
exit /b 1
