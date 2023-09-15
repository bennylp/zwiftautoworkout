SendMode "Input"
SetTitleMatchMode 3
ZTITLE := "Zwift ahk_class GLFW30"
WinGetPos( , , &ZW, &ZH, ZTITLE )

X_SCALE := ZW / 1936.0
;Y_SCALE := ZH / 1056.0
Y_SCALE := ZH / 1150.0
;X_SCALE := 1.0
;Y_SCALE := 1.0

WO_ITEM_X := Round( 500 * X_SCALE )
WO_ITEM_Y := Array()
y := 210
Loop 9
{
    WO_ITEM_Y.Push( Round(y * Y_SCALE ) )
    y := y + 60
}

DLG_START_X := Round( 1090 * X_SCALE )
DLG_START_Y := Round( 1000 * Y_SCALE )

DLG_END_X := Round( 987 * X_SCALE )
DLG_END_Y := Round( 1000 * Y_SCALE )

ShowInfo(idx)
{
    ;cls := WinGetClass(ZTITLE)
    ;MsgBox("ZW=" . ZW . ", ZH=" . ZH . ", class=" . cls)

    y := WO_ITEM_Y[idx]
    Click( WO_ITEM_X, y, "Left" )
}

ActivateZwift()
{
    WinActivate(ZTITLE)
    Sleep( 100 )
}

StartWorkout(idx)
{
    y := WO_ITEM_Y[idx]
    Send( "e" )
    Sleep( 350 )
    Click( WO_ITEM_X, y, "Left" )
    Sleep( 350 )
    Click( DLG_START_X, DLG_START_Y, "Left" )
    ;Sleep( 100 )
    ;Click( DLG_START_X, DLG_START_Y, "Left" )
    ;Click( 1000, 967, "Left")
}

CloseDialog()
{
    Loop 1
    {
        Click( DLG_END_X, DLG_END_Y, "Left" )
        Sleep( 50 )
        Send("{Esc}")
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
    idx := Integer(A_Args[2])
    ActivateZwift()
    StartWorkout(idx)
}
else if (cmd = "hotstart" )
{
    idx := Integer(A_Args[2])
    StartWorkout(idx)
}
else if (cmd = "close")
{
    ActivateZwift()
    CloseDialog()
}
else if (cmd = "cancel")
{
    ActivateZwift()
    CancelWorkout()
    Sleep(500)
    CloseDialog()
}
else if (cmd = "uturn")
{
    ActivateZwift()
    Sleep(200)
    Send("{Down down}")
    Sleep(3000)
    Send("{Down up}")
}
else if (cmd = "info")
{
    ActivateZwift()
    idx := Integer(A_Args[2])
    ShowInfo(idx)
}

ExitApp()
