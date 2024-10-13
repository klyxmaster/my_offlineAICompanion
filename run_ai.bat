@echo off
title Virtual AI 
cls
:: change terminal color - mostly for PS.
color 7

:: Set the path to WinPython and its Scripts folder
SET "PYTHON_PATH=E:\python\python-3.11.9.amd64"
SET "SCRIPTS_PATH=%PYTHON_PATH%\Scripts"

:: Set the path to Ollama (adjust path based on where you installed it)
SET "OLLAMA_PATH=E:\Ollama"

:: Add the WinPython, Scripts, and Ollama directories to the PATH environment variable
SET "PATH=%PYTHON_PATH%;%SCRIPTS_PATH%;%OLLAMA_PATH%;%PATH%"

:: Print the current PATH to verify the changes (optional)
:: echo Current PATH: %PATH%

:: Run the Python script using WinPython's Python executable
"%PYTHON_PATH%\python.exe" app.py

exit /b 0
