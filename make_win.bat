@echo off
REM Wrapper script to setup Visual Studio environment and run make on Windows
REM Usage: make_win.bat [target]

set CL_FOUND=1
set CMAKE_FOUND=1
set VCPKG_FOUND=1

REM Check if cl.exe is in PATH
where cl.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set CL_FOUND=0

REM Check if cmake.exe is in PATH
where cmake.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set CMAKE_FOUND=0

REM Check if vcpkg.exe is in PATH
where vcpkg.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 set VCPKG_FOUND=0

REM Only setup VS environment if tools are missing
if %CL_FOUND% EQU 0 if %CMAKE_FOUND% EQU 0 if %VCPKG_FOUND% EQU 0 (
  echo Build tools already available, running make directly...
  goto :setup_vcpkg_env
)

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

REM Check if cmake.exe is still missing and try to find it
where cmake.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :setup_vcpkg

echo Looking for CMake in common installation locations...

REM Common CMake installation paths
set CMAKE_PATHS=
set CMAKE_PATHS=%CMAKE_PATHS%;C:\Program Files\CMake\bin
set CMAKE_PATHS=%CMAKE_PATHS%;C:\Program Files (x86)\CMake\bin
set CMAKE_PATHS=%CMAKE_PATHS%;%ProgramFiles%\CMake\bin
set CMAKE_PATHS=%CMAKE_PATHS%;%ProgramFiles(x86)%\CMake\bin

REM Check VS installer for CMake
if defined VSROOT (
  set CMAKE_PATHS=%CMAKE_PATHS%;%VSROOT%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin
)

REM Try to find CMake in these paths
for %%p in (%CMAKE_PATHS:;= %) do (
  if exist "%%p\cmake.exe" (
    echo Found CMake at: %%p
    set PATH=%%p;%PATH%
    goto :setup_vcpkg
  )
)

echo WARNING: cmake.exe not found in common locations.
echo Please install CMake and add it to PATH.
echo Download from: https://cmake.org/download/
echo Or install via chocolatey: choco install cmake
echo Or install via Visual Studio Installer (C++ CMake tools)

:setup_vcpkg
REM Always use local vcpkg installation for better control
echo Setting up local vcpkg for dependency management...

REM Force local vcpkg installation
set VCPKG_ROOT=%CD%\vcpkg

if not exist "%VCPKG_ROOT%" (
  echo Cloning vcpkg repository...
  git clone https://github.com/Microsoft/vcpkg.git "%VCPKG_ROOT%"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to clone vcpkg. Please ensure git is installed.
    exit /b 1
  )
)

echo Bootstrapping local vcpkg...
pushd "%VCPKG_ROOT%"
if not exist "vcpkg.exe" (
  call .\bootstrap-vcpkg.bat
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to bootstrap vcpkg
    popd
    exit /b 1
  )
)
popd

REM Add local vcpkg to PATH (prepend to ensure it takes precedence)
set PATH=%VCPKG_ROOT%;%PATH%

:setup_vcpkg_env
REM Set vcpkg environment variables
if not defined VCPKG_ROOT (
  for /f "delims=" %%i in ('where vcpkg.exe 2^>nul') do (
    for %%j in ("%%i") do set VCPKG_ROOT=%%~dpj
  )
)

if defined VCPKG_ROOT (
  REM Remove trailing backslash
  if "%VCPKG_ROOT:~-1%"=="\" set VCPKG_ROOT=%VCPKG_ROOT:~0,-1%
  echo Using vcpkg from: %VCPKG_ROOT%
  set CMAKE_TOOLCHAIN_FILE=%VCPKG_ROOT%\scripts\buildsystems\vcpkg.cmake
  set VCPKG_INSTALLED_DIR=%CD%\vcpkg_installed

  REM Install required dependencies
  echo Installing dependencies via vcpkg manifest...
  vcpkg install --triplet x64-windows
  if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Failed to install dependencies via vcpkg manifest, trying classic mode...
    vcpkg install zlib:x64-windows
    if %ERRORLEVEL% NEQ 0 (
      echo WARNING: Failed to install zlib via vcpkg
    )
  )
) else (
  echo WARNING: vcpkg not available, dependencies may not be found
)

:run_make
REM Verify tools are available
where cl.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: cl.exe not found. Please install Visual Studio with C++ build tools.
  exit /b 1
)

where cmake.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: cmake.exe not found. Build will fail.
  echo Please install CMake or ensure it's in your PATH.
  exit /b 1
)

echo Build environment ready.
echo - Visual C++ compiler: available
echo - CMake: available
if defined CMAKE_TOOLCHAIN_FILE (
  echo - vcpkg toolchain: %CMAKE_TOOLCHAIN_FILE%
)

REM Run make with all passed arguments
if "%~1"=="" (
  make
) else (
  make %*
)

exit /b %ERRORLEVEL%
