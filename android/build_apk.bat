@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo    VOICESHIELD AI - ANDROID TELEPHONY DEFENSE APK BUILD UTILITY
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 1. Check Java
java -version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Java not found in PATH. Please install JDK 17+ or set JAVA_HOME.
    exit /b 1
)
echo [OK] Java environment detected.

:: 2. Check Android SDK
set "SDK_FOUND=0"
if defined ANDROID_HOME (
    if exist "%ANDROID_HOME%" (
        echo [OK] ANDROID_HOME found: %ANDROID_HOME%
        set "SDK_FOUND=1"
    )
)

if "%SDK_FOUND%"=="0" (
    if exist "%LOCALAPPDATA%\Android\Sdk" (
        echo [OK] Local Android SDK detected at %LOCALAPPDATA%\Android\Sdk
        echo sdk.dir=%LOCALAPPDATA%\Android\Sdk> local.properties
        set "SDK_FOUND=1"
    )
)

if "%SDK_FOUND%"=="0" (
    if not exist "local.properties" (
        echo.
        echo [NOTE] Android SDK not detected in default CLI path.
        echo RECOMMENDED APPROACH:
        echo 1. Open Android Studio.
        echo 2. Click "Open" and select the folder:
        echo    %SCRIPT_DIR%
        echo 3. Android Studio will automatically download the SDK and Gradle.
        echo 4. Click "Build" > "Build Bundle(s) / APK(s)" > "Build APK(s)".
        echo.
        echo If you already have the SDK installed elsewhere, copy local.properties.example
        echo to local.properties and set your sdk.dir path.
        exit /b 0
    )
)

:: 3. Run Gradle Build
echo.
echo [BUILD] Invoking Gradle Wrapper to assemble Debug APK...
call gradlew.bat assembleDebug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ======================================================================
    echo    BUILD SUCCESSFUL! VoiceShield AI APK Ready
    echo ======================================================================
    echo Output APK location:
    echo %SCRIPT_DIR%app\build\outputs\apk\debug\app-debug.apk
    echo.
    echo Next Steps:
    echo 1. Connect Android phone via USB with USB Debugging enabled.
    echo 2. Install: adb install app\build\outputs\apk\debug\app-debug.apk
    echo 3. Open VoiceShield AI on your phone and tap "Set Default Call Screening".
    echo ======================================================================
) else (
    echo.
    echo [ERROR] Build encountered an issue. Try opening the project in Android Studio.
)

endlocal
