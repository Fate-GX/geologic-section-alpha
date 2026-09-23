Option Explicit
Dim fs, sh, base, python, command
Set fs = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
base = fs.GetParentFolderName(WScript.ScriptFullName)
python = base & "\.venv\Scripts\pythonw.exe"
If fs.FileExists(python) Then
  command = Chr(34) & python & Chr(34)
Else
  command = "pyw.exe -3"
End If
On Error Resume Next
sh.Run command & " " & Chr(34) & base & "\tools\launch_gui.pyw" & Chr(34), 1, False
If Err.Number <> 0 Then
  MsgBox "Install Python 3.11+ with Tkinter and the Windows Python launcher, then try again.", 16, "Geologic Section Alpha"
End If
