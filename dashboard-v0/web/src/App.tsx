import { useEffect, useState } from "react";
import type {
  Action,
  Decision,
  Timeline,
  LogEntry,
  Role,
  DemoVariant as Variant,
} from "./interfaces";
const actions: Action[] = [
  "RUN_AS_PLANNED",
  "EXPEDITE",
  "BUFFER",
  "REROUTE",
  "QUARANTINE",
];
async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json()).error || "Output unavailable");
  return r.json();
}
const label = (a: string) => a.replaceAll("_", " ");
const time = (s: string) =>
  new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Europe/Zurich",
  }).format(new Date(s)) + " Basel";

export default function App() {
  const [scene, setScene] = useState(
    new URLSearchParams(location.search).get("scene") ||
      "s3_lowriver_2026-10-01",
  );
  const [scenes, setScenes] = useState<{ id: string; ready: boolean }[]>([]);
  const [decision, setDecision] = useState<Decision | null>(null),
    [timeline, setTimeline] = useState<Timeline | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]),
    [view, setView] = useState("Operator"),
    [error, setError] = useState("");
  const [role, setRole] = useState<Role>("operator"),
    [reason, setReason] = useState(""),
    [chosen, setChosen] = useState<Action>("BUFFER"),
    [busy, setBusy] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [variant, setVariant] = useState(""),
    [variants, setVariants] = useState<Variant[]>([]);
  const folder = `/snapshots/${scene}${variant ? "/variants/" + variant : ""}`;
  useEffect(() => {
    get<typeof scenes>("/api/scenes")
      .then(setScenes)
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    let current = true;
    setDecision(null);
    setTimeline(null);
    setLogs([]);
    setError("");
    setReason("");
    Promise.all([
      get<Decision>(`${folder}/decision.json`),
      get<Timeline>(`${folder}/timeline.json`),
      get<LogEntry[]>(`/snapshots/${scene}/log.json`),
    ])
      .then(([d, t, l]) => {
        if (current) {
          setDecision(d);
          setTimeline(t);
          setLogs(l);
          setChosen(d.recommended);
          setCursor(t.steps.length - 1);
        }
      })
      .catch((e) => {
        if (current) setError(String(e));
      });
    return () => {
      current = false;
    };
  }, [scene, variant]);
  useEffect(() => {
    get<Variant[]>(`/snapshots/${scene}/variants.json`)
      .then(setVariants)
      .catch(() => setVariants([]));
  }, [scene]);
  async function submit(verdict: "APPROVE" | "OVERRIDE") {
    if (!decision) return;
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: scene,
          variant,
          decision_id: decision.decision_id,
          by: role,
          verdict,
          reason,
          ...(verdict === "OVERRIDE" ? { chosen_action: chosen } : {}),
        }),
      });
      const value = await r.json();
      if (!r.ok) throw new Error(value.error);
      setLogs(value);
      setReason("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const steps = timeline?.steps || [],
    point = steps[cursor];
  const visible =
    view === "QA" ? steps : steps.filter((s) => s.segment !== "sea");
  const maxTemp = Math.max(12, ...visible.map((s) => s.product_c));
  const minTemp = Math.min(0, ...visible.map((s) => s.product_c));
  const y = (t: number) => 160 - ((t - minTemp) / (maxTemp - minTemp)) * 140;
  const start = visible.length ? Date.parse(visible[0].t) : 0,
    end = visible.length ? Date.parse(visible[visible.length - 1].t) : 1;
  const x = (t: string) =>
    30 + ((Date.parse(t) - start) / Math.max(1, end - start)) * 900;
  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">TEAM MANUX · CHALLENGE 4</p>
          <h1>Rhine to reactor</h1>
          <p>Will the material arrive, and is it still good to use?</p>
        </div>
        <span className="pill">OFFLINE DEMO · SIMULATED SHIPMENT</span>
      </header>
      <nav>
        {["Operator", "Decision", "Scenario controls", "QA"].map((v) => (
          <button
            key={v}
            className={view === v ? "active" : ""}
            onClick={() => setView(v)}
          >
            {v}
          </button>
        ))}
      </nav>
      <label className="scene">
        Scene{" "}
        <select
          value={scene}
          onChange={(e) => {
            setScene(e.target.value);
            setVariant("");
          }}
        >
          {scenes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id}
              {s.ready ? "" : " · verification pending"}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!decision && !error && <p>Loading cached evidence…</p>}
      {view === "Scenario controls" && (
        <section>
          <h2>Scenario controls</h2>
          <p>
            Independent, precomputed sensitivity controls. Select one at a time;
            observations stay unchanged. Current: {variant || "baseline"}.
          </p>
          <button onClick={() => setVariant("")}>Reset to baseline</button>
          {variants
            .filter((v) => v.id !== "early-unload")
            .map((v) => (
              <label className="control" key={v.id}>
                {v.label}
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="1"
                  value={variant === v.id ? 1 : 0}
                  disabled={!v.ready}
                  onChange={(e) =>
                    setVariant(e.target.value === "1" ? v.id : "")
                  }
                  aria-label={v.label}
                />
                <small>
                  {v.ready
                    ? `Baseline / ${v.value} ${v.unit} · ${v.recommended}`
                    : v.error}
                </small>
              </label>
            ))}
          {variants
            .filter((v) => v.id === "early-unload")
            .map((v) => (
              <button key={v.id} onClick={() => setVariant(v.id)}>
                {v.label} · {v.recommended}
              </button>
            ))}
        </section>
      )}
      {decision && timeline && view !== "Scenario controls" && (
        <>
          {(view === "Operator" || view === "QA") && (
            <section>
              <h2>
                {view === "QA"
                  ? `QA lot history · ${decision.lot}`
                  : "Shipment journey"}
              </h2>
              <p>
                {timeline.status === "suspended"
                  ? "Barge suspended under assumed navigation bands"
                  : `ETA ${timeline.eta ? time(timeline.eta) : "unknown"}`}{" "}
                · {decision.slot}
              </p>
              <div className="journey">
                {Array.from(new Set(steps.map((s) => s.segment))).map((s) => (
                  <span
                    key={s}
                    className={point?.segment === s ? "current" : ""}
                  >
                    {label(s)}
                  </span>
                ))}
              </div>
              <input
                className="scrub"
                type="range"
                min="0"
                max={Math.max(0, steps.length - 1)}
                value={cursor}
                onChange={(e) => setCursor(Number(e.target.value))}
                aria-label="Container journey position"
              />
              <p>
                {point ? time(point.t) : ""} · {label(point?.segment || "")} ·
                simulated product {point?.product_c.toFixed(1)} °C
              </p>
              <h3>Product temperature · real ambient / simulated product</h3>
              <svg
                viewBox="0 0 960 190"
                role="img"
                aria-label="Product temperature trace, shaded exposure periods, and 2 to 8 degree band"
              >
                <rect
                  x="30"
                  y={y(8)}
                  width="900"
                  height={y(2) - y(8)}
                  fill="var(--band)"
                />
                {visible
                  .filter(
                    (s, i) =>
                      !s.refrigerated &&
                      (i === 0 || visible[i - 1].segment !== s.segment),
                  )
                  .map((s) => {
                    const last = visible
                      .filter((p) => p.segment === s.segment)
                      .at(-1)!;
                    return (
                      <rect
                        key={s.t}
                        x={x(s.t)}
                        y="10"
                        width={Math.max(2, x(last.t) - x(s.t))}
                        height="160"
                        fill="var(--exposure)"
                      />
                    );
                  })}
                <polyline
                  points={visible
                    .map((s) => `${x(s.t)},${y(s.product_c)}`)
                    .join(" ")}
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="3"
                />
                <text x="3" y={y(8)}>
                  8°
                </text>
                <text x="3" y={y(2)}>
                  2°
                </text>
              </svg>
              <p>
                Excursion budget used: {(timeline.budget_used * 100).toFixed(1)}
                % · cumulative, including recovery
              </p>
              <progress max="1" value={Math.min(1, timeline.budget_used)} />
              <small>
                Budget and thermal response are ASSUMED; QA alone decides
                quarantine or release.
              </small>
            </section>
          )}
          <section className="decision">
            <p className="eyebrow">RECOMMENDATION · HUMAN DECISION REQUIRED</p>
            <h2>{label(decision.recommended)}</h2>
            <p className="headline">{decision.headline}</p>
            <p>{decision.explanation}</p>
            <ol>
              {decision.reasons.map((r) => (
                <li key={r.n}>
                  {r.text}
                  <small>
                    {r.source} · {time(r.at)}
                  </small>
                </li>
              ))}
            </ol>
            <details open={view === "Decision" || view === "QA"}>
              <summary>Rejected options</summary>
              {decision.rejected.map((r) => (
                <p key={r.action}>
                  <strong>{label(r.action)}</strong>: {r.reason}
                  <small>
                    {r.source} · {time(r.at)}
                  </small>
                </p>
              ))}
            </details>
            <h3>Would change if</h3>
            <ul>
              {decision.would_change_if.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <p>
              Required approver:{" "}
              <strong>{decision.requires_approval_by}</strong>. Role selector is
              a demo label, without authentication.
            </p>
            <label>
              Acting role{" "}
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as Role)}
              >
                {(["operator", "logistics", "QA"] as Role[]).map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <label>
              Reason{" "}
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Confirm evidence or explain your override"
              />
            </label>
            <div className="buttons">
              <button
                disabled={
                  busy ||
                  !reason.trim() ||
                  role !== decision.requires_approval_by
                }
                onClick={() => submit("APPROVE")}
              >
                Approve
              </button>
              <select
                aria-label="Override action"
                value={chosen}
                onChange={(e) => setChosen(e.target.value as Action)}
              >
                {actions.map((a) => (
                  <option key={a}>{a}</option>
                ))}
              </select>
              <button
                disabled={busy || !reason.trim()}
                onClick={() => submit("OVERRIDE")}
              >
                Override with reason
              </button>
            </div>
          </section>
          <p>
            <a href="https://opendatadocs.meteoswiss.ch/general/terms-of-use">
              Source: MeteoSwiss
            </a>{" "}
            ·{" "}
            <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>{" "}
            · PEGELONLINE. Cached observations trimmed; shipment and thermal
            outputs simulated.
          </p>
          <section>
            <h2>Decision log</h2>
            {logs.length === 0 ? (
              <p>No decisions recorded.</p>
            ) : (
              logs.map((l, i) => (
                <article key={i}>
                  <strong>
                    {l.verdict} · {l.chosen_action || decision.recommended}
                  </strong>
                  <p>
                    {l.by} · {time(l.at)} · {l.reason}
                  </p>
                  <small>
                    Evidence snapshot SHA-256: {l.decision_snapshot_sha256}
                  </small>
                </article>
              ))
            )}
          </section>
        </>
      )}
    </main>
  );
}
