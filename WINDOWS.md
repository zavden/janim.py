# Janim (Python) en Windows 11 · sugerencias para el agente

Escrito el 2026-10-21 en el Mac M1 donde se acaba de terminar el port a macOS
(`MACOS.md`), **sin probar nada en Windows**. Son sugerencias, no
instrucciones cerradas: cada punto dice qué espero, dónde mirar y cómo
confirmarlo. Lo que pude comprobar desde aquí (wheels, cabeceras, código)
lleva la marca «comprobado». Si algo resulta falso, corrígelo en este fichero
y di que lo estaba.

El repo hermano, Janim.jl, tiene su propio `WINDOWS.md`, y en Windows va un
paso por delante: ya elige DX12 y trae wgpu-native para `x86_64-windows`.
Las dos bibliotecas comparten los shaders WGSL y la versión mayor de
wgpu-native (v24), así que lo que aprendas en una sirve para la otra. Lee
también el `MACOS.md` de este repo: el port a macOS es el precedente y casi
todo lo que tocó (backend, plataforma de GLFW, fuentes) se vuelve a tocar
aquí, en el mismo sitio.

## Resultado · 2026-10-21, Windows 11 Home 25H2, Ryzen 7 9700X, Radeon RX 9070 XT, Python 3.14.9

**El port está casi terminado.** Instalación, DX12, vídeo, fuentes, ventana
en vivo y Python contra Julia, comprobados en esta máquina el 2026-10-21 y
la madrugada del 22. Faltan: probar a mano las teclas y el ratón de la
ventana (§7), el §6 (`-p` y lo demás escrito para Unix) y la comparación de
frames en Linux y macOS que pide el §0, porque un shader común cambió. Todo
está en la rama `testing-windows`.

- **§1 · Preparar.** Python llegó con uv (`uv python install 3.14`), no con
  el instalador de python.org: no hay `py`, y `python` sigue siendo el atajo
  de la Store. ffmpeg 9.0.2 y MiKTeX 26.5 (`latex`, `dvisvgm` 3.6,
  `AutoInstall=1`) con winget. Git 2.56 ya estaba, con `core.autocrlf=true`:
  los dos primeros clones salieron con CRLF, como se preveía. DejaVu 2.37 y
  Liberation 2.1.5 instaladas para el usuario
  (`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, registradas en HKCU).
- **§2 · Instalar.** Confirmado: las wheels existen (wgpu-native 24.0.0.2 en
  la de wgpu) y `import wgpu` pasa `NATIVE_VERSION`. Hecho lo sugerido: la
  parte de Python del bootstrap vive en `scripts/bootstrap.py`;
  `bootstrap.sh` lo llama igual que antes y `scripts/bootstrap.cmd` lo llama
  tras crear el venv con `py -3.14`, con `uv venv --seed` o con
  `python3.14`. **Dos cosas no previstas:** el `python3.14.exe` que deja uv
  es un lanzador y `venv` no puede copiarlo (`ensurepip` falla), de ahí la
  rama de uv; y pip falla con `[Errno 2]` dentro de rutas largas (el `numpy`
  de la wheel pasa de MAX_PATH): un clon a dos o tres carpetas de la raíz no
  lo sufre. `bin/janim.cmd` hace de `bin/janim` y PowerShell lo encuentra
  como `bin\janim`. El `.gitattributes` (`bin/janim` y `*.sh` LF, `*.cmd`
  CRLF) cierra el CRLF para quien clone con `autocrlf=true`. **Falso:** que
  lo primero en fallar fuese el backend. Lo primero fue
  `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81` al leer
  `stencil.wgsl`: `read_text()` sin `encoding` usa cp1252 en Windows (Python
  3.14 aún no trae UTF-8 por defecto; llega en 3.15) y los shaders llevan
  `──`. Arreglado con `encoding="utf-8"` en los nueve `read_text` y
  `write_text` que no lo decían (`pipelines.py`, `compositor.py`,
  `triangle.py`, `window.py`, `core/model.py`, `scene/scene.py`,
  `text/tex.py`).
- **§3 · DX12.** Hecho: `BACKEND = {"darwin": "Metal", "win32":
  "DX12"}.get(sys.platform, "Vulkan")` en `context.py`, y las dos tablas de
  `native.py` ganan `DX12` (`1 << 3`, `WGPUBackendType_D3D12`). Antes del
  cambio, con Vulkan sobre el driver de AMD (26.10.1, LLPC), la primera
  `create_render_pipeline` moría con un *access violation* dentro de
  wgpu-native, sin nada en `JANIM_WGPU_LOG=info`: Vulkan en Windows no es una
  opción con este driver. **§3.3, confirmado:** `JANIM_HEADLESS=1` funciona:
  WARP sale como «Microsoft Basic Render Driver», tipo `cpu`, y da otros
  bytes que la GPU. **§3.4, falso:** DX12 no da el nombre del vendedor.
  wgpu-native pone en `vendor` la versión del driver («32.0.32015.7029») y
  deja `description` vacía, así que el slug es `320320157029` (WARP:
  `100261009711`, la build de Windows) y la versión `unknown`. No rompe
  nada, pero el slug cambia con cada driver; si importa, derivarlo de
  `vendor_id` (0x1002 AMD, 0x10DE NVIDIA, 0x8086 Intel, 0x1414 Microsoft).
  **Lo que FXC no compila:** `effects.wgsl` escribía `grille[col] = 1.0`,
  una componente de `vec3` con índice dinámico, y la demo 06 (efecto CRT)
  moría con `X3500: array reference cannot be used as an l-value`. Era la
  única escritura así en los shaders; ahora es un `select` con el mismo
  valor, en las dos bibliotecas. Las doce demos a 1280×720 y 60 fps salen
  (la 12 pide la fuente «Fredoka Expanded», no instalada), y en Python las
  04 y 07 tardan 50 s frente a 11 y 9 en Julia: CPU, no GPU.
- **§4 · Vídeo.** Confirmado el fallo (`WinError 10038` en `video.py:290`) y
  hecho el arreglo mínimo: en `win32` no hay `select`, se escribe sobre el
  pipe no bloqueante y se duerme 1 ms cuando `BlockingIOError` dice que está
  lleno. `finish` valía tal cual. **La granja `-j 2`** funciona sin tocar
  `concat_listing`: las rutas van entre comillas simples y el demuxer no
  interpreta la `\` dentro de ellas.
- **§5 · Fuentes.** Hecho: `_font_catalog` gana la rama `win32` con las dos
  carpetas de BaseDirs, en su orden (la del sistema y la del usuario), sin
  recursión. «DejaVu Sans» resuelve a `DejaVuSans.ttf` del usuario entre 374
  caras, y el frame sale byte a byte igual que con
  `FREETYPE_ABSTRACTION_FONT_PATH`.
- **§6 · Lo demás.** Sin empezar (`-p`, `open_output`).
- **§7 · La ventana.** Hecha con lo previsto: `native_handles` devuelve el
  HWND y wgpu-py monta la `WGPUSurfaceSourceWindowsHWND`; `create_window`
  acepta `win32`; `JANIM_GLFW_PLATFORM` admite `win32` o `null`. **No
  previsto:** `_headless_env` tomaba Windows por headless (no hay `DISPLAY`)
  y GLFW arrancaba en Null; ahora Win32 cuenta como macOS. La superficie
  ofrece `bgra8unorm-srgb` primero (se usa `bgra8unorm`), mailbox, Fifo e
  Immediate, y CopySrc; `framebuffer_size` es `(854, 480)` para una ventana
  de 854×480. El bucle en vivo con `03_portals` a 15 fps presentó 69 frames
  en 5 s sin reconfigurar. **Sin probar a mano:** teclas, ratón y dos
  previews seguidas.
- **§8 · Python contra Julia.** Hecho con los dos arneses del `MACOS.md` de
  Janim.jl, a 640×360 y 10 fps, un proceso por render: las cinco demos dan
  frames **idénticos byte a byte** en DX12 (140, 140, 180, 141 y 220).
- **Lo que no cambió:** `live.py`, `cli.py`, `bin/janim`.

## 0 · Reglas de trabajo

- **El objetivo** es que en un Windows 11 funcionen el render a fichero, la
  CLI `bin/janim` y la ventana en vivo, con la GPU de la máquina.
- **Linux y macOS no pueden cambiar.** Todo lo específico de Windows va dentro
  de `sys.platform == "win32"`, y en Linux y en macOS el código que corre y los
  frames que salen deben ser los mismos que hoy. Al volver a esas máquinas, se
  repite allí la comparación de frames contra la versión anterior.
- **No hay frames de referencia en el repo.** En DX12 muchos bordes cambiarán
  un píxel respecto a Linux y a Metal, así que una diferencia de bytes no es
  un fallo. Lo que hay que buscar es que algo se vea MAL. Las escenas se
  miran; un exit 0 no dice nada de lo que hay en pantalla.
- **Commits solo con permiso de Alex, y nunca push.** Un commit por arreglo,
  en español, que explique el porqué. Ninguna dependencia nueva sin preguntar;
  de las wheels no espero ninguna (§2). Solo texto y SVG en git.
- **El orden que sugiero:**
  1. Instalar (§1, §2): el bootstrap y el lanzador no saben de `Scripts\`.
  2. Que la instancia elija DX12 (§3).
  3. Arreglar el escritor de vídeo, que usa `select` sobre un pipe (§4).
  4. Renderizar a fichero una escena simple; luego fórmulas, capas y 3D.
  5. Fuentes (§5) y el resto de lo escrito para Unix (§6).
  6. Dejar la ventana en vivo para el final (§7).
  7. Python contra Julia en la misma máquina (§8).

## 1 · Preparar el Windows

- **Windows 11** (o Windows 10 con DX12). La GPU necesita un driver WDDM con
  Direct3D 12; cualquier GPU de la última década lo tiene. Sin GPU, DX12 ofrece
  WARP, el rasterizador por software de Microsoft (§3).
- **Python 3.14**: el instalador de python.org o `winget install
  Python.Python.3.14`, con el lanzador `py`. Comprueba `py -3.14 --version`.
- **Git for Windows**, por su Git Bash: `scripts/bootstrap.sh` y `bin/janim`
  son bash. Ojo con `core.autocrlf`: si está en `true` (el valor por defecto
  del instalador), los scripts salen con CRLF y bash muere con
  `$'\r': command not found`. Ver §2.
- **ffmpeg** en el `PATH`: `winget install Gyan.FFmpeg` (o chocolatey,
  scoop). Janim lo llama por nombre, `ffmpeg`/`ffprobe`; `shutil.which`
  encuentra los `.exe`.
- **Fuentes:** DejaVu no viene con Windows. Descárgala de
  dejavu-fonts.github.io e instálala «para todos los usuarios» (va a
  `C:\Windows\Fonts`) o solo para ti (va a
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts`). Las dos carpetas se recorren
  (§5). Algunas lecciones piden «Liberation Serif» y «Liberation Mono».
- **LaTeX, opcional, para `Tex`/`MathTex`:** MiKTeX (trae `dvisvgm`) o TeX
  Live. `latex.exe` y `dvisvgm.exe` en el `PATH`. En MiKTeX, pon la
  instalación de paquetes que falten en «siempre», o el primer `Tex` se queda
  esperando un diálogo que nadie ve.
- **Windows Terminal**: la barra de progreso usa secuencias ANSI
  (`\r\033[K`), que el conhost viejo no entiende.

## 2 · Instalar: lo que va a fallar antes de empezar

Comprobado desde el Mac con `pip download --platform win_amd64
--python-version 3.14 --only-binary=:all: --no-deps`: **existen wheels de
Windows x86-64 para todas** las versiones fijadas en `pyproject.toml`, y
ninguna declara una dependencia solo de Windows (la única marca de plataforma
en los metadatos de wgpu es `rubicon-objc; sys_platform == 'darwin'`). Lo que
traen de nativo:

| paquete | qué trae para Windows |
|---|---|
| `wgpu==0.21.0` | `wgpu/resources/wgpu_native-release.dll` (7,8 MB), wgpu-native v24; `NATIVE_VERSION = (24, 0)` en `context.py` debería pasar |
| `glfw==2.10.2` | `glfw/glfw3.dll` y `glfw/msvcr120.dll` |
| `freetype-py==2.5.1` | `freetype/libfreetype.dll` |
| `numpy==2.4.6` | `cp314-win_amd64` |
| `cffi==2.1.1` | `cp314-win_amd64` |

`wgpu_native-release.dll` está compilada con MSVC; necesita el runtime de
Visual C++ (`vcruntime140.dll`), que Windows 11 ya trae. Si `import wgpu`
dice que falta una DLL, instala «Microsoft Visual C++ Redistributable».

**Lo que va a fallar:**

1. **`scripts/bootstrap.sh`** llama a `python3.14`, que en Windows no existe
   (es `py -3.14` o `python`), y crea el venv esperando
   `.venv/bin/python`, que en Windows es `.venv\Scripts\python.exe`. **`bin/janim`**
   usa la misma ruta. Lo que sugiero, sin tocar lo que Linux hace hoy:
   - mover la parte de Python del bootstrap (el heredoc: pip con
     `--only-binary=:all: --no-deps` sobre las versiones de `pyproject.toml` y
     el `janim.pth`) a `scripts/bootstrap.py`, de modo que `bootstrap.sh` lo
     llame y un `scripts/bootstrap.cmd` nuevo haga lo mismo con
     `py -3.14 -m venv .venv` y `.venv\Scripts\python.exe scripts\bootstrap.py`;
   - un `bin/janim.cmd` de cuatro líneas que use `.venv\Scripts\python.exe`
     si existe y `py -3.14` si no, y haga `-m janim.cli %*`.
   Alternativa menor: que los dos scripts bash detecten `.venv/Scripts/python.exe`
   para quien use Git Bash. La `.pth` va a `Lib\site-packages`:
   `sysconfig.get_path("purelib")` ya lo resuelve.
2. **CRLF.** Con `core.autocrlf=true` los scripts bash se rompen. Añade un
   `.gitattributes` con `* text=auto`, `bin/janim text eol=lf` y
   `scripts/*.sh text eol=lf` (los `.wgsl` y los `.py` no sufren con CRLF,
   pero `eol=lf` para todo el repo es lo más simple). Pide permiso: es un
   fichero nuevo en git.
3. **`PYTHON=... scripts/bootstrap.sh` desde Git Bash:** `python3.14` no
   existe, pero `PYTHON=py` tampoco vale (el lanzador necesita `-3.14`).
   Esto es lo que resuelve el `.cmd`.

Después:

```bat
scripts\bootstrap.cmd
.venv\Scripts\python.exe -c "import janim, wgpu; print(wgpu.__version__)"
```

## 3 · Que la instancia elija DX12 (lo primero que fallará al renderizar)

1. **El backend.** `context.BACKEND` dice «Metal» en darwin y «Vulkan» en el
   resto; en `win32` debe decir «DX12», porque Janim.jl elige DX12 en Windows
   (`src/backend/wgpu/context.jl:242`, `_instance_backends`) y la comparación
   del §8 exige el mismo backend en las dos. Vulkan existe en Windows, pero
   DX12 es la ruta que wgpu prueba más y la que trae WARP. En `native.py`:
   `_INSTANCE_BACKENDS["DX12"] = 1 << 3` (comprobado en `wgpu/resources/wgpu.h`:
   `WGPUInstanceBackend_DX12 = 1 << 3`) y
   `_BACKEND_TYPES["DX12"] = lib.WGPUBackendType_D3D12` (= 4 en `webgpu.h`).
   Los mensajes ya usan `BACKEND`.
2. **El compilador de shaders.** `WGPUInstanceExtras` tiene
   `dx12ShaderCompiler`, `dxilPath` y `dxcPath` (comprobado en `wgpu.h`);
   `native.py` no los toca y Julia pasa `WGPUDx12Compiler_Undefined`, así que
   las dos usan FXC (`d3dcompiler_47.dll`, que viene con Windows). DXC daría
   otra precisión y necesita dos DLL más: no lo cambies, y si lo cambias,
   cámbialo en las dos bibliotecas.
3. **`JANIM_HEADLESS=1` puede FUNCIONAR en Windows.** DX12 enumera WARP
   («Microsoft Basic Render Driver») y wgpu lo reporta como adaptador de tipo
   `CPU`, que es justo lo que `choose_adapter` busca. Compruébalo:
   `JANIM_HEADLESS=1 bin/janim render … -qs` y `gpu_info()`; el slug saldrá
   de `vendor` («Microsoft» → `microsoft`). Si funciona, los README y
   `llms.txt` dejan de poder decir que el modo headless es solo de Linux.
4. **La identidad del driver.** DX12 da nombres de vendedor («NVIDIA»,
   «Advanced Micro Devices, Inc.», «Intel»), así que el slug será `nvidia`,
   `advancedmicrodevicesinc` o `intel`, y `description` la versión del
   driver. Que un nombre nuevo no rompa nada en la cabecera `# driver:`.
5. **Los límites:** en DX12 `min-uniform-buffer-offset-alignment` es 256,
   como en Metal; el código ya lo admite. `float32-filterable` existe.
6. **Un pánico de wgpu-native mata el proceso.** Si muere en seco, repite con
   `JANIM_WGPU_LOG=info` (o `debug`) y mira la última llamada.

Primera prueba (en cuanto el §4 esté hecho):

```bat
bin\janim render examples\tutorial\c1_01_basics\01_how_janim_works.py -ql
```

Luego, en este orden: **fórmulas**
(`examples/tutorial/c1_03_groups_and_text/04_latex.py`), **capas y efectos**
(`examples/demo/03_portals.py`), **3D** (`examples/tutorial/c2_03_camera/03_camera_3d.py`
y `examples/demo/07_text_mask.py`), **partículas y bloom**
(`examples/demo/04_lorenz_glow.py`). Mira el centro de cada Transform, el
primer frame y el último (`bin/janim frame …`).

## 4 · El vídeo: `select` no existe para pipes en Windows

`janim/video.py:290` espera a que el pipe de ffmpeg admita escritura con
`select.select([], [descriptor], [], 0.01)`. En Windows `select` solo acepta
sockets: el primer frame termina en `OSError: [WinError 10038]`. Lo demás del
escritor sí vale: `os.set_blocking(fd, False)` (línea 202) funciona sobre
pipes en Windows desde Python 3.12, `os.write` sobre un pipe no bloqueante
lanza `BlockingIOError` cuando está lleno, y el bucle ya trata ese caso con
`continue`.

- **El arreglo mínimo** que sugiero: en `win32` no llamar a `select` y, en su
  lugar, dormir un milisegundo cuando la escritura no avanza, de modo que el
  bucle no gire en vacío. Es decir, dejar la rama de Linux byte a byte igual y
  añadir una rama `if sys.platform == "win32": time.sleep(0.001)` en el sitio
  del `select`. La alternativa limpia (un hilo escritor con escrituras
  bloqueantes) toca el diseño del escritor; no la hagas sin preguntar.
- **`finish`** (líneas 316-345) no usa `select`: cierra `stdin` y espera con
  `poll`; vale tal cual. `janim/scene/audio.py` usa `subprocess.run`; vale.
- **La granja (`-j`)** lanza `subprocess.Popen([sys.executable, "-c", code])`
  (`scene.py:800`) y pasa las rutas dentro de `code` con `repr`, así que las
  barras invertidas de Windows sobreviven. Lo que hay que mirar es el fichero
  de la lista del `concat` de ffmpeg (`scene.py:741`, «in its own quoting»):
  con rutas `C:\…` conviene escribirlas con `/`, que el demuxer acepta y no
  interpreta como escape.
- **`core/image.py`** llama a `ffprobe`/`ffmpeg` por nombre con
  `subprocess.run`: vale.

## 5 · Fuentes: el catálogo conoce Linux y macOS, no Windows

`janim/text/glyphs.py` (`_font_catalog`) tiene una rama darwin y otra XDG. En
Windows no encontrará nada.

Que imite a FreeTypeAbstraction, como ya hace en las otras dos plataformas.
Comprobado en el código de BaseDirs (`nt.jl`): en Windows `FONTS_DIRS` es

1. la carpeta `Fonts` del sistema, por su «known folder» (`C:\Windows\Fonts`);
2. `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (las fuentes instaladas «solo
   para mí»).

En ese orden, el sistema ANTES que el usuario (al revés que en macOS), y **sin
entrar en subcarpetas**: la recursión de FreeTypeAbstraction es solo para
`Sys.isunix() && !Sys.isapple()`. En Python: `Path(os.environ.get("WINDIR",
r"C:\Windows")) / "Fonts"` y `Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Windows/Fonts"`,
planas. Si el orden o el recorrido difieren, las dos bibliotecas pueden elegir
caras distintas para el mismo nombre y el §8 lo notará.

`C:\Windows\Fonts` tiene muchas `.ttc` (se carga la primera cara, como en
FreeTypeAbstraction) y `.fon` de mapa de bits que FreeType puede abrir con
nombres de familia raros; no molestan al marcador, pero comprueba que
`find_face("DejaVu Sans")` resuelve a `DejaVuSans.ttf` y no a otra cosa.

## 6 · Lo demás que está escrito para Unix

- **GLFW:** `janim/backend/glfw.py`. `LIBRARY` (`/usr/lib64/libglfw.so.3`)
  no existe y se usará el `glfw3.dll` del wheel. `_headless_env` decide «no
  hay pantalla» sin `DISPLAY`: en `win32` cuenta como pantalla, igual que en
  darwin. La tabla de `JANIM_GLFW_PLATFORM` debe ser `null` o `win32`
  (`glfw.PLATFORM_WIN32`, comprobado en pyglfw 2.10.2: `0x00060001`), y los
  nombres (`names`) ganan `"win32"`. `_point_xkb_at_x_locale` no aplica.
- **`-p`:** `cli.py:329` (`open_output`) solo conoce `open` y `xdg-open`; en
  Windows es `os.startfile(path)`.
- **`bin/janim`:** `readlink -f` existe en Git Bash; lo que no existe es
  `.venv/bin/python` (§2).
- **LaTeX:** `tex.py` busca `latex` y `dvisvgm` con `shutil.which`, que
  encuentra los `.exe`; la caché va a `%XDG_CACHE_HOME%` o `~/.cache/janim/tex`,
  que en Windows es `C:\Users\<tú>\.cache\janim\tex`. Vale.
- **Direcciones `C:\x.py:Clase`:** `janim/scene/address.py` corta en el
  ÚLTIMO `:` cuyo lado izquierdo termina en `.py`, así que la letra de unidad
  sobrevive (`C:\…\x.py` no termina en `.py` antes de su `:`). Compruébalo con
  `bin/janim render C:\…\scenes.py:Hello -qs`.
- **`MESA_VK_IGNORE_CONFORMANCE_WARNING`** (`context.py:53`) es inofensivo.
- **Lo que no toca Unix:** `threading`, `time.monotonic`, `Path.home()`,
  `tempfile`, `subprocess`. No hay `fcntl`, `signal`, `fork` ni `setsid` en el
  paquete (comprobado con grep). El único `select` es el del §4.

## 7 · La ventana en vivo: lo que falta escribir

1. **La fuente de la superficie.** `glfw.py` (`native_handles`) devuelve
   Wayland, X11 o Cocoa. Para Win32, devuelve
   `{"platform": "win32", "window": int(glfw.get_win32_window(window.handle))}`
   (comprobado: pyglfw 2.10.2 tiene `get_win32_window`). `native.create_surface`
   se lo pasa a `_helpers.get_surface_id_from_info` de wgpu-py, cuya rama
   `win` ya construye `WGPUSurfaceSourceWindowsHWND` con el `hwnd` y un
   `hinstance` de `GetModuleHandleW` (comprobado en
   `wgpu/backends/wgpu_native/_helpers.py:107-112`). No hay que escribir nada
   de Win32.
2. **`create_window`** (`janim/backend/wgpu/window.py`) acepta `wayland`,
   `x11` y `cocoa`: añade `win32`.
3. **No hay paso Retina.** En Windows GLFW declara el proceso consciente del
   DPI por monitor y, con `GLFW_SCALE_TO_MONITOR` apagado (el valor por
   defecto), la ventana nace con el tamaño pedido en píxeles y
   `framebuffer_size` es igual al tamaño de la ventana. En una pantalla 4K la
   ventana se verá pequeña; no es un fallo. Comprueba que
   `framebuffer_size == (1280, 720)` y que `sync_content_scale` (que es de
   Cocoa) no se llama.
4. **El formato y los modos:** DX12 preferirá `bgra8unorm` o su variante
   sRGB; `plain_format` maneja las dos. Fifo existe. CopySrc suele ofrecerse
   en el swapchain de DX12; si `present_readback` devuelve `None`, es que no,
   y no es un error.
5. **El hilo principal.** Win32 entrega los mensajes de una ventana al hilo
   que la creó: es el principal, como hoy. El playhead (`janim-playhead`) no
   toca GLFW.
6. **Bucles modales.** Arrastrar la ventana por el título mete a Windows en un
   bucle modal que detiene `poll_events` hasta soltar: la preview se congela
   mientras tanto y sigue después. Es normal, no lo «arregles».
7. **El drenaje de foco de Wayland** (`drain_focus`) esconde la ventana antes
   de destruirla; en Cocoa no estorbó. Si en Windows deja la ventana
   parpadeando o tarda, limítalo a Linux.

Prueba con `bin\janim examples\demo\03_portals.py`: teclas (espacio, `,`/`.`,
←/→, `[`/`]`, Esc), ratón, y abrir y cerrar dos previews seguidas.

## 8 · Un instrumento sin Linux: Python contra Julia en el mismo Windows

Es el §7 del `MACOS.md`, y los dos arneses (hashes por frame con `frame_tap`
en Python y `Janim._FRAME_TAP` en Julia) están en el `MACOS.md` de Janim.jl,
§6. En Linux (RADV) y en macOS (Metal) las cinco demos `01_multicam`,
`03_portals`, `04_lorenz_glow`, `07_text_mask` y `11_chase_camera` dan frames
idénticos byte a byte en las dos bibliotecas; en Windows, con las dos en DX12,
deberían seguir coincidiendo entre sí.

**Lo que aprendimos en macOS y que puede repetirse en DX12.** Python fusiona
en un solo `draw_indexed` las mallas consecutivas que comparten pipeline,
bloque de uniformes y textura (`render.py`, `_record_commands`); Julia emite
una llamada por malla. En Metal, el color iluminado que se interpola sobre un
triángulo cambia en el último bit según la llamada que lo lleva, y
`11_chase_camera` (tres `Torus` consecutivos) difería en los 220 frames
mientras las otras cuatro coincidían. El arreglo fue
`_MERGE_MESH_DRAWS = BACKEND != "Metal"`. Si en Windows pasa lo mismo (la 11
difiere, las otras cuatro no, y la diferencia está en los píxeles de los
toros), haz `_MERGE_MESH_DRAWS = BACKEND not in ("Metal", "DX12")`, vuelve a
medir y comprueba que las otras cuatro no cambian ni un byte. Si difieren más
demos, mira primero las fuentes (§5) y luego el compilador de shaders (§3.2).

**Determinismo:** la misma escena en dos procesos de la misma máquina debe
dar los mismos frames. Compruébalo con un par de escenas, y con WARP si el
§3.3 funciona (WARP es determinista y no depende de la GPU).

## 9 · Lo que no es un problema de Windows

- **El desenfoque de movimiento en vídeo no existe** en ninguna plataforma:
  `Scene` no acepta `motion_blur` y la CLI rechaza `--motion-blur`. Las demos
  10 y 12 y las lecciones de `c3_05_motion_blur` lo describen y fallan igual
  en Linux y en macOS.
- **`c2_05_from_manim/01_from_manim_ce.py` dice que `-ql` no existe**, pero
  la CLI sí lo tiene.
- **Las lecciones que piden Liberation** dan `FontNotFound` si la familia no
  está instalada: es a propósito.

## 10 · WSL2 es un atajo, no el port

La versión de Linux corre tal cual en WSL2 (Ubuntu) con lavapipe
(`JANIM_HEADLESS=1`) y, con WSLg, abre la ventana en Wayland. La GPU por
Vulkan dentro de WSL2 depende del driver `dzn` de Mesa (Vulkan sobre D3D12),
experimental. Sirve para comparar y para desatascarse, no es el objetivo de
este fichero: el objetivo es Windows nativo con DX12.

## 11 · Al terminar

Deja aquí, en este fichero, lo que confirmaste y lo que resultó falso (como
hace el `MACOS.md`, con una sección de resultados al principio), y en la
sección «Known limitations» de los dos README cambia «Linux y macOS» por lo
que de verdad funcione, con la versión de Windows y la GPU en que se probó.
