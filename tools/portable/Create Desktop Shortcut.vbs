' Creates a Lucy C2 desktop shortcut that silently launches the dashboard.
Option Explicit

Dim fso, shell, desktop, shortcut, scriptDir, launchVbs, rootDir, iconFile
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
launchVbs = fso.BuildPath(scriptDir, "Launch Lucy.vbs")
rootDir = fso.GetFolder(scriptDir).ParentFolder.ParentFolder.Path
iconFile = fso.BuildPath(scriptDir, "lucy.ico")

If Not fso.FileExists(launchVbs) Then
    WScript.Echo "Launch Lucy.vbs not found in " & scriptDir, vbCritical, "Lucy"
    WScript.Quit 1
End If

desktop = shell.SpecialFolders("Desktop")
Set shortcut = shell.CreateShortcut(fso.BuildPath(desktop, "Lucy C2.lnk"))
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & launchVbs & """"
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "Launch Lucy C2"
shortcut.WindowStyle = 7 ' Minimized
If fso.FileExists(iconFile) Then
    shortcut.IconLocation = iconFile & ",0"
Else
    ' Fallback to a generic system icon
    shortcut.IconLocation = "%SystemRoot%\System32\SHELL32.dll,14"
End If
shortcut.Save

WScript.Echo "Lucy C2 shortcut created on your desktop.", vbInformation, "Lucy"
