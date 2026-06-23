:: filepath: /c:/Users/wiz/Desktop/dev/Emby115Toolkit/build.bat
@echo off
echo Cleaning previous builds...
rmdir /s /q build
rmdir /s /q dist

echo Building application...
cd /d %~dp0..
pyinstaller --clean scripts\build.spec

echo Build complete!
pause