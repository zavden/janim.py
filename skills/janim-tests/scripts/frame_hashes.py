#!/usr/bin/env python
"""frame_hashes.py — the SHA-256 of every frame of every example scene, one process per scene.

    frame_hashes.py seal OUT_DIR [--only SUBSTR]... [--size WxH] [--fps N]
    frame_hashes.py compare BEFORE_DIR AFTER_DIR
    frame_hashes.py one SCENE.py CLASS OUT.tsv [--size WxH] [--fps N]
    frame_hashes.py list SCENE.py
    frame_hashes.py driver

`seal` finds every `Scene` subclass defined in examples/{tutorial,gallery,scenes,demo}
(skipping the `*.es.py` twins and `output/` folders), renders each one in its own
process at 640×360 and 10 fps by default, and writes to OUT_DIR:

    <relative path with __ for />__<Class>.tsv    one `index<TAB>sha256` line per frame
    summary.tsv                                   scene, class, frames, seconds — or ERR and the last line
    driver.txt                                    the route that ran, the Python and the git HEAD

The hashes are of the raw RGB bytes handed to `Scene(frame_tap=…)`, before the encoder,
so the mp4 container never enters the comparison. `--only` restricts the sweep to the
scenes whose path or class contains the substring (repeatable).

`compare` prints SAME, DIFFER n/N (first frame k) or MISSING per scene and the totals,
and exits 1 when anything differs or is missing. `one` is what `seal` runs per scene;
`list` prints the Scene subclasses a file defines; `driver` prints the route line.

Run it with the checkout's interpreter from the checkout root:

    .venv/bin/python skills/janim-tests/scripts/frame_hashes.py seal output/frames/before
"""

import argparse
import hashlib
import importlib.util
import inspect
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
EXAMPLE_FOLDERS = ("tutorial", "gallery", "scenes", "demo")


def load_module(path):
    """Import a scene file by path, with its folder first on sys.path (lessons import siblings)."""
    path = Path(path).resolve()
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scene_classes(module):
    from janim import Scene

    return sorted(
        name
        for name, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, Scene) and cls is not Scene and cls.__module__ == module.__name__
    )


def command_list(args):
    for name in scene_classes(load_module(args.scene)):
        print(name)


def command_one(args):
    width, height = parse_size(args.size)
    module = load_module(args.scene)
    cls = getattr(module, args.cls)
    hashes = []
    with tempfile.TemporaryDirectory() as tmp:
        start = time.perf_counter()
        scene = cls(
            output=os.path.join(tmp, "x.mp4"),
            fps=args.fps,
            resolution=(width, height),
            frame_tap=lambda index, pixels: hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest()),
        )
        scene.render()
        elapsed = time.perf_counter() - start
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{index}\t{digest}\n" for index, digest in enumerate(hashes)), encoding="utf-8")
    print(f"{len(hashes)}\t{elapsed:.1f}")


def command_driver(args):
    from janim import driver_header, gpu_info

    print(driver_header(gpu_info()))


def child(*argv, timeout):
    """Run this script again in a fresh interpreter: one device and one import of the tree per scene."""
    return subprocess.run(
        [sys.executable, "-I", str(HERE), *argv],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=timeout,
    )


def last_line(text):
    lines = text.strip().splitlines()
    return lines[-1][:200] if lines else ""


def scene_files():
    return sorted(
        path
        for folder in EXAMPLE_FOLDERS
        for path in (ROOT / "examples" / folder).rglob("*.py")
        if path.name != "__init__.py" and not path.name.endswith(".es.py") and "output" not in path.parts
    )


def command_seal(args):
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    only = args.only or []
    files = scene_files()
    header = child("driver", timeout=600)
    git_head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    (out / "driver.txt").write_text(
        f"{header.stdout.strip() or 'ERR ' + last_line(header.stderr)}\n"
        f"# python: {sys.version.split()[0]}\n"
        f"# git: {git_head or 'unknown'}\n"
        f"# size: {args.size} @ {args.fps} fps\n",
        encoding="utf-8",
    )
    count = 0
    start_all = time.time()
    # A lowercase --only token filters PATHS before any import; a token with a
    # capital letter names a CLASS and needs the listing to decide.
    path_tokens = [token for token in only if token == token.lower()]
    class_tokens = [token for token in only if token != token.lower()]
    with open(out / "summary.tsv", "w", encoding="utf-8") as summary:
        for path in files:
            rel = path.relative_to(ROOT / "examples")
            if only and not class_tokens and not any(token in str(rel) for token in path_tokens):
                continue
            listing = child("list", str(path), timeout=600)
            if listing.returncode != 0:
                summary.write(f"{rel}\t-\tLISTERR {last_line(listing.stderr)}\n")
                summary.flush()
                continue
            for cls in listing.stdout.split():
                if only and not any(token in str(rel) or token in cls for token in only):
                    continue
                tsv = out / (str(rel).replace("/", "__").removesuffix(".py") + "__" + cls + ".tsv")
                started = time.time()
                run = child("one", str(path), cls, str(tsv), "--size", args.size, "--fps", str(args.fps), timeout=1800)
                if run.returncode == 0:
                    frames, seconds = last_line(run.stdout).split("\t")
                    status = f"{frames}\t{seconds}"
                else:
                    status = f"ERR {last_line(run.stderr)}\t{time.time() - started:.1f}"
                summary.write(f"{rel}\t{cls}\t{status}\n")
                summary.flush()
                count += 1
                print(f"{rel}:{cls}\t{status}", flush=True)
    print(f"{count} scenes in {time.time() - start_all:.0f} s → {out}")


def command_compare(args):
    before, after = Path(args.before), Path(args.after)
    names = sorted(({p.name for p in before.glob("*.tsv")} | {p.name for p in after.glob("*.tsv")}) - {"summary.tsv"})
    same = differ = missing = 0
    for name in names:
        first, second = before / name, after / name
        if not first.exists() or not second.exists():
            side = "only in before" if first.exists() else "only in after"
            print(f"MISSING  {name}  ({side})")
            missing += 1
            continue
        lines_a = first.read_text(encoding="utf-8").splitlines()
        lines_b = second.read_text(encoding="utf-8").splitlines()
        if lines_a == lines_b and lines_a:
            same += 1
            continue
        bad = [index for index, (x, y) in enumerate(zip(lines_a, lines_b)) if x != y]
        total = max(len(lines_a), len(lines_b))
        count = len(bad) + abs(len(lines_a) - len(lines_b))
        first_bad = bad[0] if bad else min(len(lines_a), len(lines_b))
        print(f"DIFFER   {name}  {count}/{total} (first frame {first_bad})")
        differ += 1
    print(f"same {same}  differ {differ}  missing {missing}  total {len(names)}")
    return 1 if differ or missing else 0


def parse_size(text):
    width, height = text.lower().split("x")
    return int(width), int(height)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    seal = sub.add_parser("seal", help="hash every example scene into OUT_DIR")
    seal.add_argument("out_dir")
    seal.add_argument("--only", action="append", help="only scenes whose path or class contains this (repeatable)")
    seal.add_argument("--size", default="640x360")
    seal.add_argument("--fps", type=int, default=10)
    seal.set_defaults(run=command_seal)

    compare = sub.add_parser("compare", help="compare two sealed directories")
    compare.add_argument("before")
    compare.add_argument("after")
    compare.set_defaults(run=command_compare)

    one = sub.add_parser("one", help="hash one scene into OUT.tsv")
    one.add_argument("scene")
    one.add_argument("cls")
    one.add_argument("out")
    one.add_argument("--size", default="640x360")
    one.add_argument("--fps", type=int, default=10)
    one.set_defaults(run=command_one)

    listing = sub.add_parser("list", help="print the Scene subclasses a file defines")
    listing.add_argument("scene")
    listing.set_defaults(run=command_list)

    driver = sub.add_parser("driver", help="print the route line of driver_header(gpu_info())")
    driver.set_defaults(run=command_driver)

    args = parser.parse_args(argv)
    return args.run(args) or 0


if __name__ == "__main__":
    sys.exit(main())
