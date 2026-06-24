:: filepath: /c:/Users/wiz/Desktop/dev/Emby115Toolkit/windows_build.bat
@echo off
echo Cleaning previous builds...
rmdir /s /q build
rmdir /s /q dist

echo Building application...
pyinstaller --clean windows_build.spec

echo Build complete!
pause
