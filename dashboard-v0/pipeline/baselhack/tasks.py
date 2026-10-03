"""Pixi task adapter accepting the brief's SCENE=... positional syntax."""

import argparse
import subprocess

from baselhack.cli import fetch
from baselhack.explain import explain
from baselhack.ml.decision_analysis import analyze
from baselhack.rules.engine import decide
from baselhack.scenario import build
from baselhack.simulator.journey import simulate
from baselhack.storage import ROOT, save


def run(task, scene):
    if (
        not (ROOT / "scenarios" / f"{scene}.yaml").is_file()
        or "/" in scene
        or "\\" in scene
    ):
        raise ValueError("Unknown scene")
    if task == "demo":
        import sys

        subprocess.run(["npm", "run", "build"], cwd=ROOT / "web", check=True)
        subprocess.run(
            [sys.executable, "-m", "baselhack.api", "--scene", scene], check=True
        )
        return
    scenario = build(scene)
    timeline = save("timeline", scene, simulate(scenario, scenario["seed"]))
    if task == "sim":
        return
    risk = save("risk", scene, analyze(scenario))
    if task == "ml":
        return
    decision = decide(scenario, timeline, risk)
    decision["explanation"] = explain(decision)
    save("decision", scene, decision)
    print(f"{scene}: {decision['recommended']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=["sim", "ml", "decide", "demo", "all"])
    parser.add_argument("scene", nargs="?", default="SCENE=s1_normal_2026-05-10")
    args = parser.parse_args()
    scene = args.scene.removeprefix("SCENE=")
    if args.task == "all":
        fetch()
        for path in sorted((ROOT / "scenarios").glob("*.yaml")):
            run("decide", path.stem)
    else:
        run(args.task, scene)
