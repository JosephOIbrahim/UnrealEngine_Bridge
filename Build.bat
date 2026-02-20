@echo off
setlocal enabledelayedexpansion

REM ============================================
REM UnrealEngineBridge Build Script
REM Builds the UE5.7 C++ project
REM ============================================

set "UE_ROOT=C:\Program Files\Epic Games\UE_5.7"
set "PROJECT_PATH=%~dp0UnrealEngineBridge.uproject"
set "UBT=%UE_ROOT%\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe"
set "BUILD_BAT=%UE_ROOT%\Engine\Build\BatchFiles\Build.bat"

echo.
echo ============================================
echo   UnrealEngineBridge Build Script
echo ============================================
echo.
echo Project: %PROJECT_PATH%
echo UE5 Path: %UE_ROOT%
echo.

REM Check if UE5 exists
if not exist "%UE_ROOT%" (
    echo ERROR: UE5.7 not found at %UE_ROOT%
    echo Please edit this script and set UE_ROOT to your UE5 installation path.
    pause
    exit /b 1
)

REM Check if project exists
if not exist "%PROJECT_PATH%" (
    echo ERROR: Project file not found: %PROJECT_PATH%
    pause
    exit /b 1
)

echo What would you like to do?
echo.
echo   1. Generate Visual Studio project files
echo   2. Build project (Development Editor)
echo   3. Both (Generate + Build)
echo   4. Clean and Rebuild
echo   5. Exit
echo.
set /p CHOICE="Enter choice (1-5): "

if "%CHOICE%"=="1" goto :generate
if "%CHOICE%"=="2" goto :build
if "%CHOICE%"=="3" goto :both
if "%CHOICE%"=="4" goto :clean
if "%CHOICE%"=="5" exit /b 0

echo Invalid choice.
pause
exit /b 1

:generate
echo.
echo Generating Visual Studio project files...
echo.
"%UBT%" -projectfiles -project="%PROJECT_PATH%" -game -engine -progress
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to generate project files.
    echo Check the log above for details.
    pause
    exit /b 1
)
echo.
echo SUCCESS: Project files generated.
echo You can now open UnrealEngineBridge.sln in Visual Studio.
pause
exit /b 0

:build
echo.
echo Building UnrealEngineBridgeEditor (Development, Win64)...
echo.
call "%BUILD_BAT%" UnrealEngineBridgeEditor Win64 Development "%PROJECT_PATH%" -waitmutex -progress
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed.
    echo Check the errors above.
    pause
    exit /b 1
)
echo.
echo SUCCESS: Build completed.
echo You can now open the project in UE5.
pause
exit /b 0

:both
echo.
echo Step 1/2: Generating Visual Studio project files...
echo.
"%UBT%" -projectfiles -project="%PROJECT_PATH%" -game -engine -progress
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to generate project files.
    pause
    exit /b 1
)
echo.
echo Step 2/2: Building UnrealEngineBridgeEditor...
echo.
call "%BUILD_BAT%" UnrealEngineBridgeEditor Win64 Development "%PROJECT_PATH%" -waitmutex -progress
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed.
    pause
    exit /b 1
)
echo.
echo SUCCESS: Project generated and built.
echo You can now open UnrealEngineBridge.uproject in UE5.
pause
exit /b 0

:clean
echo.
echo Cleaning intermediate files...
echo.
if exist "%~dp0Intermediate" (
    echo Removing Intermediate folder...
    rmdir /s /q "%~dp0Intermediate"
)
if exist "%~dp0Binaries" (
    echo Removing Binaries folder...
    rmdir /s /q "%~dp0Binaries"
)
if exist "%~dp0.vs" (
    echo Removing .vs folder...
    rmdir /s /q "%~dp0.vs"
)
if exist "%~dp0*.sln" (
    echo Removing solution files...
    del /q "%~dp0*.sln"
)
echo.
echo Clean complete. Now rebuilding...
goto :both
