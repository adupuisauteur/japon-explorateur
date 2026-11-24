@echo off
rem Assistant J-ed (version 2.0.2) : double-cliquez sur ce fichier pour ouvrir l'assistant.
rem Il lance la fenetre de l'assistant avec Windows PowerShell, sans console.
rem 2.0.2-rc5 (R6) : sous Windows 11, le Terminal ignore -WindowStyle Hidden et laissait une fenetre vide ouverte.
rem PowerShell est donc lance cache des le depart (Start-Process -WindowStyle Hidden) ; cette fenetre-ci se ferme
rem aussitot. En cas d'echec, lancement comme en 2.0.2-rc4.
set "JED_ASSISTANT=%~dp0assistant\assistant-j-ed.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -WindowStyle Hidden -ArgumentList ('-NoProfile -Sta -ExecutionPolicy Bypass -WindowStyle Hidden -File \"' + $env:JED_ASSISTANT + '\"')"
if errorlevel 1 start "" powershell.exe -NoProfile -Sta -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0assistant\assistant-j-ed.ps1"
