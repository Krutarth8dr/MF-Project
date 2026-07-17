@echo off
setlocal enabledelayedexpansion

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

set FAILED_STEPS=

REM ============================================================
REM STEP 1: Downloads for all AMCs
REM
REM If one AMC's download fails (site down, layout change, etc.)
REM it is logged and skipped -- the refresh keeps going so the
REM other 11 AMCs still get downloaded and cleaned.
REM ============================================================

echo.
echo ============================================================
echo STEP 1: Downloading raw files for all AMCs
echo ============================================================

call :run_step "Aditya Birla Download" "02_scripts\Download_Scripts\download_aditya_monthly_files.py"
call :run_step "Axis Download"         "02_scripts\Download_Scripts\download_axis_monthly_files.py"
call :run_step "BOI Download"          "02_scripts\Download_Scripts\download_boimf_enumerate_monthly.py"
call :run_step "DSP Download"          "02_scripts\Download_Scripts\download_dsp_monthly_files.py"
call :run_step "HDFC Download"         "02_scripts\Download_Scripts\download_hdfc_monthly_files.py"
call :run_step "Invesco Download"      "02_scripts\Download_Scripts\download_invesco_monthly_files.py"
call :run_step "JB Download"           "02_scripts\Download_Scripts\download_jblrk_monthly_files.py"

echo.
echo ------------------------------------------------------------
echo NOTE: Kotak's downloader is INTERACTIVE. A browser will open
echo and the script will PAUSE for you to log in / solve a captcha,
echo then pause again between pages while scanning for files.
echo Keep an eye on this window until it finishes.
echo ------------------------------------------------------------
call :run_step "Kotak Download"        "02_scripts\Download_Scripts\download_kotakmf_interactive.py"

call :run_step "Nippon Download"       "02_scripts\Download_Scripts\download_nippon_monthly_files.py"
call :run_step "PPFAS Download"        "02_scripts\Download_Scripts\download_ppfas_monthly_files.py"
call :run_step "Quant Download"        "02_scripts\Download_Scripts\download_quant_monthly_files.py"
call :run_step "SBI Download"          "02_scripts\Download_Scripts\download_sbi_monthly_files.py"

REM NOTE: There is currently no ICICI download script in this project
REM (download_icici_monthly_zip.py was removed). ICICI raw files need
REM to be placed under 01_raw_files\ICICI another way for now --
REM the ICICI cleaning step below will just use whatever is already there.

REM ============================================================
REM STEP 2: Cleaning for all AMCs
REM
REM Same continue-on-error behavior as downloads: one AMC's raw
REM files having a bad/changed layout won't block the others.
REM ============================================================

echo.
echo ============================================================
echo STEP 2: Cleaning all AMC files
echo ============================================================

call :run_step "Aditya Birla Clean" "02_scripts\Cleaning_Scripts\clean_absl_all_funds.py"
call :run_step "Axis Clean"         "02_scripts\Cleaning_Scripts\clean_axis_all_funds.py"
call :run_step "BOI Clean"          "02_scripts\Cleaning_Scripts\clean_boimf_all_funds.py"
call :run_step "DSP Clean"          "02_scripts\Cleaning_Scripts\clean_dsp_all_funds.py"
call :run_step "HDFC Clean"         "02_scripts\Cleaning_Scripts\clean_hdfc_all_funds.py"
call :run_step "ICICI Clean"        "02_scripts\Cleaning_Scripts\clean_icici_all_funds.py"
call :run_step "Invesco Clean"      "02_scripts\Cleaning_Scripts\clean_invesco_all_funds.py"
call :run_step "JB Clean"           "02_scripts\Cleaning_Scripts\clean_jb_all_funds.py"
call :run_step "Kotak Clean"        "02_scripts\Cleaning_Scripts\clean_kotak_all_funds.py"
call :run_step "Nippon Clean"       "02_scripts\Cleaning_Scripts\clean_nippon_all_funds.py"
call :run_step "PPFAS Clean"        "02_scripts\Cleaning_Scripts\clean_ppfas_all_funds.py"
call :run_step "Quant Clean"        "02_scripts\Cleaning_Scripts\clean_quant_all_funds.py"
call :run_step "SBI Clean"          "02_scripts\Cleaning_Scripts\clean_sbi_all_funds.py"

REM ============================================================
REM STEP 3: Build the master Power BI dataset (security master +
REM long-format quantity matrix) from every AMC's cleaned file.
REM
REM CRITICAL step -- everything after this depends on it, so we
REM stop the whole refresh here if it fails.
REM ============================================================

echo.
echo ============================================================
echo STEP 3: Building Power BI Dataset (security master + long matrix)
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\build_powerbi_dataset.py"
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Power BI dataset build failed. Stopping here -- the
    echo remaining steps all depend on this output.
    set FAILED_STEPS=!FAILED_STEPS! "Power BI Dataset Build"
    goto :summary
)

REM ============================================================
REM STEP 4: Single-AMC net-buy analysis
REM
REM Only reads the matrix built above, doesn't produce anything
REM anything else depends on -- so a failure here is logged but
REM doesn't block the Supabase upload.
REM ============================================================

echo.
echo ============================================================
echo STEP 4: Finding Single-AMC Net Buys
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\find_single_amc_buy.py"
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Single-AMC net-buy analysis failed. Continuing.
    set FAILED_STEPS=!FAILED_STEPS! "Single-AMC Net Buys"
)

REM ============================================================
REM STEP 5: Upload to Supabase
REM ============================================================

echo.
echo ============================================================
echo STEP 5: Upload to Supabase
echo ============================================================

%PYTHON_EXE% "%~dp002_scripts\upload_to_supabase.py"
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Supabase upload failed.
    set FAILED_STEPS=!FAILED_STEPS! "Supabase Upload"
)

:summary
echo.
echo ============================================================
echo FULL MF DATA REFRESH FINISHED
echo ============================================================

if defined FAILED_STEPS (
    echo.
    echo The following steps reported errors ^(scroll up for details^):
    echo   !FAILED_STEPS!
) else (
    echo.
    echo All steps completed with no errors.
)

echo.
echo Final outputs:
echo Security Master:
echo   %~dp005_matrix\MASTER\security_master.xlsx
echo.
echo Power BI Long Table:
echo   %~dp005_matrix\MASTER\matrix_all_amc_funds_quantity_long.xlsx

echo.
pause
exit /b 0

REM ============================================================
REM SUBROUTINE: run one script, log a warning and continue if it
REM fails instead of stopping the whole refresh.
REM   %1 = display name (for messages)
REM   %2 = script path, relative to this .bat file's folder
REM ============================================================

:run_step
echo.
echo ---- %~1 ----
%PYTHON_EXE% "%~dp0%~2"
IF %ERRORLEVEL% NEQ 0 (
    echo WARNING: %~1 failed. Continuing with the rest of the refresh.
    set FAILED_STEPS=!FAILED_STEPS! "%~1"
)
exit /b 0