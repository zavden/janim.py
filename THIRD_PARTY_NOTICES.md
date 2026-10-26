# Third-party notices

Janim is released under the MIT License (see `LICENSE`). Parts of it are
ported from, or follow closely, the projects below. All of them are
distributed under the MIT License; their copyright notices are reproduced
here, and the MIT permission notice that applies to each of them is the one
at the end of this file.

| Project | What Janim takes from it | Copyright |
|---|---|---|
| [ManimGL](https://github.com/3b1b/manim) | the API and behaviour Janim follows; the structure of the stroke, fill and surface shaders | Copyright (c) 2020-2023 3Blue1Brown LLC |
| [Manim Community](https://github.com/ManimCommunity/manim) | the color catalogues in `janim/core/_palette.py`; the CE spellings of several names; the `Code` listing of `janim/text/code.py` and the tests of `tests/test_code.py` | Copyright (c) 2018 3Blue1Brown LLC; Copyright (c) 2024, the Manim Community Developers |
| [Julia](https://github.com/JuliaLang/julia) | the Float64/Float32 math of `janim/core/_julia_math.py`, `_atan.py`, `_atan32.py`, `_ranges.py` and `_reductions.py` (Base) | Copyright (c) 2009-2024: Jeff Bezanson, Stefan Karpinski, Viral B. Shah, and other contributors: https://github.com/JuliaLang/julia/contributors |
| [FastPower.jl](https://github.com/SciML/FastPower.jl) | `fastlog2` and `fastpower` in `janim/core/_julia_math.py` | Copyright (c) 2024 SciML Open Source Scientific Machine Learning |
| [ForwardDiff.jl](https://github.com/JuliaDiff/ForwardDiff.jl) | the forward-mode duals of `janim/ode/dual.py` | Copyright (c) 2015: Jarrett Revels, Theodore Papamarkou, Miles Lubin, and other contributors |
| [OrdinaryDiffEq.jl](https://github.com/SciML/OrdinaryDiffEq.jl) (OrdinaryDiffEqTsit5, OrdinaryDiffEqCore) | the Tsit5 tableau and the adaptive driver of `janim/ode/tsit5.py` | Copyright (c) 2016-2020: ChrisRackauckas, Yingbo Ma, Julia Computing Inc, and other contributors |
| [DiffEqBase.jl](https://github.com/SciML/DiffEqBase.jl) | the error norm and residuals of `janim/ode/tsit5.py` | Copyright (c) 2016-2020: ChrisRackauckas, Julia Computing |
| [SciMLBase.jl](https://github.com/SciML/SciMLBase.jl) | the integrator interface of `janim/ode/tsit5.py` | Copyright (c) 2021 Chris Rackauckas and contributors |
| [Colors.jl](https://github.com/JuliaGraphics/Colors.jl) | the named-color table of `janim/core/_named_colors.py` | Copyright (c) 2012-2013: Daniel Jones, Jeff Bezanson, and other contributors |
| [isosurfaces](https://github.com/jared-hughes/isosurfaces) | the quadtree isoline tracer of `ImplicitFunction` in `janim/core/implicit.py` | Copyright (c) 2024 Jared Hughes |

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
