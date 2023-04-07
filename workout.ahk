SendMode Input
WinActivate, Zwift
WinGetPos, WX, WY, WW, WH, Zwift

Sleep, 100

X_SCALE := %WW% / 1936
Y_SCALE := %WH% / 1056

WO_ITEM_X := 500 ; * %X_SCALE%
WO_ITEM1_Y := 430 ; * %Y_SCALE%
WO_ITEM2_Y := 460 ; * %Y_SCALE%

DLG_START_X := 1090 ; * %X_SCALE%
DLG_START_Y := 967 ; * %Y_SCALE%

DLG_END_X := 987 ; * %X_SCALE%
DLG_END_Y := 1000 ; * %Y_SCALE%

ShowInfo()
{
    global WW, WH
    ;MsgBox, %WW% " " %WH%
}

StartWorkout(y)
{
    global WO_ITEM_X, DLG_START_X, DLG_START_Y

    ; MsgBox, %WO_ITEM_X% " " %DLG_START_X% " " %DLG_START_Y%
    SendRaw, e
    Sleep, 250
    ;Click, %WO_ITEM_X%, %y% Left
    Click, 500, %y% Left
    Sleep, 250
    ;Click, %DLG_START_X%, %DLG_START_Y% Left
    Click, 1000, 967 Left
}

CloseDialog()
{
    global DLG_END_X, DLG_END_Y
    Loop, 1
    {
        ; Click, %DLG_END_X%, %DLG_END_Y% Left
        Click, 987, 1000 Left
        Sleep, 500
    }
}

CancelWorkout()
{
    Loop, 4
    {
        Send {Tab}
        Sleep, 500
    }
}

cmd := A_Args[1]

if (cmd = "start" )
{
    StartWorkout(430)
}
else if (cmd = "close")
{
    CloseDialog()
}
else if (cmd = "cancel")
{
    CancelWorkout()
    CloseDialog()
}
else if (cmd = "info")
{
    ShowInfo()
}

ExitApp
