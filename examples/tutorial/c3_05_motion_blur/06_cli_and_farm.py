"""Course 3 · 5.6 — Motion blur from the CLI, and the render farm

    janim render scene.py -o out.mp4 --motion-blur 8
    janim render scene.py -o out.mp4 --motion-blur 8,0.25    # n,shutter
    janim render scene.py -o out.mp4 --motion-blur 8 -j 4    # …across 4 processes

That is the flag as this lesson shows it on screen: `n` or `n,shutter`,
composing with `--from label` (skip to a checkpoint), `-j` (the farm),
`-r`/`--fps`. It belongs to a motion blur accumulated inside the frame loop;
Janim's CLI (`docs/cli.md`) has no `--motion-blur` and rejects it by name.
The commands stay on screen as the lesson's subject; the blurred still
(`render_frame_motion`, lesson 5.4) is what renders.

WHAT IT DOES NOT COMPOSE WITH, and the refusal is deliberate: `-n X,Y` (an
animation range) inside `render_parallel`. A worker whose frame range does
not intersect the animation range would emit an mp4 with NO frames, and
`ffmpeg -f concat` would splice an empty segment without complaining. So the
farm refuses the combination instead of producing a silently short film.

Two more practical notes:

  · for a BYTE-reproducible render, add `encoder_threads=1`. x264 is not
    bit-deterministic multi-threaded, and blurred content is exactly the
    high-frequency case where it shows. The FRAMES are deterministic either
    way.
  · cost is linear in n: the scene is simulated once and DRAWN n times.
    Check a still with `render_frame_motion` first (lesson 5.4).

    python examples/tutorial/c3_05_motion_blur/06_cli_and_farm.py
"""

from pathlib import Path

from janim import *

PREVIEW_T = 1.4
PREVIEW_MOTION = 8


class CliAndFarm(Scene):
    def construct(self):
        title = Text("--motion-blur N[,SHUTTER]", size=0.5, color=GREY_A)
        title.to_edge(UP, buff=0.4)
        self.add(title)

        commands = VGroup()
        for s in (
            "janim render scene.py -o out.mp4 --motion-blur 8",
            "janim render scene.py -o out.mp4 --motion-blur 8,0.25",
            "janim render scene.py -o out.mp4 --motion-blur 8 -j 4",
            "janim render scene.py -o out.mp4 --motion-blur 8 --from act2",
        ):
            commands.add(Text(s, size=0.32, color="#7FDD58", font="Liberation Mono"))
        commands.arrange(DOWN, buff=0.28, aligned_edge=LEFT)
        commands.move_to(1.4 * UP)
        self.add(commands)

        # Something moving, so the rendered file actually shows the flag's effect.
        runner = VGroup()
        for k in range(5):
            d = Dot((-5.4, -1.6 - 0.0 * k, 0), radius=0.18 - 0.02 * k)
            d.set_fill(color_gradient(["#39D0FF", "#FF3D8B"], 5)[k])
            runner.add(d)
        self.add(runner)

        self.play(
            LaggedStart(*(FadeIn(c) for c in commands.submobjects), lag_ratio=0.2),
            run_time=1.2,
        )
        self.play(
            AnimationGroup(
                *(d.animate(rate_func=linear).shift((10.6, 0, 0)) for d in runner.submobjects),
                lag_ratio=0.08,
            ),
            run_time=1.6,
        )
        self.wait(0.4)


if __name__ == "__main__":
    here = Path(__file__).resolve()
    out = here.parents[1] / "output" / here.parent.name / (here.stem + ".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    # The kwargs form of the flags minus the unsupported pair (motion_blur, shutter) —
    # plus the byte-reproducible encoder.
    CliAndFarm(output=str(out), fps=30, resolution=(854, 480), encoder_threads=1).render()
    print("→", out)
