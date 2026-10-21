# Janim (Python) en macOS (Apple Silicon) · sugerencias para el agente

Escrito el 2026-10-21 en la máquina Linux de desarrollo (RADV, Fedora), **sin
probar nada en un Mac**. Son sugerencias, no instrucciones cerradas: cada punto
dice qué espero, dónde mirar y cómo confirmarlo. Si una resulta falsa,
corrígela aquí mismo y di que lo estaba.

El repo hermano, Janim.jl, tiene su propio `MACOS.md`, y en macOS va un paso
por delante: ya elige Metal. Las dos bibliotecas comparten los shaders WGSL y
la versión mayor de wgpu-native (v24), así que lo que aprendas en una sirve
para la otra. Si tienes los dos clones, lee también ese fichero.

## 0 · Reglas de trabajo

- **El objetivo** es que en un M1 funcionen el render a fichero, la CLI
  `bin/janim` y la ventana en vivo.
- **Linux no puede cambiar.** Todo lo específico de macOS va dentro de
  `sys.platform == "darwin"`, y en Linux el código que corre y los frames que
  salen deben ser los mismos que hoy. Al volver a la máquina Linux, se repite
  allí la comparación de frames contra la versión anterior.
- **No hay frames de referencia en el repo.** En Metal muchos bordes cambiarán
  un píxel respecto a Linux, así que una diferencia de bytes no es un fallo.
  Lo que hay que buscar es que algo se vea MAL. Las escenas se miran; un exit 0
  no dice nada de lo que hay en pantalla.
- **Commits solo con permiso de Alex, y nunca push.** Un commit por arreglo,
  en español, que explique el porqué. Ninguna dependencia nueva sin preguntar:
  la única que hace falta seguro es `rubicon-objc` (§2), y también se
  pregunta. Solo texto y SVG en git.
- **El orden que sugiero:**
  1. Instalar.
  2. Que la instancia elija Metal.
  3. Renderizar a fichero una escena simple.
  4. Probar fórmulas, capas y 3D.
  5. Dejar la ventana en vivo para el final.

## 1 · Preparar el Mac

- **macOS 14 o posterior**: el wheel de `numpy==2.4.6` para cp314 arm64 es
  `macosx_14_0`.
- **Python 3.14**: `brew install python@3.14`, o el instalador de python.org.
- **ffmpeg** en el `PATH`: `brew install ffmpeg`. Janim lo llama por nombre,
  `ffmpeg`/`ffprobe`.
- **Fuentes:** `brew install --cask font-dejavu`, que las deja en
  `~/Library/Fonts`. Los ejemplos piden DejaVu Sans, y una familia que falta es
  un `FontNotFound` a propósito, no un sustituto silencioso.
- **LaTeX, opcional, para `Tex`/`MathTex`:** MacTeX o BasicTeX, más `dvisvgm`,
  en `/Library/TeX/texbin`. Comprueba que esa carpeta está en el `PATH` del
  proceso, no solo en el de la terminal.

## 2 · Instalar: un arreglo seguro antes de empezar

`scripts/bootstrap.sh` instala con `--only-binary=:all: --no-deps` las
versiones fijadas de `pyproject.toml`. Comprobado desde Linux con
`pip download --platform macosx_14_0_arm64 --python-version 3.14`: **existen
wheels de macOS arm64 para todas**. Las que llevan código nativo:

| paquete | qué trae para macOS |
|---|---|
| `wgpu==0.21.0` | `wgpu/resources/libwgpu_native-release.dylib`, wgpu-native **v24.0.0.2**, la misma versión que el wheel de Linux, así que `NATIVE_VERSION = (24, 0)` en `janim/backend/wgpu/context.py` pasa |
| `glfw==2.10.2` | `glfw/libglfw.3.dylib` |
| `freetype-py==2.5.1` | wheel `universal2` |
| `cffi==2.1.1` | `cp314 macosx_11_0_arm64` |

**Lo que va a fallar:** el `METADATA` de wgpu 0.21.0 declara
`rubicon-objc>=0.4.1; sys_platform == 'darwin'`, y
`wgpu/backends/wgpu_native/_helpers.py:33` lo importa al cargar el módulo en
macOS. Con `--no-deps` no se instala, así que `import wgpu` fallará.

- **El arreglo** que sugiero (dependencia nueva: pide permiso a Alex) es
  añadir `"rubicon-objc==0.5.7; sys_platform == 'darwin'"` a
  `[tool.janim.bootstrap] dependencies` en `pyproject.toml`. Es un wheel
  `py3-none-any`, y pip respeta el marcador, así que en Linux no cambia nada.
- **Después:**

  ```bash
  PYTHON=python3.14 scripts/bootstrap.sh
  .venv/bin/python -c "import janim, wgpu; print(wgpu.__version__)"
  ```

## 3 · Que la instancia elija Metal (lo primero que fallará al renderizar)

1. **La instancia se crea SOLO con Vulkan**:
   `janim/backend/wgpu/native.py:62-64` (`extras.backends = 1 << 0`).
   - En `wgpu.h`: Vulkan es `1 << 0`, GL `1 << 1`, Metal `1 << 2` y DX12
     `1 << 3`. Compruébalo en `wgpu/resources/wgpu.h`.
   - Julia ya lo hace en `src/backend/wgpu/context.jl:242`, con Metal en macOS.
     Copia esa regla, dentro de `sys.platform == "darwin"`.
2. **`_adapter_information` rechaza todo lo que no sea Vulkan**
   (`native.py:77`) y escribe `backend_type="Vulkan"` fijo (`:89`). Acepta
   `lib.WGPUBackendType_Metal` en macOS y pon el nombre real.
3. **Mensajes que dicen «Vulkan»:** `native.py:49`, `:69` y
   `janim/backend/wgpu/context.py:1` y `:110`. Que digan el backend de verdad.
4. **`JANIM_HEADLESS=1` no funciona en macOS.** Pide el adaptador de CPU de
   Mesa (lavapipe), que en macOS no existe. `choose_adapter`
   (`context.py:103-125`) ya da un error con la lista de adaptadores, y es el
   comportamiento correcto. Sin la variable, elige la GPU integrada del M1.
5. **Los límites del dispositivo:** `native.py:226-227` pide las alineaciones
   del adaptador, y `uniforms.py:154` las usa. En Metal pueden ser 256, no 32;
   el código ya lo admite. `float32-filterable` se pide solo si existe.
6. **Un pánico de wgpu-native mata el proceso de Python.** Si muere en seco,
   repite con `JANIM_WGPU_LOG=info` (o `debug`) y mira la última llamada.

Primera prueba:

```bash
bin/janim render examples/tutorial/c1_01_basics/01_how_janim_works.py -ql
```

Luego, en este orden:

- **Fórmulas:** `examples/tutorial/c1_03_groups_and_text/`.
- **Capas y efectos:** `examples/demo/03_portals.py`.
- **3D:** `examples/tutorial/c2_03_camera/` y `examples/demo/07_text_mask.py`.

Mira el centro de cada Transform, el primer frame y el último
(`bin/janim frame …`).

## 4 · Fuentes: el catálogo solo conoce las carpetas de Linux

`janim/text/glyphs.py:27-45` (`_font_catalog`) recorre las raíces XDG de Unix.
En macOS no encontrará nada fuera de `~/.local/share/fonts`.

Que imite exactamente a FreeTypeAbstraction, el buscador que usa Janim.jl.
En macOS, ese buscador usa las carpetas de `BaseDirs.fonts()`, en este orden y
**sin entrar en subcarpetas**:

1. `~/Library/Fonts`
2. `/Library/Fonts`
3. `/System/Library/Fonts`
4. `/System/Library/Fonts/Supplemental`
5. `/Network/Library/Fonts`

Si el orden o el recorrido difieren, las dos bibliotecas pueden elegir caras
distintas para el mismo nombre. Se notaría en la comparación del §7, aunque
cada una se vea bien por separado.

Las `.ttc` (colecciones) tienen varias caras. Hoy, como FreeTypeAbstraction,
se carga solo la primera (`freetype.Face(path)`): no lo cambies sin cambiarlo
en los dos lados.

## 5 · Lo demás que está escrito para Linux

- **GLFW:** `janim/backend/glfw.py:13`, `LIBRARY = "/usr/lib64/libglfw.so.3"`,
  solo se usa si existe. En macOS se cargará la `libglfw.3.dylib` del wheel.
  `:14` (`X_LOCALE_DIRECTORY`) solo aplica si existe.
- **¿Hay pantalla?** `glfw.py:50-53` (`_headless_env`) decide «no hay
  pantalla» si faltan `DISPLAY` y `WAYLAND_DISPLAY`, que en macOS nunca
  existen. Haz que en darwin cuente como pantalla. Julia lo restringe a Linux
  en `src/backend/glfw.jl:186`.
- **La plataforma:** `glfw.py:71-90` solo conoce Null, Wayland y X11. Añade
  `glfw.PLATFORM_COCOA` a la tabla de `JANIM_GLFW_PLATFORM` y a los nombres
  (`:89`), como `"cocoa"`.
- **`-p`** ya abre con `open` en macOS (`janim/cli.py:329`).
- **`bin/janim`** usa `readlink -f`, que necesita macOS 12.3 o posterior, y el
  `.venv/bin/python` del checkout.

## 6 · La ventana en vivo: lo que falta escribir

1. **La fuente de la superficie.** `glfw.py:115-127` (`native_handles`) solo
   devuelve Wayland o X11. Para Cocoa, devuelve
   `{"platform": "cocoa", "window": int(glfw.get_cocoa_window(window.handle))}`.
   `native.create_surface` (`native.py:297-301`) se lo pasa a
   `_helpers.get_surface_id_from_info` de wgpu-py. Su rama `darwin` ya crea la
   `CAMetalLayer` sobre el `contentView` del `NSWindow` con rubicon-objc, y la
   superficie `WGPUSurfaceSourceMetalLayer`. No hay que escribir Objective-C.
2. **`create_window`** (`janim/backend/wgpu/window.py:221-232`) solo acepta
   `"wayland"` y `"x11"`: añade `"cocoa"`.
3. **Retina.** El presentador ya se configura con `framebuffer_size` (píxeles
   físicos, `window.py:225`), que en Retina es el doble que la ventana. La capa
   que crea wgpu-py no ajusta `contentsScale`. Si la imagen sale borrosa o en
   un cuarto de la ventana, pon `contentsScale = backingScaleFactor` del
   `NSWindow` sobre la capa (con rubicon). En la era OpenGL, este error dio una
   ventana negra en este mismo M1.
4. **El formato:** `window.py:25-28` ya maneja `bgra8unorm`, que es lo que
   preferirá Metal.
5. **El hilo principal.** Cocoa exige ventanas y eventos en el hilo principal.
   - La preview simula la escena en un hilo aparte (`janim/interactive/live.py:220`,
     `janim-playhead`), y el bucle de eventos y el presente van en el principal
     (`live.py:240`).
   - Comprueba que ninguna llamada a GLFW (ni `create_window`, ni callbacks
     instalados desde el otro hilo) ocurre fuera del hilo principal.
   - Si la ventana se congela o el proceso muere al abrirla, sospecha esto
     primero.
6. **El parche de Wayland** (`glfw.py:160-200`) esconde la ventana y bombea
   eventos antes de destruirla. Si en macOS estorba, limítalo a Linux.
7. **El ratón en Retina.** El cursor llega en coordenadas lógicas y el
   framebuffer está en físicas. Si orbitar o arrastrar va al doble o a la
   mitad de velocidad, la mezcla está en los callbacks de `live.py` (hacia
   `:540-600`) y en `janim/interactive/`.

Prueba con `bin/janim examples/demo/03_portals.py`: teclas (espacio, `,`/`.`,
←/→, `[`/`]`, Esc), ratón, y abrir y cerrar dos previews seguidas.

## 7 · Un instrumento sin Linux: Python contra Julia en el mismo Mac

En Linux (RADV, 640×360 a 10 fps) estas cinco demos dan **frames idénticos
byte a byte** en Janim.py y en Janim.jl, medido el 2026-10-21:

| demo | clase | frames |
|---|---|---|
| `01_multicam` | `Multicam` | 140 |
| `03_portals` | `Portals` | 140 |
| `04_lorenz_glow` | `LorenzGlow` | 180 |
| `07_text_mask` | `TextMask` | 141 |
| `11_chase_camera` | `ChaseCamera` | 220 |

Las otras ya difieren en Linux: la 08 por su texto en pantalla, y las 02, 05,
06 y 09 por causas no investigadas. No las uses. En el Mac las dos
bibliotecas deberían seguir coincidiendo entre sí. Los dos arneses (hashes por
frame con `frame_tap` en Python y `Janim._FRAME_TAP` en Julia) están en el
`MACOS.md` de Janim.jl, §6. Guárdalos fuera del repo.

Si en el Mac no coinciden y en Linux sí, por orden:

1. **Las fuentes.** Mira el §4: el mismo nombre resuelto a caras distintas.
2. **La libm.** Python usa `math.sin`/`math.cos`/`math.tan` del sistema en
   algunos sitios, y Julia usa sus propias implementaciones:
   - `janim/animation/transform.py:129-132` (`path_arc`);
   - `janim/animation/indication.py:61` y `:99`;
   - `janim/animation/homotopy.py:63` (`ApplyWave`);
   - `janim/backend/wgpu/effects.py:95` y `:238-243` (ángulos de efectos);
   - `janim/core/decor.py:146-153`.

   La glibc de Linux da los mismos bits que Julia en estos casos; la libm de
   Apple puede no darlos en el último ulp. El arreglo es usar `sin`/`cos`/`tan`
   de `janim/core/_julia_math.py`, el port de Julia Base que ya usa
   `janim/core/surface.py` (`_julia_trig`). Cámbialo solo si en Linux los
   frames siguen idénticos: allí glibc y Julia coinciden en estos casos, no en
   todos los valores posibles.
3. **numpy.** `janim/core/bezier.py` usa `np.sin`/`np.cos`, y numpy tiene sus
   propias implementaciones vectoriales por arquitectura: NEON en arm64 y AVX
   en x86. Pueden diferir en el último bit entre las dos máquinas.

**Determinismo:** la misma escena en dos procesos del Mac debe dar los mismos
frames. No debería depender de la GPU; compruébalo con un par de escenas.

## 8 · Lo que no es un problema del Mac

- **El desenfoque de movimiento en vídeo no existe** en ninguna plataforma.
  `Scene` no acepta `motion_blur` y la CLI rechaza `--motion-blur`. Las demos
  10 y 12 y las lecciones de `c3_05_motion_blur` lo describen.
- **`c2_05_from_manim/01_from_manim_ce.py` dice que `-ql` no existe**, pero la
  CLI sí lo tiene.

## 9 · Al terminar

Deja aquí, en este fichero, lo que confirmaste y lo que resultó falso, y en la
sección «Known limitations» de los dos README cambia «Linux only» por lo que
de verdad funcione, con la versión de macOS y el chip en que se probó.
