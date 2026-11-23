@echo off
setlocal
set "IITPAVE_SOURCE=%~dp0external_tools\IRC_37_IITPAVE"
set "IITPAVE_WORK=%~dp0external_tools\IITPAVE_work"

if not exist "%IITPAVE_SOURCE%\IITPAVE_START.jar" (
  echo IITPAVE_START.jar was not found in "%IITPAVE_SOURCE%".
  goto :failed
)
if not exist "%IITPAVE_SOURCE%\lib\AbsoluteLayout.jar" (
  echo IITPAVE's AbsoluteLayout.jar was not found in "%IITPAVE_SOURCE%\lib".
  goto :failed
)
if not exist "%IITPAVE_SOURCE%\IITPAVE\IITPFILE.exe" (
  echo IITPAVE's native solver was not found in "%IITPAVE_SOURCE%\IITPAVE".
  goto :failed
)
if not exist "%IITPAVE_SOURCE%\IITPAVE\gauss.qua" (
  echo IITPAVE's gauss.qua data file was not found in "%IITPAVE_SOURCE%\IITPAVE".
  goto :failed
)
where java.exe >nul 2>&1
if errorlevel 1 (
  echo Java was not found on PATH. Install a compatible Windows Java runtime and retry.
  goto :failed
)
if /i "%~1"=="--check" (
  echo IITPAVE files and Java were found. Working directory: "%IITPAVE_WORK%"
  exit /b 0
)
if not exist "%IITPAVE_WORK%\IITPAVE\" mkdir "%IITPAVE_WORK%\IITPAVE"
if not exist "%IITPAVE_WORK%\IITPAVE\" (
  echo Could not create the IITPAVE working folder.
  goto :failed
)
if not exist "%IITPAVE_WORK%\IITPAVE\IITPFILE.exe" copy /b "%IITPAVE_SOURCE%\IITPAVE\IITPFILE.exe" "%IITPAVE_WORK%\IITPAVE\IITPFILE.exe" >nul
if not exist "%IITPAVE_WORK%\IITPAVE\gauss.qua" copy /b "%IITPAVE_SOURCE%\IITPAVE\gauss.qua" "%IITPAVE_WORK%\IITPAVE\gauss.qua" >nul
if not exist "%IITPAVE_WORK%\IITPAVE\IITPFILE.exe" goto :failed
if not exist "%IITPAVE_WORK%\IITPAVE\gauss.qua" goto :failed
pushd "%IITPAVE_WORK%"
if errorlevel 1 goto :failed
echo Opening IITPAVE. Inputs and results are stored in "%IITPAVE_WORK%\IITPAVE".
java.exe -cp "%IITPAVE_SOURCE%\IITPAVE_START.jar;%IITPAVE_SOURCE%\lib\AbsoluteLayout.jar" NewJFrame1
set "IITPAVE_EXIT=%ERRORLEVEL%"
popd
if not "%IITPAVE_EXIT%"=="0" (
  echo IITPAVE could not be started or exited with an error. Java returned %IITPAVE_EXIT%.
  goto :failed
)
exit /b 0

:failed
echo.
echo See frontend\README.md for setup details.
if /i not "%~1"=="--check" pause
exit /b 1
