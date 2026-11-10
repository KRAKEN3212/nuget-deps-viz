@echo off
rem Usage:  run.bat -p PACKAGE [options]
rem Tests:  run.bat test
if "%~1"=="test" goto tests
python "%~dp0src\main.py" %*
exit /b %ERRORLEVEL%

:tests
pushd "%~dp0"
python -m unittest discover -s tests -t . -v
set CODE=%ERRORLEVEL%
popd
exit /b %CODE%
