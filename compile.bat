@echo off
cd /d "%~dp0"
echo Compiling action_dispatch...
cargo build --all 2>&1
echo.
echo Exit code: %errorlevel%

