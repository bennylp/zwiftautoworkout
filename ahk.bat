@echo off

if exist "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe" (
    "C:\Program Files\AutoHotkey\v2\AutoHotkey.exe" %1 %2 %3 %4
) else (
    "C:\Program Files\AutoHotkey\AutoHotkey.exe"  %1 %2 %3 %4
)
