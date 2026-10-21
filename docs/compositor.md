# Capas y efectos

Una `Composition` define lo que se dibuja. Las raíces de la escena siguen
recibiendo sus updaters, pero el dibujo sale de sus capas, de abajo arriba.
Dentro de una capa los objetos se dibujan como en la ruta directa; entre
capas la composición y los efectos trabajan con luz lineal premultiplicada.
Los tres shaders del fill descartan el triángulo Loop–Blinn de un lado
recto más fino que 2⁻⁹ px de ventana: lavapipe fabricaba en él un téxel NaN
que la ruta compuesta arrastraba bajo cualquier efecto. Poner
`_FILL_THIN_PX = 0` en `janim/backend/wgpu/pipelines.py` desactiva ese
descarte.

```python
from janim import *


class LayerExample(Scene):
    def construct(self):
        square = Square(fill_color=BLUE, fill_opacity=1)
        disc = Circle(fill_color=RED, fill_opacity=0.7).shift(RIGHT)
        blur = Blur(0.12)
        self.use_composition(
            Composition(
                Layer(square, effects=[blur]),
                Layer(disc, blend="screen"),
                background=(0.03, 0.04, 0.05, 1),
            ),
        )
        self.play(disc.animate.shift(LEFT))
        self.wait()
```

Los modos de mezcla son `normal`, `add`, `multiply`, `screen` y `overlay`.
La opacidad de capa multiplica su imagen terminada. `Layer(composition)`
anida una composición con acumuladores propios; `Layer(effects=[...])`
aplica sus efectos a lo compuesto debajo. Una capa de ajuste solo lleva
efectos: máscara, opacidad, blend, matte, cámara y ventana son errores.

`Mask(*mobjects, invert=False, feather=0, hard=False, luma=False)` recorta
el contenido. `crop(*mobjects, inside=shape)` y `crop(*mobjects, minus=shape)`
construyen esos recortes. La máscara se dibuja en el espacio del padre,
después de colocar la ventana. Su feather se mide también en ese espacio.
Un `matte="alpha"`, `"luma"`, `"alpha_inv"` o `"luma_inv"` consume la capa
siguiente: usa su contenido y cámara, omitiendo sus efectos y máscara.

`Layer(*world, camera=view, window=rectangle)` crea una vista del mundo en
una ventana. `view` es un `CameraFrame`; el rectángulo se proyecta con la
cámara del padre y su aspecto recorta el centro de la vista. Sus efectos
se calculan antes de reducirla a la ventana, con la escala de su cámara.
Las cámaras interiores sobrescriben la vista heredada de una precomposición.

Los objetos compartidos se actualizan una vez. Primero corren las raíces
de escena, después los contenidos y máscaras, y finalmente las cámaras y
ventanas que aún no estaban en esas listas. `remove` y los reemplazos de
animación recorren también las capas anidadas. `clear` solo vacía raíces.
`describe(scene)` muestra el árbol de capas y máscaras además de las raíces.

| Efecto | Parámetros principales | Unidad |
|---|---|---|
| `Blur(sigma, in_pixels=False)` | sigma | Escena, o píxeles explícitos |
| `BoxBlur(radius)` | radius | Escena |
| `DirectionalBlur(sigma, angle)` | sigma, angle | Escena y radianes |
| `RadialBlur(strength, center_point=(0, 0))` | strength, center_point | Fracción y escena |
| `Dof(focus=None, aperture=0.4, max_sigma=4)` | Distancia al plano focal | Escena |
| `Bloom(threshold=0.6, intensity=1, sigma=0.15)` | Umbral, ganancia, sigma | Luz lineal y escena |
| `Glitch()` | intensity, seed, rate, rgb_shift, slices, block | Escena y frames |
| `CRT()` | intensity, scanlines, scan_depth, mask, curvature, vignette, roll | Cantidades y fracciones |
| `VHS()` | intensity, seed, rate, chroma_bleed, jitter, noise, head_switch | Escena, frames y fracciones |
| `ColorAdjust()` | brightness, contrast, saturation, hue | Factores y radianes |
| `Pixelate(size=0.2)` | size | Escena |
| `Vignette()` | amount, radius, feather | Fracciones de la semidiagonal |
| `Grain()` | amount, seed, rate, levels=8 | Factores y frames |
| `ChromaticAberration(amount=0.1)` | amount | Escena |
| `Sharpen(amount=0.6, sigma=0.05)` | amount, sigma | Factor y escena |
| `Wave()` | amplitude, wavelength, angle, phase | Escena y radianes |
| `EdgeDetect()` | amount, color, thickness | Factor, color y píxeles |

Los campos son mutables y pueden cambiar desde un updater. `rate` cuenta
frames. El ruido mezcla la semilla con el nombre del tipo y el índice de
frame de la escena; no consulta un reloj externo. Un campo `current_frame`
recibe ese índice automáticamente y requiere un objeto mutable.

Un efecto con sus mandos en identidad omite el pase, con tres excepciones: `BoxBlur(0)` usa al menos un píxel de radio,
`RadialBlur(0)` ejecuta sus 32 muestras y `Bloom(intensity=0)` ejecuta la
pirámide y su suma saturante. Los kernels gaussianos y de caja avisan
cuando el radio pedido supera los 63 píxeles admitidos.

Un shader propio se registra con `effect_shader`. El handler se registra
por tipo y recibe la ranura de origen; devuelve esa misma ranura si es
identidad, o una ranura temporal con el resultado. Ejemplo mínimo:

```python
from dataclasses import dataclass
from janim import apply_effect, effect_shader
from janim.backend.wgpu.uniforms import quad_params


@dataclass
class Posterize:
    levels: float = 6


effect_shader(
    "posterize",
    """
    @fragment
    fn fs_posterize(in: QuadOut) -> @location(0) vec4<f32> {
        let c = sample_a(in.uv);
        let s = floor(unpremult(c) * P.f0.x + 0.5) / P.f0.x;
        return vec4<f32>(s * c.a, c.a);
    }
    """,
)


@apply_effect.register(Posterize)
def posterize(effect, compositor, source):
    if effect.levels <= 1:
        return source
    return compositor._quad(
        "posterize",
        compositor._scratch(source),
        source,
        params=quad_params(f0=(effect.levels,)),
    )
```

El registro añade `sample_a`, `sample_b`, `P`, las funciones de ruido y
`unpremult`/`luma`. Registrar de nuevo el mismo nombre recompila en el
siguiente uso. Los nombres de fábrica están reservados. Los efectos de
color deben dividir por alfa antes de operar y multiplicarlo al terminar.

Para usos fuera de `Scene`, `render_composition(comp, camera, rv=rv, cg=cg)`
devuelve RGB de arriba abajo. `read_layer_rgba(layer, camera, rv=rv, cg=cg)`
devuelve RGBA recto, con la primera fila abajo. El `flip_y` de la ruta
directa es distinto del vídeo en efectos verticalmente asimétricos como VHS;
cada función mantiene su propio contrato.
