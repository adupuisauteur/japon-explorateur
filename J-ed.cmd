@echo off
rem Assistant J-ed (version 2.0.2) : double-cliquez sur ce fichier pour ouvrir l'assistant.
rem Il lance la fenetre de l'assistant avec Windows PowerShell, sans ouvrir de console.
start "" powershell.exe -NoProfile -Sta -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0assistant\assistant-j-ed.ps1"
