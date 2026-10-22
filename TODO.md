# Open items

What is known to be unresolved at version 1.0.0 (2026-10-22). Each entry says
what is wrong, where it lives and what settling it would take. Most of them
were found while porting to macOS and Windows and re-checking Linux; the
guides that record those sessions are in [`history/2026-10/`](history/2026-10/).
An item leaves this file when it is settled.

## Documentation and examples

- **Motion blur in video is described but does not exist.** `Scene` takes no
  `motion_blur` or `shutter` and the CLI rejects `--motion-blur`; what exists
  is `render_frame_motion`, which averages several exposures into one frame.
  The lessons in `examples/tutorial/c3_05_motion_blur/` still narrate the
  in-video version, and the headers of `examples/demo/10_motion_blur.py` and
  `12_motion_blur.py` explain the substitution at length. Either bring the
  feature back or rewrite the lessons.
- **Fonts the README does not install.** `c1_03_groups_and_text/03_text.py`
  (and its `scenes.py`), `c3_05_motion_blur/05_physics_warning.py` and
  `06_cli_and_farm.py` ask for Liberation Serif and Liberation Mono; the
  README names them under Requirements and in the Windows section, but the
  `dnf`/`apt`/`brew` lines only install DejaVu (`liberation-fonts`,
  `fonts-liberation` and `font-liberation` would do).
  `examples/demo/12_motion_blur.py` asks for «Fredoka Expanded», which no
  platform ships by default, so that demo fails on Windows and macOS (and on
  any Linux without the font). Options: install lines, substitute DejaVu, or
  ship the fonts (both families are published under the SIL Open Font
  License).
- **The clone line still says `<user>`.** Both READMEs clone
  `https://github.com/<user>/Janim.py.git` and then `cd Janim.py`; the
  repository is `zavden/janim.py`, so the directory a clone creates is
  `janim.py`.
- **`apt install python3.14` does not work on Debian 13.** Trixie has no
  `python3.14` package (forky/sid and Ubuntu 26.04 do). The uv note below
  the command covers the case, but the line itself fails as written.
- **A lesson contradicts the CLI.**
  `examples/tutorial/c2_05_from_manim/01_from_manim_ce.py` (line 13) says
  `-ql` does not exist; `bin/janim render … -ql` is a quality preset.
- **Two languages.** The READMEs come in both; `docs/*.md` and
  `examples/demo/README.md` are Spanish; the code, `llms.txt` and the
  tutorial's README are English. Decide the policy for the documentation.

## Behaviour and performance

- **Two demos are CPU-bound.** At 1080p60, `04_lorenz_glow` and
  `07_text_mask` take 25 s and 44 s on Linux (Ryzen 7 9700X) against 11 s
  and 10 s in Janim.jl, 61 s and 51 s on Windows, and on the M1 `07` takes
  78 s against Julia's 38 s. The time is numpy work per frame, not the GPU.
  Profile the two and move the hot loops.
- **A per-backend switch in the renderer.**
  `_MERGE_MESH_DRAWS = BACKEND != "Metal"` (`janim/backend/wgpu/render.py`):
  on Metal, merging the meshes into one `draw_indexed` moved the last bit of
  the lighting, so Metal draws them one by one. Understand why before another
  backend needs the same switch.
- **No CPU route on macOS.** `JANIM_HEADLESS=1` fails with the adapter list
  on Metal, because there is no lavapipe or WARP equivalent there. By design,
  but the error could say so.
- **Routes differ by a pixel at some edges.** Frames are reproducible within
  a route (RADV, lavapipe, Metal, DX12, WARP), not across them. Reference
  hashes, when they exist, have to be per route.

## Janim.py against Janim.jl

- **`Tex` glyph spacing.** Janim.py composes formulas with LaTeX's kerning;
  Janim.jl's default route (MathTeXEngine) spreads the glyphs. That alone
  makes demos `02`, `05` and `06` differ between the two libraries, while
  `01`, `03`, `04`, `07`, `10` and `11` are frame-identical on Linux and
  macOS (`08` and `09` differ only because their on-screen text names the
  language). The decision belongs to Janim.jl.
- **Comparing mp4s across the libraries measures the encoder.** Janim.py
  writes through the `PATH`'s ffmpeg (x264 core 165 on Fedora and Homebrew);
  Janim.jl through FFMPEG_jll's (core 164). `11_chase_camera` differs in 28
  frames at 54–58 dB with identical raw frames. Compare raw frames (the
  `frame_tap` harness), or pin the encoder on both sides.

## Testing and release

- **No test suite ships with the repository.** The release was verified with
  session harnesses: per-frame SHA-256 of every example and demo at 640×360
  and 10 fps, before and after each port (`Scene(..., frame_tap=...)`;
  `history/2026-10/LINUX.md`, §6). Turn that into a `tests/` suite with
  per-route reference hashes, and run it on the three platforms.
- **Not on PyPI.** Installation is a clone plus `scripts/bootstrap.sh`, which
  pins exact versions in `.venv/`. Decide whether to publish a wheel; the
  `[tool.janim.bootstrap]` dependencies would need a home in the metadata.
- **Keep `__version__` and `pyproject.toml` in sync.** They disagreed
  (`0.0.0` against `0.1.0`) until 1.0.0; a single source
  (`importlib.metadata` or a check) would stop it recurring.
- **`examples/assets/linux.svg` has mixed line endings** (90 CRLF lines out
  of 91). Harmless; normalize it or declare it in `.gitattributes`.
