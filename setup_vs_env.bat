@echo off
REM Setup Visual Studio environment for building C++ projects on Windows
REM This script checks if cl.exe and cmake.exe are available and sets up VS environment if needed

set CL_FOUND=1
set CMAKE_FOUND=1

REM Check if cl.exe is in PATH
where cl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set CL_FOUND=0

REM Check if cmake.exe is in PATH
where cmake.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set CMAKE_FOUND=0

REM Only setup VS environment if cl.exe or cmake.exe are missing
if %CL_FOUND% NEQ 0 (
  goto :setup_vs
)
if %CMAKE_FOUND% NEQ 0 (
  goto :setup_vs
)
goto :run_cmake

:setup_vs
echo Setting up Visual Studio environment...

REM Find latest installed VS with a VC toolset
for /f "usebackq tokens=*" %%i in (`
  "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" ^
    -latest -requires Microsoft.Component.MSBuild -products * -property installationPath 2^>nul
`) do set VSROOT=%%i

if not defined VSROOT (
  echo Visual Studio not found. Please install Visual Studio with C++ build tools.
  echo You can also install Build Tools for Visual Studio 2022 from:
  echo https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
  exit /b 1
)

echo Found Visual Studio at: %VSROOT%
call "%VSROOT%\Common7\Tools\VsDevCmd.bat" -arch=x64

if %ERRORLEVEL% NEQ 0 (
  echo Failed to setup Visual Studio environment
  exit /b 1
)

echo Visual Studio environment setup complete.

:run_cmake
REM Verify tools are now available
where cl.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: cl.exe still not found after VS setup
  exit /b 1
)

where cmake.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo WARNING: cmake.exe not found. Please install CMake and add it to PATH.
  echo Download from: https://cmake.org/download/
  exit /b 1
)

echo Build environment ready.
exit /b 0
