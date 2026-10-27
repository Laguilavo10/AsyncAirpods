# AirPods Sync

🇬🇧 [Read in English](README.md)

Proyecto educativo para acercar lo más posible el cambio automático de los AirPods a Windows:
te pones los AirPods, reproduces algo en la PC y se conectan solos.
Das doble toque atrás del iPhone y vuelven a él.

## Uso diario

| Quieres usar | Haces | Qué pasa |
|---|---|---|
| **PC** | Nada: te pones los AirPods y la PC suena | Tras 2 s de sonido se conectan en ~1.5–4 s |
| **iPhone** | Doble toque atrás del iPhone ([atajo](#atajo-del-iphone)) | Vuelven al iPhone y la PC **no los recupera** |
| **Control manual** | Ícono en la bandeja junto al reloj, o **Ctrl+Alt+A** | Ver el estado, cambiar a mano, pausar el cambio automático |

Colores del ícono: **verde** = en esta PC · **azul** = conectando (un intento a la vez:
los clics extra se ignoran, porque cada pedido reinicia la conexión) · **gris** = no están en esta PC ·
**ámbar** = cambio automático pausado o en espera · **rojo** = error (pasa el mouse para ver el detalle).

Menú del ícono: *Use on PC* (también con clic izquierdo) · *Release* · *Auto-switch* ·
*Pause media on disconnect* · *Notifications* · *Start with Windows* ·
*Open log folder* · versión · *Quit*.

Con *Pause media on disconnect* (activado por defecto), lo que suene en la PC
(Spotify, un video del navegador...) se pausa cuando los AirPods se van de la PC,
sea como sea, para que no siga por los altavoces. Es una pausa real, no la tecla
Play/Pausa, así que si no sonaba nada no empieza a sonar nada.

**Ctrl+Alt+A** funciona desde cualquier programa: hace *Use on PC* si los AirPods
están en otro lado y *Release* si están en esta PC. Si otro programa ya usa esa
combinación, el menú no muestra la pista y el log lo indica.

Las notificaciones de Windows avisan cuando los AirPods se conectan, se van de la
PC o no se pueden conectar. Se apagan con *Notifications*; la elección se guarda en
`%LOCALAPPDATA%\AirPodsSync\preferences.json`.

### Al iniciar

El ícono arranca **inactivo** (color ámbar): abrirlo o prender la PC nunca te quita
los AirPods. El cambio automático empieza después de tu primer *Use on PC*.
Pasa el mouse por el ícono para ver qué está esperando y las cuentas regresivas.

### La regla de respeto

Si los AirPods se van de la PC sin que la PC lo pida (el iPhone los reclamó, elegiste
*Release* o los guardaste en el estuche), el cambio automático **se queda en espera** para
no quitártelos mientras la PC siga sonando. Se reanuda cuando la PC pasa **15 s en
silencio**, cuando **llevas 60 s sin tener puestos los AirPods** (ponértelos de nuevo es
empezar de cero), o de inmediato si eliges *Use on PC*.

Si una conexión no se completa en 20 s, el ícono se pone rojo y explica por qué
(normalmente los AirPods están en el estuche cerrado o fuera de alcance).

### Atajo del iPhone

1. App **Atajos** → **+** → **Agregar acción** → **Establecer destino de reproducción**.
2. Toca **iPhone** en la acción y elige tus **AirPods**. Llámalo "AirPods al iPhone".
3. **Configuración → Accesibilidad → Tocar → Tocar atrás → Doble toque** → elige el atajo.

También se puede asignar al botón de Acción, a un widget o a Siri.

## Cómo funciona

1. **Leer los AirPods (BLE).** Los AirPods emiten constantemente anuncios Bluetooth
   Low Energy con su batería, si están en el oído y el estado del estuche.
   Cualquier dispositivo cercano puede leerlos **sin conectarse**.
2. **Detectar audio en la PC.** El medidor de picos de Windows Core Audio indica
   si el dispositivo de salida predeterminado está sonando.
3. **Conectar.** Cada salida de audio Bluetooth tiene detrás un filtro del driver
   de audio Bluetooth de Windows que acepta una orden puntual de *reconectar* /
   *desconectar* (`KSPROPSETID_BtAudio`), el mismo método que usa ToothTray.
4. **Regla de cambio automático.** Si tienes puestos los AirPods (en el oído y cerca
   de la PC), la PC lleva 2 segundos sonando, aún no están conectados y no hay
   espera activa, se le pide a Windows que los conecte.

La PC no puede entregarle los AirPods al iPhone: al desconectarlos solo quedan
libres. Volver al iPhone siempre empieza en el iPhone.

## Instalación

Requiere Windows 10/11 y Python 3.10 o superior.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
airpods-sync startup on     # iniciar el ícono de la bandeja con Windows
```

### .exe independiente

Para usarlo en otro PC sin Python:

```powershell
pip install -e ".[build]"
python packaging\build_exe.py
```

Esto crea `dist\AirPodsSync.exe`, un único archivo sin ventana de consola que
abre el ícono de la bandeja. En cualquier PC, ábrelo desde donde esté (Descargas,
un USB) y marca *Start with Windows* en el menú del ícono: el .exe se copia a
`%LOCALAPPDATA%\Programs\AirPodsSync` y registra esa copia, así que puedes borrar
el original. Para actualizarlo, abre el .exe nuevo y vuelve a marcar la opción
(desmárcala antes si ya está marcada); reemplaza la copia instalada.

## Comandos

```powershell
airpods-sync tray           # ícono en la bandeja con cambio automático (lo que inicia con Windows)
airpods-sync auto           # el mismo cambio automático en la terminal (Ctrl+C para detener)
airpods-sync connect        # conectar los AirPods a la PC ahora y medir el tiempo
airpods-sync disconnect     # desconectarlos de la PC
airpods-sync devices        # listar dispositivos de audio Bluetooth emparejados
airpods-sync startup on|off|status
airpods-sync scan           # tabla en vivo de los AirPods cercanos
airpods-sync scan --raw     # bytes de cada paquete por campo, para estudiar el protocolo
pytest                      # ejecutar las pruebas
```

`connect`, `disconnect`, `auto` y `tray` aceptan `--device <parte del nombre>`
(por defecto: `AirPods`). `auto` y `tray` aceptan `--min-rssi` (por defecto `-55`)
para ignorar AirPods más lejanos, como los de otras personas. Además, solo cuentan
los anuncios del mismo modelo que tus AirPods emparejados, que se lee de Windows.

Archivo de log: `%LOCALAPPDATA%\AirPodsSync\logs\airpods-sync.log` (menú del ícono: *Open log folder*). Rota al llegar a 1 MB y guarda 3 archivos anteriores.

### Experimentos con `scan --raw`

Fíjate qué bytes cambian cuando:
- abres o cierras el estuche → `lid`
- sacas un auricular o te lo pones → bits de `status(bin)`
- pones a cargar el estuche → nibble alto de `charge/case`

Si tu modelo aparece como `Unknown (0x....)`, agrega ese código a
`MODEL_NAMES` en `src/airpods_sync/domain/airpods.py`.

## Arquitectura

```
src/airpods_sync/
├── domain/                 Lógica pura, sin E/S
│   ├── airpods.py                  AirPodsStatus, PodStatus, CaseStatus, nombres de modelos
│   └── proximity_pairing.py        Decodificador del mensaje BLE 0x07 de Apple
├── application/            Casos de uso, solo dependen de domain + ports
│   ├── ports.py                    Interfaces: AdvertisementSource, AudioActivityMonitor, HeadsetController
│   ├── tracker.py                  AirPodsTracker: último estado por dispositivo, expiración
│   ├── headsets.py                 find_headset, wait_until_connected
│   ├── auto_switch.py              AutoSwitcher: reglas de conexión y de respeto, comandos manuales
│   └── runner.py                   SwitcherRunner: bucle de escaneo + evaluación, comandos thread-safe
├── infrastructure/         Adaptadores de librerías concretas y APIs de Windows
│   ├── bleak_source.py             Escaneo BLE con bleak
│   ├── core_audio_interfaces.py    Declaraciones COM que no trae pycaw
│   ├── windows_audio.py            Medidor de audio y conexión/desconexión Bluetooth
│   ├── windows_startup.py          Inicio con Windows (clave Run de HKCU, autoinstalación)
│   ├── windows_hotkey.py           Atajo global (RegisterHotKey)
│   ├── windows_media.py            Pausar apps multimedia (controles multimedia del sistema)
│   ├── preferences.py              Preferencias guardadas del ícono (JSON)
│   └── single_instance.py          Mutex con nombre para que solo corra un ícono
├── cli/                    Presentación en terminal
│   ├── main.py                     Punto de entrada y raíz de composición
│   ├── scan.py                     Bucle de escaneo
│   └── render.py                   Renderizado de texto puro
└── tray/                   Presentación en la bandeja del sistema
    ├── app.py                      TrayApp: ícono, menú, estado, atajo
    ├── notifications.py            Qué cambios merecen una notificación
    └── icons.py                    Íconos dibujados en tiempo de ejecución
```

Las dependencias solo apuntan hacia adentro (`cli/tray → infrastructure → application → domain`).
La capa de aplicación nunca importa `bleak`, `pycaw`, `comtypes` ni `pystray`, así que
las reglas se prueban con dobles de prueba y los adaptadores se pueden reemplazar.

## Limitaciones

- El formato del mensaje BLE viene de ingeniería inversa de la comunidad, no de Apple.
  Verificado con AirPods Pro 3: modelo `0x2027` (little-endian), bits de oído
  `0x02` = izquierdo y `0x08` = derecho sin importar qué auricular emite.
- Parte del paquete está cifrado y no se puede leer sin las claves de Apple, así que
  no se puede saber con certeza qué anuncio BLE corresponde a tus AirPods emparejados.
  Se usan el modelo y la intensidad de la señal (`--min-rssi`): alguien con el mismo
  modelo sentado justo a tu lado aún puede contar como tú. El color no ayuda: los
  Pro 3 solo se venden en blanco (byte de color `00`).
- Para conectar hay que pedírselo a los dos filtros del driver (estéreo y manos libres):
  pidiéndoselo solo al estéreo tardaba 8–11 s; a los dos juntos, 1.5–4 s, igual que el
  botón "Conectar" de Windows.
- Si el botón "Conectar" de Windows también deja de funcionar, el emparejamiento está
  dañado: quita los AirPods de Windows y vuelve a emparejarlos.
