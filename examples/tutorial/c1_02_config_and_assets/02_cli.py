"""Course 1 · 2.2 — The CLI

`bin/janim` runs one Python process per call: there is no daemon, so every
call pays its own start-up. `janim <this file>` with no verb
opens the live window — Esc or `q` closes it (so does Ctrl-C in the
terminal, or the window's close button).

    janim frame  <this file> 45 out.png      # frame 45, for looking at
    janim render <this file> -o out.mp4 -r 1280x720 --fps 30
    janim render <this file> --from act2     # draw nothing before the mark
    janim render <this file> -n 3,5          # only animations 3 to 5
    janim render <this file> -j 4            # the farm: 4 processes
    janim preview <this file>                # live window, hot reload, Esc/q quits
    janim states  <this file>                # says so: no snapshots outlive a process

Flags adopted from Manim: -r/--resolution, --fps, -o, -n, -p — and the
quality presets: -qs 360p10 · -ql 480p15 · -qm 720p30 · -qh 1080p60 ·
-qq 1440p60 · -qk 4K60. They are kept because you end up typing the geometry
EVERY time, and the numbers stay written out in the help instead of in
someone's head.

TWO WAYS TO CUT A LONG SCENE, and they are not the same tool:

    -n X,Y     numbers every play AND every wait, gates the DRAWING only
               (the scene is still simulated in full, which is what makes the
               output identical to those frames of the whole film).
               Sugar for exploring: insert one play and every number shifts.
    --from L   starts at `self.checkpoint("L")`. Anchored by NAME, so it
               survives edits. The CLI, one process per call,
               simulates the prefix WITHOUT DRAWING it. Inside one process,
               `render_from` keeps a snapshot, keyed by a hash of the file
               BEFORE the mark: edit the prefix and it invalidates itself.

    python examples/tutorial/c1_02_config_and_assets/02_cli.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 3.0


class Cli(Scene):
    def construct(self):
        title = Text("act 1", size=0.7, color=GREY_A)
        title.to_edge(UP, buff=0.5)
        self.add(title)

        # ── act 1 · animations 1–3 ───────────────────────────────────────
        dots = VGroup()
        for k in range(12):
            dot = Dot((-4.4 + 0.8 * k, 0.8, 0), radius=0.14)
            dot.set_fill("#2C5F8A")
            dots.add(dot)
        self.play(
            LaggedStart(
                *(FadeIn(dot) for dot in dots.submobjects),
                lag_ratio=0.12,
            ),
            run_time=1.5,
        )                                                        # animation 1
        self.play(dots.animate.rotate(TAU / 24), run_time=1.0)   # animation 2
        self.wait(0.5)                                           # animation 3

        # A checkpoint is one call, and it is the same call in both modes: in
        # a normal run it SAVES the state here; under `--from act2` it is
        # where the skipped prefix hands over. Keep it at top level of
        # construct — the invalidation hash is computed from its line in the
        # source.
        self.checkpoint("act2")

        # ── act 2 · animations 4–6 ───────────────────────────────────────
        act2 = Text("act 2", size=0.7, color=YELLOW)
        act2.to_edge(UP, buff=0.5)
        self.play(Transform(title, act2), run_time=0.8)         # animation 4
        ring = Circle(radius=1.6)
        ring.set_stroke(YELLOW, width=5.0)
        ring.set_fill(opacity=0)
        ring.move_to(1.1 * DOWN)
        self.play(ShowCreation(ring), run_time=1.2)              # animation 5
        self.wait(0.8)                                           # animation 6


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Cli(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
    print("now try:  bin/janim render", here, "-n 4,6 -o act2.mp4")
