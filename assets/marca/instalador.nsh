; Dónde se instala Matcher por defecto.
;
; PEDIDO DEL DUEÑO: que la instalación NO vaya al disco C por defecto.
;
; Sin esto, electron-builder con `perMachine: false` propone
; %LOCALAPPDATA%\Programs\Matcher, que está en C: siempre. Este script corre
; antes de que el instalador calcule esa ruta y, si encuentra un disco de datos
; usable, propone ese en su lugar.
;
; TRES COSAS QUE NO SE TOCAN, PORQUE CADA UNA ROMPE LA INSTALACIÓN DE ALGUIEN:
;
; 1. **C: es el respaldo, no una opción a evitar a toda costa.** La enorme
;    mayoría de las máquinas con Windows tienen un solo disco. Si no hay otro,
;    el instalador tiene que instalar igual en C: — un instalador que se planta
;    porque no encontró un disco D no instala en el 80% de las computadoras.
;
; 2. **Sólo discos FIJOS.** `GetDrives "HDD"` deja afuera pendrives, unidades
;    de red y lectores. Instalar el programa en un pendrive que mañana no está
;    es dejar un acceso directo que abre un error, y un desinstalador que no
;    puede desinstalar.
;
; 3. **Se prueba a escribir antes de elegir.** Un disco montado puede estar
;    lleno, ser de sólo lectura o tener permisos que este usuario no tiene
;    (acá no hay administrador: `perMachine: false` a propósito, para que la
;    gente pueda instalar en una máquina del trabajo). Proponer una carpeta
;    donde el instalador va a fallar es peor que proponer C:. Por eso se crea
;    la carpeta y se escribe un archivo de prueba; recién si eso sale bien se
;    propone el disco.
;
; Y el usuario siempre puede cambiarlo en pantalla:
; `allowToChangeInstallationDirectory` está en `true` en electron-builder.yml.
; Esto decide lo que viene PROPUESTO, no lo que se impone.

!include "FileFunc.nsh"
!include "LogicLib.nsh"

Var MatcherDisco
Var MatcherLibre

; Se llama una vez por cada disco fijo. Elige el que más espacio libre tenga.
Function MatcherMirarDisco
  ; $9 lo pone GetDrives con la unidad ("D:\"). $8 trae el tipo.
  StrCpy $R0 $9 1

  ; El disco del sistema es justamente el que el dueño no quiere: se saltea.
  ; La letra del sistema se lee de $WINDIR y no se cablea "C": en una máquina
  ; con Windows instalado en otra letra, cablear C la daría por buena.
  StrCpy $R2 $WINDIR 1
  ${If} $R0 == $R2
    Push $0
    Return
  ${EndIf}

  ${DriveSpace} $9 "/D=F /S=M" $R1   ; libre, en MB
  ${If} $R1 > $MatcherLibre
    StrCpy $MatcherLibre $R1
    StrCpy $MatcherDisco $R0
  ${EndIf}
  Push $0
FunctionEnd

!macro preInit
  StrCpy $MatcherDisco ""
  StrCpy $MatcherLibre 0

  SetRegView 64
  ReadRegStr $R9 HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation"

  ; Si ya hay una instalación, MANDA la carpeta que eligió el usuario esa vez.
  ; Pisarla en una actualización le movería el programa de lugar sin avisar y
  ; dejaría la instalación vieja tirada ocupando disco.
  ${If} $R9 == ""
    ${GetDrives} "HDD" "MatcherMirarDisco"

    ; 1024 MB de margen: el programa pesa ~200 MB instalado y un disco al borde
    ; de llenarse es un disco donde la instalación falla a mitad de camino.
    ${If} $MatcherDisco != ""
    ${AndIf} $MatcherLibre > 1024
      StrCpy $R8 "$MatcherDisco:\Matcher"

      ; Prueba de escritura de verdad. Que el disco exista y tenga lugar no
      ; quiere decir que este usuario pueda escribir en él.
      CreateDirectory "$R8"
      ClearErrors
      FileOpen $R7 "$R8\.matcher-prueba" w
      ${IfNot} ${Errors}
        FileClose $R7
        Delete "$R8\.matcher-prueba"
        ; Las dos vistas del registro: el instalador puede correr en 32 o en 64
        ; bits según la máquina, y cada una lee la suya. Escribir sólo una deja
        ; la propuesta a medias en la mitad de las computadoras.
        WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation" "$R8"
        SetRegView 32
        WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation" "$R8"
        SetRegView 64
      ${EndIf}
      ; Si la carpeta quedó vacía porque no se pudo escribir, no se deja
      ; basura: RMDir sin /r sólo borra si está vacía, así que una instalación
      ; anterior con archivos adentro no corre riesgo.
      RMDir "$R8"
    ${EndIf}
  ${EndIf}
!macroend
