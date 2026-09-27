Option Explicit
Dim fso, shell, folder, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & "D:\python\pythonw.exe" & Chr(34) & " " & _
          Chr(34) & folder & "\qqreader_gui.py" & Chr(34)
shell.Run command, 0, False
