' Lucy C2 — Silent launcher for Windows.
' Double-click this file to start Lucy without any terminal window.
' Logs are written to tools\portable\lucy.log.
' The backend process ID is saved to tools\portable\lucy.pid.
Option Explicit

Dim fso, shell, scriptDir, launcher, logFile, pidFile
Dim chosen, candidates, candidate, cmd
Dim wmi, startup, process, processId, result

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
Set wmi = GetObject("winmgmts:{impersonationLevel=impersonate}!\\.\root\cimv2")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(scriptDir, "launcher.py")
logFile = fso.BuildPath(scriptDir, "lucy.log")
pidFile = fso.BuildPath(scriptDir, "lucy.pid")

If Not fso.FileExists(launcher) Then
    MsgBox "launcher.py not found in " & scriptDir, vbCritical, "Lucy"
    WScript.Quit 1
End If

' Prevent multiple launches.
If fso.FileExists(pidFile) Then
    Dim existingPid, proc
    On Error Resume Next
    existingPid = CInt(fso.OpenTextFile(pidFile).ReadAll())
    On Error GoTo 0
    If existingPid > 0 Then
        Set proc = Nothing
        On Error Resume Next
        Set proc = wmi.Get("Win32_Process.Handle=" & existingPid)
        On Error GoTo 0
        If Not proc Is Nothing Then
            MsgBox "Lucy is already running (PID " & existingPid & ")." & vbCrLf & _
                   "Use 'Stop Lucy.vbs' to stop it first.", vbExclamation, "Lucy"
            WScript.Quit 0
        End If
    End If
End If

' Prefer pythonw.exe so no console appears even if launcher.py is run directly.
chosen = ""
candidates = Array( _
    fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe"), _
    fso.BuildPath(scriptDir, ".venv\Scripts\python.exe"), _
    "pythonw.exe", _
    "python.exe" _
)
For Each candidate In candidates
    If fso.FileExists(candidate) Then
        chosen = candidate
        Exit For
    End If
Next

' Fallback to PATH lookup for pythonw/python.
If chosen = "" Then
    For Each candidate In candidates
        If shell.Run("cmd /c """ & candidate & """ --version 2>nul""", 0, True) = 0 Then
            chosen = candidate
            Exit For
        End If
    Next
End If

If chosen = "" Then
    MsgBox "No Python interpreter found. Please install Python 3.12 or run setup.", vbCritical, "Lucy"
    WScript.Quit 1
End If

cmd = """" & chosen & """ """ & launcher & """ --browser --fast --log-file """ & logFile & """"

' Launch hidden via WMI Win32_Process (returns PID).
Set startup = wmi.Get("Win32_ProcessStartup").SpawnInstance_
startup.ShowWindow = 0 ' SW_HIDE

result = wmi.Get("Win32_Process").Create(cmd, scriptDir, startup, processId)

If result <> 0 Then
    MsgBox "Lucy failed to start (error " & result & "). Check " & logFile, vbExclamation, "Lucy"
    WScript.Quit result
End If

' Save PID for Stop Lucy.vbs.
On Error Resume Next
Dim pidWriter
Set pidWriter = fso.CreateTextFile(pidFile, True)
pidWriter.WriteLine(processId)
pidWriter.Close
On Error GoTo 0
