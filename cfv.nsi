; This is a NSIS installer script.  See http://nsis.sourceforge.net/

!define VER 1.18.3

Name "cfv"

Outfile "cfv-${VER}.exe"

; usa LZMA (7zip) compression, about 20% smaller
SetCompressor lzma

; The default installation directory
InstallDir $PROGRAMFILES\cfv

ShowInstDetails show
;hmm
ShowUninstDetails show

; The text to prompt the user to choose components
ComponentText "This will install cfv ${VER} onto your computer.  For typical usage you will want cfv available in your PATH.  Therefore, it is recommended that you choose the option to create a cfv.bat in your windows directory."

; The text to prompt the user to enter a directory
DirText "Choose a directory to install in to:"


Section "exe and support files (required)"
  SectionIn RO

  SetOutPath $INSTDIR

  File dist\cfv.exe
  File dist\library.zip
  File dist\*.pyd
  File dist\*.dll

  ; Write the installation path into the registry
  ;WriteRegStr HKLM SOFTWARE\cfv "Install_Dir" "$INSTDIR"
  
  ; Write the uninstall keys for Windows
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\cfv" "DisplayName" "cfv ${VER} (remove only)"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\cfv" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteUninstaller "uninstall.exe"

SectionEnd


Section "documentation"
  SetOutPath $INSTDIR

  File cfv.txt
  File Changelog.txt
  File COPYING.txt

SectionEnd


Section "$WINDIR\cfv.bat file"
  DetailPrint "Creating batch file: $WINDIR\cfv.bat"

  FileOpen $1 $WINDIR\cfv.bat w
  FileWrite $1 "@echo off$\r$\n" 
  FileWrite $1 "$\"" 
  FileWrite $1 $INSTDIR
  FileWrite $1 "\cfv.exe$\" "

  ; we want to use %* in the .bat file, but it doesn't exist on win 9x/ME
  ReadRegStr $2 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" CurrentVersion
  IfErrors 0 lbl_winnt
  ; we are not NT.
  FileWrite $1 "%1 %2 %3 %4 %5 %6 %7 %8 %9$\r$\n"
  Goto lbl_done
lbl_winnt:
  FileWrite $1 "%*$\r$\n"
lbl_done:

  FileClose $1
SectionEnd


;--------------------------------

; Uninstaller

UninstallText "This will remove cfv from your computer. Hit the uninstall button if you wish to continue."

; Uninstall section

Section "Uninstall"
  
  ; remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\cfv"
  ;DeleteRegKey HKLM SOFTWARE\cfv

  ; remove files
  Delete $INSTDIR\cfv.exe
  Delete $INSTDIR\library.zip
  Delete $INSTDIR\*.dll
  Delete $INSTDIR\*.pyd
  
  Delete $INSTDIR\cfv.txt
  Delete $INSTDIR\Changelog.txt
  Delete $INSTDIR\COPYING.txt
  
  ; remove generated .bat file
  Delete $WINDIR\cfv.bat
  
  ; remove uninstaller
  Delete $INSTDIR\uninstall.exe

  ; remove shortcuts, if any
  ;Delete "$SMPROGRAMS\cfv\*.*"

  ; remove directories used
  ;RMDir "$SMPROGRAMS\cfv"
  RMDir "$INSTDIR"

SectionEnd

