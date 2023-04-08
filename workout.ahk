SendMode "Input"
SetTitleMatchMode 3
WinActivate("Zwift")
WinGetPos( , , &ZW, &ZH, "Zwift" )
Sleep( 100 )

;X_SCALE := ZW / 1936.0
;Y_SCALE := ZH / 1056.0
X_SCALE := 1.0
Y_SCALE := 1.0

WO_ITEM_X := Round( 500 * X_SCALE )
WO_ITEM1_Y := Round(370 * Y_SCALE )
WO_ITEM2_Y := Round( 430 * Y_SCALE )

DLG_START_X := Round( 1090 * X_SCALE )
DLG_START_Y := Round( 967 * Y_SCALE )

DLG_END_X := Round( 987 * X_SCALE )
DLG_END_Y := Round( 1000 * Y_SCALE )

ShowInfo()
{
    MouseMove(WO_ITEM_X, WO_ITEM1_Y)
}

StartWorkout(y)
{
    ; global WO_ITEM_X, DLG_START_X, DLG_START_Y
    ; MsgBox WO_ITEM_X . " " . DLG_START_X . " " . DLG_START_Y
    Send( "e" )
    Sleep( 250 )
    Click( WO_ITEM_X, y, "Left" )
    ;Click( 500, y, "Left" )
    Sleep( 250 )
    Click( DLG_START_X, DLG_START_Y, "Left" )
    Click( 1000, 967, "Left")
}

CloseDialog()
{
    ; global DLG_END_X, DLG_END_Y
    Loop 1
    {
        Click( DLG_END_X, DLG_END_Y, "Left" )
        ; Click( 987, 1000, "Left" )
        Sleep( 500 )
    }
}

CancelWorkout()
{
    Loop 4
    {
        Send( "{Tab}" )
        Sleep( 500 )
    }
}

cmd := A_Args[1]

if (cmd = "start" )
{
    StartWorkout(WO_ITEM1_Y)
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

ExitApp()