"""Course 1 · 2.3 — The settings dict (Manim's config dict)

CE's `config["frame_rate"]` and `with tempconfig({…})` are a global mutable
dictionary. Janim's equivalent is a plain dict that you splat into the
scene, and it is better in the two ways that matter: it is LOCAL (two scenes
in one session cannot fight over it) and it is VISIBLE (the settings that
made the video are in the call, not in a file somewhere).

    DRAFT = dict(fps=15, resolution=(640, 360), crf=30)
    FINAL = dict(fps=60, resolution=(1920, 1080), crf=18, preset="slow", encoder_threads=1)

    MyScene(output="x.mp4", **DRAFT).render()
    MyScene(output="x.mp4", **FINAL).render()

The same dict feeds the whole family, because they take the same kwargs:
`render_frame`, `render_segment`, `render_parallel` (the live window,
`janim.interactive.live.live`, takes `fps` and `resolution`).

One setting deserves naming: `encoder_threads=1`. x264 is NOT
bit-deterministic multi-threaded, so a render you want to be identical
twice — blurred or high-contrast content especially — asks for one thread.
The FRAMES are always deterministic; it is the encoder that is not.

    python examples/tutorial/c1_02_config_and_assets/03_config_dict.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.2

# Fast and ugly: for iterating.
DRAFT = dict(
    fps=15,
    resolution=(640, 360),
    crf=30,
    preset="veryfast",
)

# Slow and exact: for the film, and reproducible.
FINAL = dict(
    fps=60,
    resolution=(1920, 1080),
    crf=18,
    preset="slow",
    encoder_threads=1,
)

# What the tutorial actually renders.
TUTORIAL = dict(
    fps=30,
    resolution=(854, 480),
)


class ConfigDict(Scene):
    def construct(self):
        title = Text("one NamedTuple, splatted", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)

        # The scene READS its own settings: nothing here is hard-coded twice.
        facts = [
            f"fps        {self.fps}",
            f"pixels     {self.camera.width}×{self.camera.height}",
            f"seconds/frame  {round(1 / self.fps, 4)}",
        ]
        rows = VGroup()
        for fact in facts:
            rows.add(Text(fact, size=0.42, color=GREY_B))
        rows.arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        rows.shift(0.6 * UP)

        # A bar whose length is the frame interval, drawn at a fixed scale: at
        # 15 fps it is four times the 60 fps one, which is the whole point of
        # a draft profile — fewer, longer steps.
        bar = Rectangle(width=max(0.2, 60 / self.fps), height=0.45)
        bar.set_fill(BLUE, 1.0)
        bar.set_stroke(opacity=0)
        bar.move_to(1.6 * DOWN)
        label = Text("one frame, to scale", size=0.33, color=GREY_C)
        label.next_to(bar, DOWN, buff=0.25)

        self.add(title, rows, bar, label)
        self.play(GrowFromEdge(bar, LEFT), run_time=0.8)
        self.wait(0.8)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    ConfigDict(output=str(out), **TUTORIAL).render()      # ← swap for DRAFT / FINAL
    print("→", out)
