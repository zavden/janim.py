# La CLI, la ventana viva y la granja

Esta página describe `bin/janim`, la ventana de previsualización en vivo, los
checkpoints y el render en paralelo (`-j N`).

## `bin/janim`: un proceso por llamada

```text
janim escena.py [flags]            sin verbo = PREVIEW; -w escribe, -p escribe y abre, -s un frame
janim render  escena.py [flags]    el vídeo entero (o un still con -s)
janim frame   escena.py K out.png  UN frame: K ↔ t = (K − ½)/fps (re-simula desde t = 0; K más allá del final es error)
janim preview escena.py [-qm] [-r WxH] [--fps N] [-c] [--samples N]
janim states  escena.py            (no hay snapshots fuera del proceso: lo dice)
janim codecs                       qué sabe hacer el ffmpeg de la CLI
janim check | finish | ping | daemon | stop     no-op de una línea, exit 0
```

No hay daemon: cada llamada es un proceso ordinario que arranca en decenas de
milisegundos. Los verbos `check`, `finish`, `ping`, `daemon` y `stop` existen
solo para que los scripts que los llaman no fallen.

Flags: `-r WxH`/`--resolution`, `--fps N`, `-q{s,l,m,h,q,k}` (resolución **y**
fps: 640×360@10 · 854×480@15 · 1280×720@30 · 1920×1080@60 · 2560×1440@60 ·
3840×2160@60), `-pq…`/`-wq…` (nunca `-qmp`), `-o`, `-j N`, `-n X,Y` y `-nX,Y`
(animaciones desde 1, los `wait` cuentan; `-n 3` = hasta el final), `--from`
(etiqueta, frame o `1.5s`), `--to`, `-t` (ProRes 4444 en `.mov`, PNG RGBA),
`-s [--to X]` (solo el último frame; `--to` lo elige), `--samples` (0/1/4; 0
es 4), `--out_dir`, `-p`, `-c`, `--only-cli`/`--no-tui` (aceptadas, no hacen
nada: no hay panel ni `janim.cfg`). **Gana la última flag**: `-qh -r 640x360`
es 640×360 a 60 fps. Defaults de la CLI: 1280×720@30, `samples 0`; un
`Scene(...)` construido a mano sigue en 1920×1080@60. La precedencia es `flag
> atributos de la clase > defaults`: se resuelve construyendo la escena con
los kwargs de la CLI.

Salida: sin `-o`, junto a la escena (`x.py:Intro` → `x_Intro.mp4`; con `-t`,
`.mov`); `--out_dir D` hace `mkdir -p`, se une a un `-o` relativo y pierde con
`WARN` ante uno absoluto. La escena se nombra `fichero.py:Clase` o `fichero.py
Clase`; sin nombre se usa la única subclase de `Scene` del fichero. La línea
de resultado es `OK <ruta> [(detalle)]` — `(animations A:B of N)`, `(frames A:B
of T)`, `(checkpoint L, prefix simulated without drawing)`, `(N frames, J
processes)`, `(still: the scene has no animations)` — y `-p` abre lo que se
escribió. Exit 0 / 1 (`ERR …` en stderr, UNA línea, nunca una traza) / 2
(solo `--motion-blur`, que no se admite) / 130 (Ctrl-C).

**Ninguna flag se ignora en silencio.** Se rechazan, con su texto: `-s` con
`-j`, `--from` o `-n`; `-t` con `-j`; `-j` con `--from`, `-n` o `--to`; `--to`
con una etiqueta; `-n` mal formada; `--from` o `--to` fuera de rango; `-n` que
no dibuja nada (`ERR -n 9 drew nothing: the scene has 4 animations`); `--from
L` cuya etiqueta nunca llega; `preview` con `-t`, `-w` o `-p`; una escena sin
animaciones con `-j`. Dos escenas en un fichero sin nombre: `ERR x.py defines
2 scenes: Main, Intro — name one as x.py:Main`; un nombre que no existe: `ERR
scene «Nope» is not defined by x.py — expected class Nope(Scene) …`.

Otros rechazos habituales:

| Orden | Respuesta |
|---|---|
| una flag que el verbo no usa (`frame … -j 4`, `render … -c`, `preview … -o x.mp4`, `states … -qm`) | `ERR frame does not take -j: it splits a video across processes, and frame takes -qs…-qk, -r, --fps, -t, --samples, --out_dir, -p` |
| `frame x.py 999 out.png` en una escena de 90 frames | `ERR frame 999 is past the end (90 frames)`, como `render -s --to 999` |
| `--samples 3` | `ERR --samples wants 0 (the default, 4), 1 or 4 (got «3»)` |
| `-j 4096` | `ERR -j 4096 asks for more processes than this machine has threads (N): …` |
| `--from 0`, `--from -2` | `ERR --from wants a frame ≥ 1 (got «0»)` |
| `--to 0` | `ERR --to 0 lands before the first frame` |
| `--from 1.5` (sin la `s`) | el error del marcador que nunca llega, más `— a time is written with its unit: --from 1.5s` |
| `check`, `finish` | `OK no daemon, so there is nothing to check or finish` |

La tabla de qué flags toma cada verbo es `VERB_FLAGS` en `janim/cli.py`.

Tres variables de entorno que no cambian ningún píxel: `JANIM_FFMPEG` (el
ejecutable ffmpeg de la CLI; por defecto el del PATH), `JANIM_CRF` (23 por
defecto) y `JANIM_ENCODER_THREADS` (los hilos de x264; por defecto los suyos).
Sirven para elegir la calidad del contenedor (por ejemplo `JANIM_CRF=0` para un
fichero sin pérdidas) o para fijar un solo hilo y obtener un mp4 reproducible
byte a byte.

## Checkpoints y rangos

`self.checkpoint("act2")` marca un punto. En la CLI, `--from act2` **simula el
prefijo sin dibujar** y empieza a dibujar en el marcador
(`render_from(..., simulate_prefix=True)`): la salida contiene los frames desde
el marcador y coincide byte a byte con los mismos frames del vídeo entero. Un
marcador que la escena nunca alcanza es un error (`drew nothing`), no un vídeo
entero ni vacío.

La API `render_from(cls, out, label, scene_path=…)` conserva dentro de un
proceso un snapshot de la geometría: con uno válido salta el prefijo
(`scene.skipped_prefix`); sin él rinde el vídeo ENTERO y toma el snapshot para
la llamada siguiente. Los snapshots guardan el estado de los mobjects, no el
interno de los updaters con estado; para esos, repetir desde cero es el camino
fiable. La clave de validez es el SHA-256 del texto del fichero antes de la
línea del marcador, un marcador escrito dos veces en un fichero nunca es
válido, y los snapshots van por escena (`Intro --from act2` con la etiqueta de
`Main` no alcanza nada y en la CLI es error).

`--from 20 --to 50` es `render_segment` (simula todo, dibuja el rango); `-n
2,3` es `anim_range` (una puerta más sobre el dibujo); los dos componen y
ninguno cambia lo simulado: `-n 2,3` entrega al codificador exactamente los
mismos frames que `--from 31 --to 75`.

## La granja: `-j N`

`render_parallel(path, out, n=, frames_total=, …)` parte los frames en N rangos
`round(T·(k−1)/N)+1 … round(T·k/N)`, lanza N procesos hijos (`sys.executable
-c`, con el nombre de la escena validado como identificador antes de
interpolarse) que corren `render_segment` con **un hilo de x264 por proceso**,
y concatena los segmentos con el MISMO ffmpeg (`-f concat -c copy`, sin
recodificar; la lista escapa el apóstrofo como pide el demuxer, así que una
salida en `it's here/` conserva su vídeo). `1 ≤ N ≤ os.cpu_count()`: cada
proceso tiene su propio dispositivo gráfico y su propia simulación completa de
la escena, de modo que el beneficio crece con la duración del vídeo.

Lo que la granja NO acelera es la simulación: cada proceso simula la escena
desde t = 0 hasta el final de su segmento (los updaters corren en todos los
frames y solo se dibujan los del segmento), así que el último proceso la
simula entera y entre todos la repiten (N + 1)/2 veces. Una escena cuyo coste
está en sus updaters tarda con `-j 4` lo mismo o más que en un proceso; la
granja reparte el dibujo y la codificación.

## La ventana viva

`janim escena.py` (o `preview`) abre una ventana GLFW **sin API gráfica**
(no redimensionable, al tamaño del render) y presenta sobre ella por una
surface WebGPU creada con sus handles nativos (Wayland o X11 en Linux, Cocoa
en macOS; con `JANIM_GLFW_PLATFORM=x11` se fuerza X11; bajo `JANIM_HEADLESS=1`
o sin display no hay surface y solo se tratan eventos). A 1:1 la ventana
recibe los bytes del frame tal cual los produce `render_frame`; en una
pantalla Retina, a 2:1, cada píxel del frame ocupa un bloque de 2×2.

Teclas: `Esc`/`q` salir · `espacio` pausa · `.`/`,` un frame · `←`/`→` ∓1 s ·
`[`/`]` animación · `PgUp`/`PgDn` checkpoint · `Home` al frame 1 · `c` parar
en checkpoints · `r` reset de la cámara del usuario · `d`+ratón rota (torno en
unidades de pantalla sobre el frame compuesto, φ ∈ [0, π], γ intacta) ·
`f`+ratón o arrastre panea (por el mundo) · rueda zoom sobre el cursor. Los
deltas del usuario se COMPONEN sobre la cámara de la escena y nunca la
editan; el cursor se re-siembra al entrar en la ventana y un salto brusco del
cursor se acota a 150 px.

El playhead: `construct` corre UNA vez en un hilo aparcado por
`Scene.frame_hook` al final de cada frame simulado; el bucle pide frames de uno
en uno y dibuja el estado aparcado (el frame k equivale a `render_frame(k)`
byte a byte, también con updaters con estado). Cualquier salto atrás
reconstruye desde t = 0 (no se resume desde snapshots). El mapa de landmarks
crece con el playhead y solo una edición del fichero lo reinicia. Hay una
caché de `max(8, 500 MB/(3·W·H))` frames; un acierto reescribe el target.

Una edición del fichero se detecta por el SHA-256 de su texto y se aplica
re-ejecutando el módulo (la clase se vuelve a resolver). Una escena que lanza
una excepción o una edición que no compila CONGELA la ventana en el último
frame bueno, con el error en un banner, y vigila el fichero: al guardar un
arreglo revive sola. La franja de tiempo del pie (pista, parte reproducida,
ticks de acto, marcas doradas de checkpoint) se pinta DESPUÉS de cachear: solo
el directo la lleva. El ritmo es `sleep(1/fps − transcurrido)`, sin descartar
frames.

Dos límites del diseño, para no descubrirlos con la ventana abierta: (1) el
bucle espera el frame siguiente sin plazo y sin bombear eventos, así que un
`construct` que calcule mucho entre dos frames congela la ventana ese tiempo y
`Esc` no responde hasta que el frame llega; (2) al cerrar, el hilo del playhead
se abandona a los 5 s y la escena se cierra desde el hilo principal aunque
`construct` siga vivo (una escena colgada): la ventana se va y el proceso
termina.

Al cerrar la ventana, el foco se drena (se esconde y se bombean eventos hasta
el `leave`, con un techo de 0,25 s). Si la ventana estaba sola en su espacio
de trabajo, el compositor del escritorio no manda el `leave` y el techo se
agota siempre; es normal.

API: `live(address, fps=, resolution=, stop_at_checkpoints=, samples=)`;
`setup_live(...)` + `live_step(v)` + `live_status(v)` + `close_live(v)` para
conducir el bucle a mano (ventana oculta por defecto); `Scene(preview=True)`
(una ventana visible que enseña cada frame dibujado; sin salida, el reloj fijo
ritmado a 1/fps); `count_frames(cls)` (simula sin dibujar, sin GPU).
