@echo off
setlocal

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo No se encontro el Python de self_healer\.venv en "%PYTHON%"
  exit /b 1
)

"%PYTHON%" "%~dp0test_harness.py" %*
exit /b %ERRORLEVEL%
