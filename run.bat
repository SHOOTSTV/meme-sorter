@echo off
chcp 65001 >nul
title Meme Sorter
cd /d "%~dp0"

REM Find Python (py launcher or python on PATH)
where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0meme_sorter.py" %*
    goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0meme_sorter.py" %*
    goto end
)

echo.
echo  Python is not installed on this computer.
echo  Install it for free from https://www.python.org/downloads/
echo  (tick "Add Python to PATH" during installation), then run this file again.
echo.
echo  ----
echo  Python n'est pas installe sur cet ordinateur.
echo  Installez-le gratuitement depuis https://www.python.org/downloads/
echo  (cochez "Add Python to PATH"), puis relancez ce fichier.
echo.
pause

:end
