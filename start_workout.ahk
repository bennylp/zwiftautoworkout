SendMode Input

StartWorkout(y)
{
  ;MsgBox Hello
  WinActivate, Zwift
  Sleep, 100
  Click, 987, 1000 Left
  Sleep, 100
  SendRaw, e
  Sleep, 250
  Click, 500, %y% Left
  Sleep, 250
  Click, 1077, 967 Left
}

StartWorkout(420)
ExitApp
