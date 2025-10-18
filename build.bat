@echo off
cd /d "%~dp0"
echo Building action_dispatch...
cargo build --all --verbose
if %errorlevel% neq 0 (
    echo Build failed!
    exit /b %errorlevel%
)
echo Build successful!

