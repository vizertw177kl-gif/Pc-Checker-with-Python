@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (set PY=python) else (set PY=py)
%PY% -c "import psutil" 2>nul || %PY% -m pip install psutil
%PY% "Pc Checker.py"
if errorlevel 1 pause
 