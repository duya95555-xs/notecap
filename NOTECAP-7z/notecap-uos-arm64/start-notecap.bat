@echo off
setlocal enabledelayedexpansion
set "DIR=%~dp0"
set "PYW="
set "PYW_FALLBACK="

rem Prefer a pythonw whose interpreter has BOTH tkinter and Pillow (Pillow = screenshot).
for /f "delims=" %%p in ('where pythonw 2^>nul') do (
    if not defined PYW (
        if exist "%%~dpppython.exe" (
            "%%~dpppython.exe" -c "import tkinter" >nul 2>nul
            if !errorlevel! equ 0 (
                if not defined PYW_FALLBACK set "PYW_FALLBACK=%%p"
                "%%~dpppython.exe" -c "import tkinter, PIL" >nul 2>nul
                if !errorlevel! equ 0 set "PYW=%%p"
            )
        )
    )
)

rem Fall back to scanning the usual per-user install locations.
if not defined PYW (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if not defined PYW (
            if exist "%%d\pythonw.exe" (
                "%%d\python.exe" -c "import tkinter" >nul 2>nul
                if !errorlevel! equ 0 (
                    if not defined PYW_FALLBACK set "PYW_FALLBACK=%%d\pythonw.exe"
                    "%%d\python.exe" -c "import tkinter, PIL" >nul 2>nul
                    if !errorlevel! equ 0 set "PYW=%%d\pythonw.exe"
                )
            )
        )
    )
)

rem Nothing has Pillow: still launch the tkinter-only one, the app will warn in its status bar.
if not defined PYW if defined PYW_FALLBACK set "PYW=!PYW_FALLBACK!"

if not defined PYW (
    echo.
    echo   [notecap] No Python with tkinter found.
    echo.
    echo   Install Python from python.org and keep the "tcl/tk" component enabled.
    echo   For screenshots also run:  pip install pillow
    echo.
    pause
    exit /b 1
)

rem Stop the running instance first, so freshly edited code actually gets loaded.
start "" /wait "!PYW!" "%DIR%notecap.py" --quit >nul 2>nul
ping -n 2 127.0.0.1 >nul

start "" "!PYW!" "%DIR%notecap.py"
