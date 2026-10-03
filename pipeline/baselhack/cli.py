import typer

from baselhack.explain import explain
from baselhack.ml.decision_analysis import analyze
from baselhack.rules.engine import decide as choose
from baselhack.scenario import build
from baselhack.simulator.journey import simulate
from baselhack.storage import ROOT, read_json, read_yaml, save

app = typer.Typer(no_args_is_help=True)


def run_scene(scene):
    scenario = build(scene)
    timeline = save("timeline", scene, simulate(scenario, scenario["seed"]))
    risk = save("risk", scene, analyze(scenario))
    decision = choose(scenario, timeline, risk)
    decision["explanation"] = explain(decision)
    save("decision", scene, decision)
    return decision


@app.command()
def fetch():
    from baselhack.loaders import basel_traffic, meteoswiss, openmeteo, pegelonline
    from baselhack.loaders.common import cache

    river = pegelonline.download()
    basel, basel_source = meteoswiss.temperatures()
    basel_traffic.download()
    for path in sorted((ROOT / "scenarios").glob("*.yaml")):
        config = read_yaml(path.relative_to(ROOT))
        start = config["evidence_date"]
        end = config.get("evidence_end_date", start)
        rotterdam, rotterdam_source = openmeteo.temperatures(start, end)

        def in_window(rows, start=start, end=end):
            return [p for p in rows if start <= p["t"][:10] <= end]

        kaub = in_window(river["KAUB_W"]["rows"])
        basel_gauge = in_window(river["Basel-Rheinhalle_W"]["rows"])
        verification = [
            "TODO(verify): traffic station selection; neutral ASSUMED factor used",
            "TODO(verify): Basel high-water stop threshold",
            "TODO(verify): Port of Switzerland navigation bands",
        ]
        if not kaub:
            verification.append(
                "Historical river unavailable: explicitly simulated sensitivity as v1.1 permits"
            )
        payload = {
            "ambient": {"basel": in_window(basel), "rotterdam": rotterdam},
            "rhine": {"kaub_cm": kaub, "basel_cm": basel_gauge},
            "traffic": {},
            "verification": verification,
            "sources": {
                "basel": basel_source + " tre200h0, UTC",
                "rotterdam": rotterdam_source + " reanalysis",
                "kaub_cm": river["KAUB_W"].get(
                    "source", "PEGELONLINE KAUB/W unavailable"
                ),
                "basel_cm": river["Basel-Rheinhalle_W"].get(
                    "source", "PEGELONLINE Basel/W unavailable"
                ),
                "traffic": "ASSUMED neutral factor pending verified station choice",
            },
        }
        # Existing historical evidence is immutable: never erase cached data with a rolling fetch.
        target = ROOT / "data" / "cache" / config["cache"]
        if target.exists():
            typer.echo(
                f"Preserved {target.name}; fresh raw/window downloads available for review"
            )
        else:
            cache(config["cache"], payload)


@app.command("simulate")
def simulate_command(scene: str = "s3_lowriver_2026-10-01"):
    scenario = build(scene)
    save("timeline", scene, simulate(scenario, scenario["seed"]))


@app.command("risk")
def risk_command(scene: str = "s3_lowriver_2026-10-01"):
    save("risk", scene, analyze(read_json(f"snapshots/{scene}/scenario.json")))


@app.command("decide")
def decide_command(scene: str = "s3_lowriver_2026-10-01"):
    decision = choose(
        read_json(f"snapshots/{scene}/scenario.json"),
        read_json(f"snapshots/{scene}/timeline.json"),
        read_json(f"snapshots/{scene}/risk.json"),
    )
    decision["explanation"] = explain(decision)
    save("decision", scene, decision)


@app.command("all")
def all_command():
    failed = []
    for path in sorted((ROOT / "scenarios").glob("*.yaml")):
        try:
            result = run_scene(path.stem)
            typer.echo(f"{path.stem}: {result['recommended']}")
        except ValueError as error:
            failed.append(path.stem)
            typer.echo(f"{path.stem}: {error}", err=True)
    if failed:
        raise typer.Exit(1)


@app.command()
def verify():
    checks = read_yaml("config/verification.yaml")["checks"]
    pending = [
        f"TODO(verify): {c['id']}: {c['detail']}" for c in checks if not c["verified"]
    ]
    for item in pending:
        typer.echo(item, err=True)
    if pending:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
