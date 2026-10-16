' Watchdog launcher - window style 0 = tanpa flash; router.cmd bg jalan tersembunyi.
' Path root diambil dari lokasi file ini sendiri -> portable ke mesin mana pun.
Dim root
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
CreateObject("Wscript.Shell").Run """" & root & "\router.cmd"" bg", 0, False
