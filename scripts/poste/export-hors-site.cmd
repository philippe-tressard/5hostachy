@echo off
rem ============================================================================
rem  export-hors-site.cmd — Lanceur Windows de la copie hors site des sauvegardes
rem
rem  Double-cliquer ce fichier. Il ne fait que trouver Git Bash et lui confier
rem  export-hors-site.sh, qui porte toute la logique : aucune règle métier ici,
rem  sinon il y en aurait deux à maintenir.
rem
rem  `pause` en fin de course : sans lui, la fenêtre se referme sur le résumé
rem  et le lancement manuel ne rend aucun compte — ce qui est tout l'intérêt.
rem ============================================================================
setlocal

set "BASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%BASH%" set "BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not exist "%BASH%" set "BASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not exist "%BASH%" echo.
if not exist "%BASH%" echo   Git Bash introuvable. Installer Git pour Windows, puis relancer.
if not exist "%BASH%" pause
if not exist "%BASH%" exit /b 1

rem Se placer a la RACINE du depot : le script y trouve lib-role.sh (table des
rem noeuds), restee la avec les scripts lances par cron (#337).
cd /d "%~dp0..\.."
"%BASH%" -lc "./scripts/poste/export-hors-site.sh"

echo.
pause
