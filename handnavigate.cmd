@echo off
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Create .venv and install requirements-dev.txt first. See CORE_WORKFLOW.md.
  exit /b 2
)
pushd "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m handnavigate live transfer %*
set "HANDNAVIGATE_EXIT=%ERRORLEVEL%"
popd
exit /b %HANDNAVIGATE_EXIT%
