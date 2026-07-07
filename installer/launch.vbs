' Asterism launcher — the Desktop shortcut points here.
' Runs the real launcher (launch.ps1) with no console window.
Set sh = CreateObject("WScript.Shell")
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
sh.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dir & "launch.ps1""", 0, False
