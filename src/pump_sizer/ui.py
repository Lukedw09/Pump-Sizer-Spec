"""Development server for the pump sizer page.

The page to open and email is ``Pump Sizer.html`` in the repo root. It is
self-contained and does not use this server. Physics stay in SI; the page
speaks bar, kW, mm, and rpm.
"""

from __future__ import annotations

import argparse
import base64
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pump_sizer.constants import PAIRS
from pump_sizer.plot import figure_png
from pump_sizer.sweep import CaseInputs, CaseResult, evaluate

_EVAL_LOCK = threading.Lock()

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pump sizer</title>
<style>
  :root {
    --bg: #f3f0e8;
    --ink: #1b1916;
    --muted: #5e584e;
    --line: #ddd6c8;
    --panel: #fffdf9;
    --accent: #0e4d5c;
    --warn-bg: #fff4ec;
    --warn: #8c3d12;
    --ox: #0072b2;
    --fuel: #9a6200;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font: 14px/1.4 "Segoe UI", system-ui, sans-serif;
  }
  header {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: baseline;
    padding: 16px 22px 8px;
  }
  h1 { font-size: 20px; font-weight: 650; margin: 0; }
  header p { margin: 0; color: var(--muted); font-size: 13px; }
  #status { color: var(--accent); font-variant-numeric: tabular-nums; }
  #answer {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin: 0 18px 10px;
  }
  .layout {
    display: grid;
    grid-template-columns: 420px minmax(0, 1fr);
    gap: 16px;
    padding: 8px 18px 28px;
    align-items: start;
  }
  .panel {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px 14px 14px;
  }
  #form { max-height: calc(100vh - 78px); overflow: auto; }
  h2 {
    margin: 14px 0 4px;
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--muted);
  }
  h2:first-child { margin-top: 2px; }
  .hint { margin: 0 0 8px; color: var(--muted); font-size: 12px; }
  .field {
    display: grid;
    grid-template-columns: 132px minmax(0, 1fr) 88px 42px;
    gap: 6px;
    align-items: center;
    margin: 6px 0;
  }
  .field span:first-child { font-size: 13px; }
  .unit { color: var(--muted); font-size: 12px; }
  input[type="number"], select {
    font: inherit;
    width: 100%;
    padding: 4px 6px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: white;
    font-variant-numeric: tabular-nums;
  }
  input[type="range"] { width: 100%; accent-color: var(--accent); }
  select { grid-column: 2 / span 2; }
  button {
    margin-top: 12px;
    font: inherit;
    background: var(--accent);
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 7px 12px;
    cursor: pointer;
  }
  button:hover { filter: brightness(1.08); }
  #error {
    min-height: 1.2em;
    margin: 8px 0 0;
    color: var(--warn);
    font-size: 13px;
  }
  .stat {
    background: #f6f3ec;
    border-radius: 8px;
    padding: 8px 10px;
  }
  .stat span { display: block; color: var(--muted); font-size: 12px; }
  .stat b {
    display: block;
    margin-top: 2px;
    font-size: 18px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { text-align: right; padding: 4px 6px; border-bottom: 1px solid var(--line); }
  th:first-child, td:first-child { text-align: left; color: var(--muted); }
  th.ox { color: var(--ox); }
  th.fuel { color: var(--fuel); }
  #plot {
    width: 100%;
    height: auto;
    margin-top: 8px;
    background: white;
    border-radius: 8px;
  }
  .warnings { margin: 8px 0 0; padding-left: 18px; }
  .warnings li { margin: 3px 0; color: var(--warn); }
  .quiet { color: var(--muted); list-style: none; margin-left: -18px; }
  .facts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px 12px;
    margin: 0 0 10px;
    font-variant-numeric: tabular-nums;
  }
  .facts span { display: block; color: var(--muted); font-size: 12px; }
  @media (max-width: 980px) {
    .layout { grid-template-columns: 1fr; }
    #form { max-height: none; }
    #answer, .facts { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<header>
  <div>
    <h1>Few-kN pump sizer</h1>
    <p>Meanline LOX/RP-1 and LOX/ethanol. Change an input and the result follows.</p>
  </div>
  <p id="status">Starting</p>
</header>
<div id="answer"></div>
<p id="error"></p>
<div class="layout">
  <form id="form" class="panel"></form>
  <section class="panel">
    <div id="details"></div>
    <ul id="warnings" class="warnings"></ul>
    <img id="plot" alt="Cavitation margin and impeller diameter versus shaft speed">
  </section>
</div>
<script>
const statusEl = document.querySelector("#status");
const errorEl = document.querySelector("#error");
let nominal = {};
let timer = 0;
let seq = 0;

function esc(value) {
  return String(value).replace(/[&<>]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[ch]));
}

function num(value, digits) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function renderField(field) {
  const row = document.createElement("label");
  row.className = "field";
  const name = document.createElement("span");
  name.textContent = field.label;
  row.appendChild(name);
  if (field.kind === "choice") {
    const select = document.createElement("select");
    select.id = field.key;
    select.dataset.key = field.key;
    select.dataset.default = field.default;
    for (const choice of field.choices) {
      const option = document.createElement("option");
      option.value = choice;
      option.textContent = choice;
      select.appendChild(option);
    }
    select.value = field.default;
    select.addEventListener("change", () => {
      onPairChange();
      schedule();
    });
    row.append(select, document.createElement("span"));
    return row;
  }
  const range = document.createElement("input");
  range.type = "range";
  range.min = field.min;
  range.max = field.max;
  range.step = field.step;
  range.value = field.default;
  const number = document.createElement("input");
  number.type = "number";
  number.id = field.key;
  number.dataset.key = field.key;
  number.step = String(field.step);
  number.value = String(field.default);
  number.dataset.default = String(field.default);
  range.addEventListener("input", () => {
    number.value = range.value;
    if (field.key === "mixture_ratio") number.dataset.userEdited = "1";
    schedule();
  });
  number.addEventListener("input", () => {
    if (number.value !== "" && !Number.isNaN(Number(number.value))) range.value = number.value;
    if (field.key === "mixture_ratio") number.dataset.userEdited = "1";
    schedule();
  });
  const unit = document.createElement("span");
  unit.className = "unit";
  unit.textContent = field.unit;
  row.append(range, number, unit);
  return row;
}

function onPairChange() {
  const pair = document.querySelector("#pair").value;
  const ratio = document.querySelector("#mixture_ratio");
  const next = nominal[pair];
  const previous = ratio.dataset.nominal;
  if (ratio.dataset.userEdited !== "1" || ratio.value === previous) {
    ratio.value = next;
    const range = ratio.parentElement.querySelector("input[type=range]");
    if (range) range.value = next;
    ratio.dataset.userEdited = "0";
  }
  ratio.dataset.nominal = String(next);
  const hint = document.querySelector("#nominal-hint");
  if (hint) {
    hint.textContent = "Tabulated c* is for r = " + next + ". More than 0.3 away warns and does not retune c*.";
  }
}

function fillDefaults() {
  for (const el of document.querySelectorAll("[data-default]")) {
    if (el.dataset.key === "pair") el.value = el.dataset.default;
    else el.value = el.dataset.default;
    const range = el.parentElement.querySelector("input[type=range]");
    if (range) range.value = el.dataset.default;
    if (el.dataset.key === "mixture_ratio") el.dataset.userEdited = "0";
  }
  onPairChange();
}

function payload() {
  const body = {};
  for (const el of document.querySelectorAll("[data-key]")) {
    body[el.dataset.key] = el.dataset.key === "pair" ? el.value : Number(el.value);
  }
  return body;
}

function answerHtml(data) {
  const side = data.limiting_side === "ox" ? "Oxidizer" : data.limiting_side === "fuel" ? "Fuel" : "Neither";
  const rpm = data.limiting_rpm === null ? "none" : num(data.limiting_rpm, 0) + " rpm";
  const cards = [
    ["Limiting speed", rpm],
    ["Limiting pump", side],
    ["Oxidizer diameter", data.ox.d2_mm === null ? "n/a" : num(data.ox.d2_mm, 2) + " mm"],
    ["Fuel diameter", data.fuel.d2_mm === null ? "n/a" : num(data.fuel.d2_mm, 2) + " mm"],
  ];
  return cards.map(([label, value]) => `<div class="stat"><span>${label}</span><b>${esc(value)}</b></div>`).join("");
}

function row(label, ox, fuel) {
  return `<tr><td>${label}</td><td>${ox}</td><td>${fuel}</td></tr>`;
}

function detailsHtml(data) {
  const eng = data.engine;
  const facts = [
    ["c*", num(eng.cstar_m_s, 1) + " m/s"],
    ["Cf", num(eng.cf, 3)],
    ["ve", num(eng.ve_m_s, 1) + " m/s"],
    ["Isp", num(eng.isp_s, 1) + " s"],
    ["mass flow", num(eng.m_dot_kg_s, 3) + " kg/s"],
    ["oxidizer flow", num(eng.m_dot_ox_kg_s, 3) + " kg/s"],
    ["fuel flow", num(eng.m_dot_f_kg_s, 3) + " kg/s"],
    ["oxidizer volume", num(eng.q_ox_l_s, 3) + " L/s"],
    ["fuel volume", num(eng.q_f_l_s, 3) + " L/s"],
    ["total power", num(data.power_total_kw, 3) + " kW"],
  ].map(([label, value]) => `<div><span>${label}</span><b>${value}</b></div>`).join("");
  const ox = data.ox;
  const fuel = data.fuel;
  const pumpRows = [
    row("zero-cross", ox.zero_rpm === null ? "none" : num(ox.zero_rpm, 0) + " rpm", fuel.zero_rpm === null ? "none" : num(fuel.zero_rpm, 0) + " rpm"),
    row("power", num(ox.power_kw, 3) + " kW", num(fuel.power_kw, 3) + " kW"),
    row("diameter at limit", ox.d2_mm === null ? "n/a" : num(ox.d2_mm, 2) + " mm", fuel.d2_mm === null ? "n/a" : num(fuel.d2_mm, 2) + " mm"),
    row("margin at limit", ox.margin_m === null ? "n/a" : num(ox.margin_m, 3) + " m", fuel.margin_m === null ? "n/a" : num(fuel.margin_m, 3) + " m"),
    row("NPSHa", num(ox.npsha_m, 2) + " m", num(fuel.npsha_m, 2) + " m"),
    row("discharge", num(ox.p_d_bar, 2) + " bar", num(fuel.p_d_bar, 2) + " bar"),
    row("suction", num(ox.p_s_bar, 2) + " bar", num(fuel.p_s_bar, 2) + " bar"),
    row("pressure rise", num(ox.dp_bar, 2) + " bar", num(fuel.dp_bar, 2) + " bar"),
    row("specific speed", ox.omega_s === null ? "n/a" : num(ox.omega_s, 3), fuel.omega_s === null ? "n/a" : num(fuel.omega_s, 3)),
  ].join("");
  return `<div class="facts">${facts}</div><table>
    <tr><th></th><th class="ox">Oxidizer</th><th class="fuel">Fuel</th></tr>
    ${pumpRows}
  </table>`;
}

function warningsHtml(warnings) {
  if (!warnings.length) return `<li class="quiet">No warnings.</li>`;
  return warnings.map((warning) => `<li>${esc(warning)}</li>`).join("");
}

async function run() {
  const id = ++seq;
  statusEl.textContent = "Updating";
  let response;
  try {
    response = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
  } catch (err) {
    if (id !== seq) return;
    statusEl.textContent = "Not updated";
    errorEl.textContent = "Could not reach the sizer.";
    return;
  }
  if (id !== seq) return;
  const data = await response.json();
  if (!data.ok) {
    statusEl.textContent = "Not updated";
    errorEl.textContent = data.error;
    return;
  }
  errorEl.textContent = "";
  statusEl.textContent = "Updated";
  document.querySelector("#answer").innerHTML = answerHtml(data);
  document.querySelector("#details").innerHTML = detailsHtml(data);
  document.querySelector("#warnings").innerHTML = warningsHtml(data.warnings);
  document.querySelector("#plot").src = "data:image/png;base64," + data.plot_png;
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(run, 160);
}

async function init() {
  const schema = await (await fetch("/api/schema")).json();
  nominal = schema.nominal_r;
  const form = document.querySelector("#form");
  form.addEventListener("submit", (event) => event.preventDefault());
  let group = "";
  for (const field of schema.fields) {
    if (field.group !== group) {
      group = field.group;
      const heading = document.createElement("h2");
      heading.textContent = group;
      form.appendChild(heading);
      if (group === "Speed window") {
        const hint = document.createElement("p");
        hint.className = "hint";
        hint.textContent = "The figure uses this window. The cavitation limit is still reported when it sits above it. Raise maximum rpm to watch the margin cross zero.";
        form.appendChild(hint);
      }
      if (group === "Assumptions") {
        const hint = document.createElement("p");
        hint.className = "hint";
        hint.textContent = "Pump efficiency 0.55 is optimistic for a few-kN machined impeller. Specific speed outside 0.4-1.5 warns and does not change the head coefficient.";
        form.appendChild(hint);
      }
    }
    form.appendChild(renderField(field));
    if (field.key === "mixture_ratio") {
      const hint = document.createElement("p");
      hint.id = "nominal-hint";
      hint.className = "hint";
      form.appendChild(hint);
    }
  }
  const reset = document.createElement("button");
  reset.type = "button";
  reset.textContent = "Reset defaults";
  reset.addEventListener("click", () => {
    fillDefaults();
    schedule();
  });
  form.appendChild(reset);
  onPairChange();
  schedule();
}

init();
</script>
</body>
</html>
"""


def _bar(pascals: float) -> float:
    return round(pascals / 1e5, 6)


def _number(key, label, unit, group, default, low, high, step):
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "group": group,
        "kind": "number",
        "default": default,
        "min": low,
        "max": high,
        "step": step,
    }


def field_schema() -> list[dict]:
    """Display-unit fields. Pressures are bar on the page and pascals in the model."""
    defaults = CaseInputs()
    return [
        {
            "key": "pair",
            "label": "Propellants",
            "unit": "",
            "group": "Mission",
            "kind": "choice",
            "choices": list(PAIRS),
            "default": defaults.pair,
        },
        _number("thrust_n", "Thrust", "N", "Mission", defaults.thrust, 500, 20000, 50),
        _number("p_c_bar", "Chamber pressure", "bar", "Mission", _bar(defaults.p_c), 5, 80, 0.1),
        _number("mixture_ratio", "Mixture ratio", "ox/fuel", "Mission", defaults.mixture_ratio, 0.8, 3.5, 0.01),
        _number("eps", "Expansion ratio", "", "Mission", defaults.eps, 2, 40, 0.5),
        _number("p_tank_ox_bar", "Oxidizer tank", "bar", "Tanks", _bar(defaults.p_tank_ox), 1, 20, 0.1),
        _number("p_tank_f_bar", "Fuel tank", "bar", "Tanks", _bar(defaults.p_tank_f), 1, 20, 0.1),
        _number("dp_suction_bar", "Suction loss", "bar", "Tanks", _bar(defaults.dp_suction), 0, 5, 0.05),
        _number("rpm_min", "Minimum rpm", "rpm", "Speed window", defaults.rpm_min, 1000, 100000, 500),
        _number("rpm_max", "Maximum rpm", "rpm", "Speed window", defaults.rpm_max, 5000, 400000, 1000),
        _number("eta_cstar", "c* efficiency", "", "Assumptions", defaults.eta_cstar, 0.7, 1, 0.01),
        _number("eta_cf", "Cf efficiency", "", "Assumptions", defaults.eta_cf, 0.7, 1, 0.01),
        _number("cf_ideal", "Ideal Cf", "", "Assumptions", defaults.cf_ideal, 1, 2, 0.01),
        _number("f_inj", "Injector drop", "of pc", "Assumptions", defaults.f_inj, 0, 0.5, 0.01),
        _number("f_line", "Line drop", "of pc", "Assumptions", defaults.f_line, 0, 0.4, 0.01),
        _number("eta_p", "Pump efficiency", "", "Assumptions", defaults.eta_p, 0.2, 0.9, 0.01),
        _number("psi", "Head coefficient", "", "Assumptions", defaults.psi, 0.2, 1.2, 0.01),
        _number(
            "suction_specific_speed",
            "Suction specific speed",
            "",
            "Assumptions",
            defaults.suction_specific_speed,
            2,
            15,
            0.1,
        ),
    ]


def schema_payload() -> dict:
    return {
        "fields": field_schema(),
        "nominal_r": {name: pair.r_nominal for name, pair in PAIRS.items()},
    }


def inputs_from_payload(data: dict) -> CaseInputs:
    return CaseInputs(
        thrust=float(data["thrust_n"]),
        p_c=float(data["p_c_bar"]) * 1e5,
        mixture_ratio=float(data["mixture_ratio"]),
        pair=str(data["pair"]),
        p_tank_ox=float(data["p_tank_ox_bar"]) * 1e5,
        p_tank_f=float(data["p_tank_f_bar"]) * 1e5,
        rpm_min=float(data["rpm_min"]),
        rpm_max=float(data["rpm_max"]),
        eta_cstar=float(data["eta_cstar"]),
        eta_cf=float(data["eta_cf"]),
        eps=float(data["eps"]),
        f_inj=float(data["f_inj"]),
        f_line=float(data["f_line"]),
        dp_suction=float(data["dp_suction_bar"]) * 1e5,
        eta_p=float(data["eta_p"]),
        psi=float(data["psi"]),
        suction_specific_speed=float(data["suction_specific_speed"]),
        cf_ideal=float(data["cf_ideal"]),
    )


def _side_payload(sweep, point) -> dict:
    return {
        "p_d_bar": sweep.duty.p_d / 1e5,
        "p_s_bar": sweep.duty.p_s / 1e5,
        "dp_bar": sweep.duty.dp / 1e5,
        "npsha_m": sweep.duty.npsha,
        "power_kw": sweep.duty.power / 1e3,
        "zero_rpm": sweep.zero_rpm,
        "zero_status": sweep.zero_status,
        "d2_mm": None if point is None else point.d2 * 1e3,
        "margin_m": None if point is None else point.margin,
        "omega_s": None if point is None else point.omega_s,
    }


def serialize_result(result: CaseResult) -> dict:
    engine = result.engine
    return {
        "pair": result.pair_name,
        "r_nominal": result.r_nominal,
        "gamma": result.gamma,
        "limiting_rpm": result.limiting_rpm,
        "limiting_side": result.limiting_side,
        "power_total_kw": result.power_total / 1e3,
        "warnings": list(result.warnings),
        "engine": {
            "cstar_m_s": engine.cstar,
            "cf": engine.cf,
            "ve_m_s": engine.ve,
            "isp_s": engine.isp,
            "m_dot_kg_s": engine.m_dot,
            "m_dot_ox_kg_s": engine.m_dot_ox,
            "m_dot_f_kg_s": engine.m_dot_f,
            "q_ox_l_s": engine.q_ox * 1e3,
            "q_f_l_s": engine.q_f * 1e3,
        },
        "ox": _side_payload(result.ox, result.ox_at_limit),
        "fuel": _side_payload(result.fuel, result.fuel_at_limit),
    }


def evaluate_payload(data: dict, *, with_plot: bool = True) -> dict:
    with _EVAL_LOCK:
        try:
            result = evaluate(inputs_from_payload(data))
        except KeyError as exc:
            return {"ok": False, "error": f"Missing input {exc}."}
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        body = {"ok": True, **serialize_result(result)}
        if with_plot:
            body["plot_png"] = base64.b64encode(figure_png(result)).decode("ascii")
        return body


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            raw = PAGE.encode("utf-8")
            self._bytes(200, raw, "text/html; charset=utf-8")
        elif path == "/api/schema":
            self._json(200, schema_payload())
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"ok": False, "error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path != "/api/evaluate":
            self._json(404, {"ok": False, "error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"ok": False, "error": "Bad content length."})
            return
        if length > 1_000_000:
            self._json(413, {"ok": False, "error": "Request too large."})
            return
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, {"ok": False, "error": "Expected a JSON object."})
            return
        if not isinstance(data, dict):
            self._json(400, {"ok": False, "error": "Expected a JSON object."})
            return
        body = evaluate_payload(data)
        self._json(200 if body.get("ok") else 400, body)

    def log_message(self, fmt: str, *args) -> None:
        return

    def _json(self, code: int, body: dict) -> None:
        self._bytes(code, json.dumps(body).encode("utf-8"), "application/json; charset=utf-8")

    def _bytes(self, code: int, raw: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the pump sizer page in a browser.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser window")
    args = parser.parse_args(argv)
    ThreadingHTTPServer.allow_reuse_address = True
    try:
        server = ThreadingHTTPServer((args.host, args.port), _Handler)
    except OSError as exc:
        print(f"error: could not listen on {args.host}:{args.port} ({exc})")
        return 1
    url = f"http://{args.host}:{args.port}/"
    print(f"Pump sizer UI at {url}", flush=True)
    print("Stop with Ctrl+C.", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
