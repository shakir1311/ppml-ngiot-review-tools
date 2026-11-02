@echo off
rem PDF Text Extractor (Windows). On the first start it sets itself up: uv (which fetches Python 3.12 for x64, which also runs
rem on Windows on ARM), the packages the app needs (ready-built, so no compiler is needed), a self-test and a shortcut on the
rem desktop. After that it starts the app at once.
cd /d "%~dp0"
set "UV="
where uv >nul 2>nul && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
  echo Installing uv ^(it fetches Python and the packages the app needs^) ...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  if errorlevel 1 ( echo Could not install uv: check the internet connection, then try again. & pause & exit /b 1 )
  set "UV=%USERPROFILE%\.local\bin\uv.exe"
)
rem set up when never set up here, or when .venv was made on another computer and does not run here
set "SETUP="
if not exist ".venv\.ready" set "SETUP=1"
if not defined SETUP ".venv\Scripts\python.exe" -c "import PySide6, pymupdf" >nul 2>nul || set "SETUP=1"
if defined SETUP (
  echo Setting up PDF Text Extractor ^(first start only; a few minutes^) ...
  if exist ".venv" rmdir /s /q ".venv"
  "%UV%" venv --managed-python --python cpython-3.12-windows-x86_64-none .venv || "%UV%" venv --python cpython-3.12-windows-x86_64-none .venv
  if errorlevel 1 ( echo The set-up failed ^(see above^). & pause & exit /b 1 )
  "%UV%" pip install --python ".venv\Scripts\python.exe" --only-binary :all: -r pyproject.toml
  if errorlevel 1 ( echo The set-up failed ^(see above^). Check the internet connection, then start again. & pause & exit /b 1 )
  echo Checking the app on sample PDFs ...
  ".venv\Scripts\python.exe" -m pdftextextractor.selftest --quick
  type nul > ".venv\.ready"
  ".venv\Scripts\python.exe" -m pdftextextractor.shortcut --if-missing
)
start "" ".venv\Scripts\pythonw.exe" -m pdftextextractor
