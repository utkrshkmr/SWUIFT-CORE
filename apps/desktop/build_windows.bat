@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /D "%SCRIPT_DIR%"

set "VENV=.venv\Scripts"
set "PYINSTALLER=%VENV%\pyinstaller.exe"
set "PYTHON=%VENV%\python.exe"
set "SPEC=swuift_app.spec"

echo ========================================
echo  SWUIFT Windows build
echo ========================================

if not exist "SWUIFT.ico" (
    echo Generating SWUIFT.ico from SWUIFT.icns ...
    "%PYTHON%" -c "from PIL import Image; img = Image.open('SWUIFT.icns'); img.save('SWUIFT.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    if errorlevel 1 (
        echo WARNING: Could not generate SWUIFT.ico. SWUIFT.icns may not be present.
    ) else (
        echo   SWUIFT.ico created.
    )
)

echo.
echo Running PyInstaller ...
"%PYINSTALLER%" "%SPEC%" --noconfirm --clean
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete: dist\SWUIFT\SWUIFT.exe

if exist "swuift_setup.iss" (
    echo.
    echo Creating Windows installer with InnoSetup ...
    set "INNO_COMPILER=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    if not exist "!INNO_COMPILER!" (
        set "INNO_COMPILER=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    )
    if exist "!INNO_COMPILER!" (
        "!INNO_COMPILER!" swuift_setup.iss
        if errorlevel 1 (
            echo WARNING: InnoSetup build failed.
        ) else (
            echo InnoSetup installer created in dist\
        )
    ) else (
        echo NOTE: InnoSetup not found, skipping installer creation.
        echo       Install InnoSetup 6 from https://jrsoftware.org/isdl.php
    )
)

echo.
echo ========================================
echo  Build finished.
echo ========================================
endlocal
