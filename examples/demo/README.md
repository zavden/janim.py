# demo/ — doce cosas que Janim hace y Manim no puede, en Python

Escenas de demostración de Janim: escenas cortas (7–23 s, 1280×720) que
viven cada una sobre UNA capacidad que ni ManimCE ni ManimGL tienen — el
compositor por capas y todo lo que cuelga de él (máscaras, modos de fusión,
efectos, una cámara por capa) más la física dentro de un updater y una nube
de un millón de partículas.

Los comentarios van en **español**; los identificadores son la API y siguen
en inglés. **Los textos que se dibujan en pantalla van en inglés** (rótulos,
pies, títulos): es material de demostración, no de estudio.

## Cómo renderizarlas

Desde la raíz del repositorio, dentro del entorno virtual del proyecto, por el
CLI (un proceso por llamada):

```bash
bin/janim render examples/demo/03_portals.py -ql     # el vídeo, junto a la escena
bin/janim examples/demo/09_reflection.py             # la ventana viva (preview)
bin/janim frame examples/demo/03_portals.py 90 f.png -ql   # UN frame (re-simula desde t = 0)
```

Los presets fijan resolución Y fps: `-qs` 640×360@10, `-ql` 854×480@15,
`-qm` 1280×720@30 (el default del CLI), `-qh` 1920×1080@60. Cada fichero
tiene una sola escena, así que no hace falta nombrar la clase.

Cada fichero es también un script completo con su pie:

```bash
python examples/demo/12_motion_blur.py   # 1280×720@30, mp4 junto al .py
```

`JANIM_HEADLESS=1` delante de cualquiera de estas órdenes renderiza en la
CPU (lavapipe); sin ella, la GPU nativa.

Un aviso que puede salir al arrancar (una vez por cada σ que no cabe) y no
es un error: `RuntimeWarning: gaussian-kernel-radius-limit`. El kernel del
compositor calcula entero hasta un radio de 63 px (σ = 21 px), y un efecto
que pide más avisa en vez de callarse: el halo sale algo más estrecho de lo
pedido. La 09 a 720p, por ejemplo, avisa tres veces: los niveles 2σ y 4σ de
su Bloom y el `feather = 0.7` de la máscara del reflejo (63 px de σ).

## El índice

| # | fichero | clase | lo que solo Janim puede hacer | dur. |
|---|---|---|---|---|
| 01 | `01_multicam.py` | `Multicam` | **una cámara por capa**: cuatro vistas del MISMO mundo 3D, cada una con su z-buffer, los updaters corriendo una sola vez. | 14 s |
| 02 | `02_pendulum_glow.py` | `PendulumGlow` | **física (Tsit5 de `janim.ode`) en un updater + capa aditiva con Bloom + máscara animada**: un doble péndulo con la rejilla entera; la estela se une con `set_points_smoothly`, la masa lleva un `GlowDot` detrás (halo redondo por fragmento) y el foco que sigue a la punta es un `crop` con `feather`. | 23 s |
| 03 | `03_portals.py` | `Portals` | **multicámara con máscaras, en 2D**: una roseta en el centro (la cámara de la escena) y dos lupas ×3 IGUALES a los lados —un círculo y una estrella que GIRA sobre sí misma—, cada una con una cámara que persigue a su punto (updater sobre el `CameraFrame`); la forma del portal es solo la máscara (`window` + `crop`), y por eso puede girar con la imagen quieta. | 14 s |
| 04 | `04_lorenz_glow.py` | `LorenzGlow` | **10⁶ partículas `GlowDots` + `"add"` + Bloom**: el atractor de Lorenz con 15 s de vuelo de cámara. | 18 s |
| 05 | `05_rack_focus.py` | `RackFocus` | **profundidad de campo por capa** (`Dof`): cinco fórmulas a cinco profundidades, el foco viaja de la más cercana a la más lejana escribiendo un número; paralaje de propina. | 13 s |
| 06 | `06_broadcast.py` | `BroadcastScene` | **los efectos de editor** (`Glitch`, `CRT` con `roll`, `VHS`, `ColorAdjust`) sobre una fórmula que sigue morfando debajo; cada dial vuelve a un cero que es un no-op exacto. | 20 s |
| 07 | `07_text_mask.py` | `TextMask` | **texto como máscara de un render 3D con luz**: «JANIM» recortando un mar de olas visto por su propia cámara, y el vuelo de cabecera a través de la «I». | 14 s |
| 08 | `08_light_vs_pigment.py` | `LightVsPigment` | **modos de fusión en luz lineal**: R+G+B = blanco con `"add"`, C×M×Y = negro con `"multiply"`, cada disco en su capa, los de luz en una precomposición con Bloom. | 12 s |
| 09 | `09_reflection.py` | `Reflection` | **un reflejo de verdad**: copia volteada en una capa con `Wave` (fase animada), `Blur`, `opacity` y una `Mask` con `feather` que la apaga con la distancia; luna y estrellas con Bloom, `Vignette` de ajuste. | 13 s |
| 10 | `10_motion_blur.py` | `MotionBlur` | una rueda que acelera, cuatro órbitas y un barrido de cámara, escritos para un **motion blur** por sub-exposiciones que el bucle de render no aplica: el vídeo sale con exposiciones simples (abajo). | 9 s |
| 11 | `11_chase_camera.py` | `ChaseCamera` | **persecución y minimapa**: un cometa por un nudo trébol con la principal orbitando, una cámara de PERSECUCIÓN por updater (lo que en CE pide un `ZoomedScene`) y un minimapa cenital en ventana cuadrada; el HUD con `fix_in_frame()` no derrapa. | 22 s |
| 12 | `12_motion_blur.py` | `MotionBlurWelcome` | variante de la 10: «Welcome / to / JANIM» entrando a látigo, «JANIM» en Fredoka Expanded; también escrita para el motion blur por sub-exposiciones. | 7 s |

## Lo que cuesta verlas bien (y por qué está así)

- **Un disco por capa** (08). Dentro de una misma capa los mobjects se tapan;
  el modo de fusión actúa entre la capa entera y lo de debajo. Si los tres
  discos fueran una sola capa, `"add"` no sumaría nada.
- **La máscara no se dibuja; el aro sí** (03, 07). La forma que recorta va
  rellena de blanco y no entra en ninguna capa de contenido; el borde visible
  es OTRO mobject con solo stroke, en una capa por encima.
- **El centro de la caja de una estrella no es su centro** (03). `rotate`
  gira sobre `get_center()` (la caja), que en una estrella de cinco puntas
  está 0.2 u por encima del centro real: la estrella orbitaba en vez de
  girar. Colocarla y girarla por `get_real_center_of_mass()` (el centroide
  exacto) lo arregla. Y como `window=` coloca la imagen en la CAJA del
  mobject, una estrella que gira haría bailar la imagen ±0.2 u: la ventana de
  esa capa es un cuadrado fijo que no se dibuja, y la estrella es solo la
  máscara.
- **Una cola del color del trazo no se ve** (03). La `TracingTail` amarilla
  sobre la roseta con degradado desaparecía al pasar por el lóbulo amarillo;
  blanca y más gruesa se lee en las tres vistas.
- **Dos animaciones sobre un mismo mobject se pisan** (07). Cada una escribe
  el estado entero, así que un `FadeOut` y un `.animate` a la vez sobre el aro
  dejaban al aro quieto. Un solo `.animate` con dos operaciones encadenadas
  (`.scale(90.0, about_point=anchor).set_stroke(opacity=0.0)`) hace las dos
  cosas.
- **σ tiene un techo honesto**: 0.23 unidades a 720p (21 px). El `Dof` de 05
  pone `max_sigma=0.23` por eso; pedir 3.0 solo produce el aviso de arriba y
  un blur recortado.
- **Un Bloom recortado hace halos CUADRADOS** (02). El nivel 4σ de la
  pirámide con `sigma=0.16` pedía 58 px y el kernel lo cortaba a ±63: una
  gaussiana truncada es casi una caja, y una caja separable H+V alrededor de
  un punto brillante es un cuadrado. Sobre un trazo largo no se nota; sobre
  la masa sí. Arreglo doble: `sigma=0.055` (los tres niveles caben) y un
  `GlowDot` detrás de la masa, que es un halo redondo por fragmento y no
  depende del kernel.
- **El estado inicial ya dibujado** (02). Varilla, masas y foco se colocan en
  la posición del estado inicial ANTES de arrancar el integrador: nada nace
  en el origen para saltar un frame después.
- **El motion blur en el bucle de render no existe** (04, 10, 12). `Scene`
  no tiene un kwarg `motion_blur` y el CLI rechaza `--motion-blur` por su
  nombre (exit 2). Las escenas se renderizan sin él; la animación es la misma.
- **`render_frame_motion` no enseña un motion blur de verdad**: renderiza el
  frame que contiene cada sub-exposición, y como la ventana del obturador
  (`shutter / fps`) es más corta que un frame, promedia como mucho DOS frames
  distintos — dos copias, no una estela. Medido en la 10 a t = 4 s:
  `render_frame_motion(MotionBlur, 4.0, n=8, shutter=0.5, fps=30)` da cada
  partícula dos veces. Para muestrear de verdad el obturador de 180° de
  30 fps hay que darle un reloj más fino y abrir el obturador en proporción:
  `render_frame_motion(MotionBlur, 4.0, n=8, shutter=4.0, fps=240)` reparte
  las ocho sub-exposiciones en cuatro frames de 1/240 s y sale una estela.
  Solo vale para escenas cuyo estado es función del tiempo (la 10, la 12): un
  integrador que avanza con `dt` (02, 04) simula OTRA cosa a otros fps.
- **Detalles numéricos de Python** que las escenas cuidan para que los
  fotogramas salgan siempre iguales: `sin`/`cos` de
  `janim.core._julia_math` (no los de `math`, que difieren en el último bit
  en ~3 % de las entradas); los rangos con `janim.core._ranges`
  (`step_range`, `linear_range`); en numpy 2 `0.22 * array_float32` se queda
  en float32, así que donde hace falta Float64 se sube a mano (03, 09: en la
  03 no llega a mover un píxel a 360p, pero es la cuenta exacta); `x ** 2`
  se escribe `x * x`; el `enumerate` empieza en 1 cuando el índice entra en
  un ángulo (08); y un `lambda` dentro de un `for` ve solo la última vuelta
  (05: se fabrica con una función).
