"""Course 1 · 2.7 — Several scenes in one file

A scene is a CLASS, and one file may hold several of them. Address the one
you mean with a `:Name` suffix (or the name as the next argument) —
everywhere a scene file is accepted:

    janim render <this file>:Intro -qm         → 07_multiscene_Intro.mp4
    janim render <this file>:Orbit -qm         → 07_multiscene_Orbit.mp4
    janim render <this file>:Multiscene -qm    → the mix below
    janim <this file>:Orbit                    # live preview of THAT scene
    janim frame <this file>:Intro 30 out.png   # one frame of the intro
    janim render <this file>:Orbit -j 4        # the farm takes the name too

The rules, all of them small:

  · A file with ONE Scene subclass needs no suffix — every file you wrote
    before this lesson keeps working unchanged. A file with several must
    name one (the CLI refuses and lists them). `SCENE` below names this
    file's default scene.
  · The default output gains the name: `x.py:Intro` writes `x_Intro.mp4`,
    so two scenes of one file never fight over one file name.
  · The split is at the LAST `:`, and only when what is left of it ends
    in `.py` — `C:\\ruta\\x.py` is a Windows path, not an address.
  · A typo'd name fails naming the FILE and the SYMBOL. A scene is a class,
    so a helper like `wipe` below is never mistaken for one.
  · Checkpoints are kept PER SCENE: `Intro` and `Orbit` may both write
    `self.checkpoint("act2")` without ever crossing snapshots.

MIXING is the other half, and it costs zero machinery: another scene can
just CALL a scene's `construct` — Manim's `OtherScene.construct(self)`,
exactly. State FLOWS across the call (that is the point: mixing is
continuing the SAME scene); wipe the stage between parts when you want a
clean one. `Multiscene` is exactly that mix, so its render tells the whole
story.

    python examples/tutorial/c1_02_config_and_assets/07_multiscene.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 4.2                  # mid-orbit, trail already drawn


def wipe(scene):
    """Clear the stage between parts — the optional wipe, in one line.

    The camera frame lives in `scene.mobjects` too (as in ManimGL): keep it."""
    scene.remove_all_except(scene.frame)


# ── scene 1 · `Intro` — render it alone with  <file>:Intro ──────────────
class Intro(Scene):
    def construct(self):
        title = Text("several scenes, one file", size=0.62)
        title.to_edge(UP, buff=0.7)
        rule = Line((-3.4, 0, 0), (3.4, 0, 0))
        rule.set_stroke(GREY_B, width=3.0)
        rule.next_to(title, DOWN, buff=0.25)

        self.play(Write(title), run_time=2)
        self.play(ShowCreation(rule), run_time=0.6)

        tag = Text("this is “intro”", size=0.45, color=YELLOW)
        tag.next_to(rule, DOWN, buff=0.6)
        self.play(FadeIn(tag, shift=0.3 * UP), run_time=0.8)
        self.wait(0.4)


# ── scene 2 · `Orbit` — render it alone with  <file>:Orbit ──────────────
class Orbit(Scene):
    def construct(self):
        sun = Dot((0, -0.4, 0), radius=0.18)
        sun.set_fill(YELLOW)
        path = Circle(radius=1.7)
        path.set_stroke(GREY_C, width=2.0)
        path.move_to(sun.get_center())
        planet = Dot(path.point_from_proportion(0.0), radius=0.11)
        planet.set_fill("#2C5F8A")
        trail = TracedPath(
            planet.get_center,
            stroke_color="#2C5F8A",
            stroke_width=2.5,
        )

        self.add(sun, path, trail, planet)
        self.play(MoveAlongPath(planet, path), run_time=2.2)
        self.wait(0.3)


# ── the mix — this file's default scene ─────────────────────────────────
class Multiscene(Scene):
    def construct(self):
        Intro.construct(self)        # scene 1, called like any function
        wipe(self)                   # optional: without it, state FLOWS
        Orbit.construct(self)        # scene 2, on a clean stage


SCENE = Multiscene


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    Multiscene(output=str(out), fps=30, resolution=(854, 480)).render()
    print("→", out)
    print("now try:  bin/janim render", str(here) + ":Orbit", "-qm")
