@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo    FULL MF DATA REFRESH STARTED
echo    %DATE% %TIME%
echo ============================================================

cd /d "%~dp0"

:: ---- Python Environment Detection ----
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
    echo [INFO] Running in local virtual environment ^(venv^)...
) else (
    set "PYTHON_EXE=python"
    echo [INFO] Running in global Python environment...
)

:: ---- Track errors without stopping ----
set FAIL_COUNT=0
set FAILED_STEPS=

:: ============================================================
:: PHASE 1: DOWNLOAD RAW FILES (all AMCs)
:: ============================================================

echo.
echo ############################################################
echo   PHASE 1: DOWNLOADING RAW FILES
echo ############################################################

set STEP=0

call :run_step "Aditya Birla Download"  "02_scripts\Download_Scripts\download_aditya_monthly_files.py"
call :run_step "Axis Download"          "02_scripts\Download_Scripts\download_axis_monthly_files.py"
call :run_step "BOI Download"           "02_scripts\Download_Scripts\download_boimf_enumerate_monthly.py"
call :run_step "DSP Download"           "02_scripts\Download_Scripts\download_dsp_monthly_files.py"
call :run_step "HDFC Download"          "02_scripts\Download_Scripts\download_hdfc_monthly_files.py"
call :run_step "Invesco Download"       "02_scripts\Download_Scripts\download_invesco_monthly_files.py"
call :run_step "Jio BlackRock Download" "02_scripts\Download_Scripts\download_jblrk_monthly_files.py"
call :run_step "Kotak Download"         "02_scripts\Download_Scripts\download_kotakmf_interactive.py"
call :run_step "Nippon Download"        "02_scripts\Download_Scripts\download_nippon_monthly_files.py"
call :run_step "PPFAS Download"         "02_scripts\Download_Scripts\download_ppfas_monthly_files.py"
call :run_step "Quant Download"         "02_scripts\Download_Scripts\download_quant_monthly_files.py"
call :run_step "SBI Download"           "02_scripts\Download_Scripts\download_sbi_monthly_files.py"

:: ICICI has no automated download script — raw files are placed manually.

:: ============================================================
:: PHASE 2: CLEAN DATA (all AMCs)
:: ============================================================

echo.
echo ############################################################
echo   PHASE 2: CLEANING DATA
echo ############################################################

call :run_step "Aditya Birla Clean" "02_scripts\Cleaning_Scripts\clean_absl_all_funds.py"
call :run_step "Axis Clean"         "02_scripts\Cleaning_Scripts\clean_axis_all_funds.py"
call :run_step "BOI Clean"          "02_scripts\Cleaning_Scripts\clean_boimf_all_funds.py"
call :run_step "DSP Clean"          "02_scripts\Cleaning_Scripts\clean_dsp_all_funds.py"
call :run_step "HDFC Clean"         "02_scripts\Cleaning_Scripts\clean_hdfc_all_funds.py"
call :run_step "ICICI Clean"        "02_scripts\Cleaning_Scripts\clean_icici_all_funds.py"
call :run_step "Invesco Clean"      "02_scripts\Cleaning_Scripts\clean_invesco_all_funds.py"
call :run_step "Jio BlackRock Clean" "02_scripts\Cleaning_Scripts\clean_jb_all_funds.py"
call :run_step "Kotak Clean"        "02_scripts\Cleaning_Scripts\clean_kotak_all_funds.py"
call :run_step "Nippon Clean"       "02_scripts\Cleaning_Scripts\clean_nippon_all_funds.py"
call :run_step "PPFAS Clean"        "02_scripts\Cleaning_Scripts\clean_ppfas_all_funds.py"
call :run_step "Quant Clean"        "02_scripts\Cleaning_Scripts\clean_quant_all_funds.py"
call :run_step "SBI Clean"          "02_scripts\Cleaning_Scripts\clean_sbi_all_funds.py"

:: ============================================================
:: PHASE 3: BUILD POWER BI DATASET
:: ============================================================

echo.
echo ############################################################
echo   PHASE 3: BUILDING POWER BI DATASET
echo ############################################################

call :run_step "Build PowerBI Dataset" "02_scripts\build_powerbi_dataset.py"

:: ============================================================
:: PHASE 4: UPLOAD TO SUPABASE
:: ============================================================

echo.
echo ############################################################
echo   PHASE 4: UPLOADING TO SUPABASE
echo ############################################################

call :run_step "Upload to Supabase" "02_scripts\upload_to_supabase.py"

:: ============================================================
:: SUMMARY
:: ============================================================

echo.
echo ============================================================
if !FAIL_COUNT! EQU 0 (
    echo    ALL STEPS COMPLETED SUCCESSFULLY
) else (
    echo    COMPLETED WITH !FAIL_COUNT! FAILED STEP^(S^)
    echo.
    echo    Failed steps:
    echo    !FAILED_STEPS!
)
echo    %DATE% %TIME%
echo ============================================================

echo.
echo Output files:
echo   Power BI Long Table : %~dp005_matrix\MASTER\matrix_all_amc_funds_quantity_long.xlsx
echo   Security Master     : %~dp005_matrix\MASTER\security_master.xlsx

echo.
pause
endlocal
exit /b 0

:: ============================================================
:: SUBROUTINE: run_step
::   %~1 = Step label
::   %~2 = Relative script path
:: ============================================================
:run_step
set /a STEP+=1
echo.
echo ------------------------------------------------------------
echo   STEP !STEP!: %~1
echo ------------------------------------------------------------

"%PYTHON_EXE%" "%~dp0%~2"

if !ERRORLEVEL! NEQ 0 (
    echo   [FAIL] %~1
    set /a FAIL_COUNT+=1
    set "FAILED_STEPS=!FAILED_STEPS!     - %~1!LF!"
) else (
    echo   [OK]   %~1
)
goto :eof