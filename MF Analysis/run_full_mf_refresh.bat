@echo off
echo ============================================================
echo FULL MF DATA REFRESH STARTED
echo ============================================================

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    set PYTHON_EXE="%~dp0venv\Scripts\python.exe"
    echo [INFO] Running in local virtual environment ^(venv^)...
) else (
    set PYTHON_EXE=python
    echo [INFO] Running in global Python environment...
)

echo.
echo ============================================================
echo STEP 1: HDFC Download + Refresh
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\download_hdfc_monthly_files.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: HDFC download/refresh failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo STEP 2: ICICI Clean All Funds
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\clean_icici_all_funds.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: ICICI cleaning failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo STEP 3: ICICI Quantity Matrix
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\create_icici_matrix.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: ICICI matrix creation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo STEP 4: Combined HDFC + ICICI Quantity Matrix
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\create_combined_mf_quantity_matrix.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Combined matrix creation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo STEP 5: Power BI Long Quantity Table
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\create_powerbi_long_quantity_table.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Power BI long table creation failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo STEP 6: Upload to Supabase
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\upload_to_supabase.py"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Supabase upload failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ============================================================
echo FULL MF DATA REFRESH COMPLETED SUCCESSFULLY
echo ============================================================

echo.
echo Final outputs:
echo HDFC Matrix:
echo %~dp004_matrix_output\HDFC\matrix_hdfc_funds_quantity.xlsx

echo.
echo ICICI Matrix:
echo %~dp004_matrix_output\ICICI\matrix_icici_funds_quantity.xlsx

echo.
echo Combined Matrix:
echo %~dp005_matrix\MASTER\matrix_all_amc_funds_quantity.xlsx

echo.
echo Power BI Long Table:
echo %~dp005_matrix\MASTER\matrix_all_amc_funds_quantity_long.xlsx

echo.
pause