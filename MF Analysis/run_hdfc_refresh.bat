@echo off
echo ==========================================
echo HDFC Mutual Fund Matrix Refresh Started
echo ==========================================

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    set PYTHON_EXE="%~dp0venv\Scripts\python.exe"
    echo [INFO] Running in local virtual environment ^(venv^)...
) else (
    set PYTHON_EXE=python
    echo [INFO] Running in global Python environment...
)

echo.
echo Step 1: Running cleaning script...
%PYTHON_EXE% "%~dp002_scripts\clean_hdfc_all_funds.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Cleaning script failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Step 2: Running matrix creation script...
%PYTHON_EXE% "%~dp002_scripts\create_hdfc_matrix.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Matrix creation script failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ==========================================
echo HDFC Matrix refreshed successfully!
echo ==========================================
pause