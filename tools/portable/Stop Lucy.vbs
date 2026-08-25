' Lucy C2 — Stop the background Lucy process started by 'Launch Lucy.vbs'.
Option Explicit

Dim fso, shell, scriptDir, pidFile, logFile
Dim pidStr, pid, killed

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pidFile = fso.BuildPath(scriptDir, "lucy.pid")
logFile = fso.BuildPath(scriptDir, "lucy.log")

If Not fso.FileExists(pidFile) Then
    WScript.Echo "Lucy does not appear to be running." & vbCrLf & _
                 "If a process is still listening on port 8000, kill it manually.", vbInformation, "Lucy"
    WScript.Quit 0
End If

Dim reader
Set reader = fso.OpenTextFile(pidFile, 1, False)
pidStr = Trim(reader.ReadLine())
reader.Close

If IsNumeric(pidStr) Then
    pid = CInt(pidStr)
    killed = False
    On Error Resume Next
    shell.Run "taskkill /PID " & pid & " /T /F", 0, True
    If Err.Number = 0 Then
        killed = True
    End If
    On Error GoTo 0

    If killed Then
        fso.DeleteFile pidFile, True
        WScript.Echo "Lucy stopped.", vbInformation, "Lucy"
    Else
        WScript.Echo "Could not stop Lucy (PID " & pid & ")." & vbCrLf & _
                     "Check " & logFile & " for details.", vbExclamation, "Lucy"
    End If
Else
    WScript.Echo "Invalid PID file: " & pidFile, vbExclamation, "Lucy"
End If
