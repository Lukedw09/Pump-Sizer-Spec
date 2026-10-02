"""Command-line printout for the pump sizer."""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

from pump_sizer.constants import (
    CF_IDEAL,
    DP_SUCTION,
    EPS,
    ETA_CF,
    ETA_CSTAR,
    ETA_P,
    F_INJ,
    F_LINE,
    PAIRS,
    PSI,
    RPM_MAX,
    RPM_MIN,
    SUCTION_SPECIFIC_SPEED,
)
from pump_sizer.sweep import CaseInputs, CaseResult, evaluate, sample_speeds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pump-sizer",
        description=(
            "Size the oxidizer and fuel pumps for a few-kN pump-fed engine. "
            "Calculations stay in SI; this printout uses bar, kW, mm, and rpm."
        ),
    )
    parser.add_argument("--thrust", type=float, default=3000.0, help="Sea-level thrust F [N]")
    parser.add_argument("--pc", type=float, default=2.0e6, help="Chamber pressure [Pa]")
    parser.add_argument(
        "--mixture-ratio",
        type=float,
        default=None,
        help="Oxidizer/fuel mass ratio. Defaults to the pair's tabulated nominal.",
    )
    parser.add_argument("--pair", choices=tuple(PAIRS), default="LOX/RP-1")
    parser.add_argument("--p-tank-ox", type=float, default=0.40e6, help="Oxidizer tank ullage [Pa]")
    parser.add_argument("--p-tank-f", type=float, default=0.40e6, help="Fuel tank ullage [Pa]")
    parser.add_argument("--rpm-min", type=float, default=RPM_MIN, help="Low end of the plotted sweep [rpm]")
    parser.add_argument("--rpm-max", type=float, default=RPM_MAX, help="High end of the plotted sweep [rpm]")
    parser.add_argument("--eta-cstar", type=float, default=ETA_CSTAR)
    parser.add_argument("--eta-cf", type=float, default=ETA_CF)
    parser.add_argument("--cf-ideal", type=float, default=CF_IDEAL, help="Ideal thrust coefficient at eps=8")
    parser.add_argument("--eps", type=float, default=EPS, help="Nozzle expansion ratio (does not recompute Cf)")
    parser.add_argument("--f-inj", type=float, default=F_INJ, help="Injector drop as a fraction of p_c")
    parser.add_argument("--f-line", type=float, default=F_LINE, help="Discharge line drop as a fraction of p_c")
    parser.add_argument("--dp-suction", type=float, default=DP_SUCTION, help="Suction-line loss, each side [Pa]")
    parser.add_argument("--eta-p", type=float, default=ETA_P, help="Pump efficiency, each side")
    parser.add_argument("--psi", type=float, default=PSI, help="Head coefficient")
    parser.add_argument(
        "--suction-specific-speed",
        type=float,
        default=SUCTION_SPECIFIC_SPEED,
        help="Dimensionless suction specific speed S",
    )
    parser.add_argument("--csv", type=Path, default=None, help="Write the per-rpm table to this path")
    parser.add_argument("--plot", type=Path, default=Path("pump_sizer.png"), help="Figure path")
    parser.add_argument("--no-plot", action="store_true", help="Skip the figure")
    parser.add_argument("--show", action="store_true", help="Also open an interactive matplotlib window")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = evaluate(_inputs_from_args(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_report(result))
    if args.csv is not None:
        write_csv(result, args.csv)
        print(f"Wrote {args.csv}")
    if not args.no_plot:
        from pump_sizer.plot import render_plot

        written = render_plot(result, args.plot, show=args.show)
        print(f"Wrote {written}")
    return 0


def format_report(result: CaseResult) -> str:
    eng = result.engine
    inp = result.inputs
    lines: list[str] = []
    add = lines.append
    add("Few-kN pump-fed sizer")
    add(
        f"Pair: {result.pair_name}    "
        f"mixture ratio r = {inp.mixture_ratio:.3f} (nominal {result.r_nominal:.3f})"
    )
    add(
        f"Thrust = {inp.thrust:.1f} N    "
        f"p_c = {_bar(inp.p_c):.3f} bar"
    )
    add("")
    add("Assumptions")
    add(
        f"  eta_cstar = {inp.eta_cstar:.3f}    eta_cf = {inp.eta_cf:.3f}    "
        f"Cf_ideal = {inp.cf_ideal:.3f}    eps = {inp.eps:g}"
    )
    add(
        f"  f_inj = {inp.f_inj:.3f}    f_line = {inp.f_line:.3f}    "
        f"dp_suction = {_bar(inp.dp_suction):.3f} bar    eta_p = {inp.eta_p:.3f}"
    )
    add(
        f"  psi = {inp.psi:.3f}    S = {inp.suction_specific_speed:g}    "
        f"gamma = {result.gamma:.2f} (tabulated, not used for Cf)"
    )
    add("")
    add("Engine")
    add(f"  c*_ideal = {eng.cstar_ideal:.1f} m/s")
    add(f"  c*       = {eng.cstar:.1f} m/s")
    add(f"  Cf_ideal = {eng.cf_ideal:.3f}")
    add(f"  Cf       = {eng.cf:.3f}")
    add(f"  ve       = {eng.ve:.1f} m/s")
    add(f"  Isp      = {eng.isp:.1f} s")
    add(f"  m_dot    = {eng.m_dot:.4f} kg/s")
    add(f"  m_dot_ox = {eng.m_dot_ox:.4f} kg/s")
    add(f"  m_dot_f  = {eng.m_dot_f:.4f} kg/s")
    add(f"  Q_ox     = {eng.q_ox:.6e} m^3/s")
    add(f"  Q_f      = {eng.q_f:.6e} m^3/s")
    add("")
    add("Pumps")
    add(f"  {'side':<10} {'p_d bar':>10} {'p_s bar':>10} {'dp bar':>10} {'NPSHa m':>10} {'P kW':>10}")
    for label, duty in (("oxidizer", result.ox.duty), ("fuel", result.fuel.duty)):
        add(
            f"  {label:<10} {_bar(duty.p_d):10.3f} {_bar(duty.p_s):10.3f} "
            f"{_bar(duty.dp):10.3f} {duty.npsha:10.3f} {duty.power / 1e3:10.3f}"
        )
    add(f"  total shaft power = {result.power_total / 1e3:.3f} kW (independent of rpm)")
    add("")
    add("Answer")
    add(_zero_line("oxidizer", result.ox.zero_rpm, result.ox.zero_status))
    add(_zero_line("fuel", result.fuel.zero_rpm, result.fuel.zero_status))
    if result.limiting_rpm is None or result.limiting_side is None:
        add("  limiting rpm: none (no rpm keeps both margins positive inside the search)")
    else:
        add(f"  limiting rpm: {result.limiting_rpm:.0f} rpm ({result.limiting_side})")
        add("  At the limiting rpm:")
        add(_limit_line("oxidizer", result.ox_at_limit, result.power_ox))
        add(_limit_line("fuel", result.fuel_at_limit, result.power_fuel))
    add("")
    add(
        f"Per-rpm table from {inp.rpm_min:.0f} to {inp.rpm_max:.0f} rpm "
        "(zero-crossing search may extend past this window)"
    )
    _, ox_rows, fuel_rows = sample_speeds(result, count=11)
    lines.extend(_speed_block("Oxidizer", ox_rows))
    lines.extend(_speed_block("Fuel", fuel_rows))
    add("")
    add("Warnings")
    if result.warnings:
        lines.extend(f"  - {warning}" for warning in result.warnings)
    else:
        add("  none")
    return "\n".join(lines)


def write_csv(result: CaseResult, path: Path) -> None:
    if result.ox.rpm.size:
        rpm = result.ox.rpm
    elif result.fuel.rpm.size:
        rpm = result.fuel.rpm
    else:
        rpm = np.linspace(result.inputs.rpm_min, result.inputs.rpm_max, 2)
    header = [
        "rpm",
        "U_ox_m_s",
        "D2_ox_mm",
        "omega_s_ox",
        "NPSHr_ox_m",
        "margin_ox_m",
        "U_f_m_s",
        "D2_f_mm",
        "omega_s_f",
        "NPSHr_f_m",
        "margin_f_m",
    ]
    columns = [
        _csv_column(result.ox, "u", 1.0, len(rpm)),
        _csv_column(result.ox, "d2", 1e3, len(rpm)),
        _csv_column(result.ox, "omega_s", 1.0, len(rpm)),
        _csv_column(result.ox, "npshr", 1.0, len(rpm)),
        _csv_column(result.ox, "margin", 1.0, len(rpm)),
        _csv_column(result.fuel, "u", 1.0, len(rpm)),
        _csv_column(result.fuel, "d2", 1e3, len(rpm)),
        _csv_column(result.fuel, "omega_s", 1.0, len(rpm)),
        _csv_column(result.fuel, "npshr", 1.0, len(rpm)),
        _csv_column(result.fuel, "margin", 1.0, len(rpm)),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for i, speed in enumerate(rpm):
            writer.writerow([f"{float(speed):.8g}", *[column[i] for column in columns]])


def _inputs_from_args(args: argparse.Namespace) -> CaseInputs:
    nominal = PAIRS[args.pair].r_nominal
    mixture_ratio = nominal if args.mixture_ratio is None else args.mixture_ratio
    return CaseInputs(
        thrust=args.thrust,
        p_c=args.pc,
        mixture_ratio=mixture_ratio,
        pair=args.pair,
        p_tank_ox=args.p_tank_ox,
        p_tank_f=args.p_tank_f,
        rpm_min=args.rpm_min,
        rpm_max=args.rpm_max,
        eta_cstar=args.eta_cstar,
        eta_cf=args.eta_cf,
        eps=args.eps,
        f_inj=args.f_inj,
        f_line=args.f_line,
        dp_suction=args.dp_suction,
        eta_p=args.eta_p,
        psi=args.psi,
        suction_specific_speed=args.suction_specific_speed,
        cf_ideal=args.cf_ideal,
    )


def _zero_line(label: str, rpm: float | None, status: str) -> str:
    if rpm is None:
        return f"  {label} zero-cross: none ({status})"
    return f"  {label} zero-cross: {rpm:.0f} rpm"


def _limit_line(label: str, point, power: float) -> str:
    if point is None:
        return f"    {label:<10} geometry unavailable    power = {power / 1e3:.3f} kW"
    return (
        f"    {label:<10} D2 = {point.d2 * 1e3:.2f} mm    "
        f"power = {power / 1e3:.3f} kW    "
        f"margin = {point.margin:.3f} m    "
        f"omega_s = {point.omega_s:.3f}"
    )


def _speed_block(title: str, kin: dict[str, np.ndarray] | None) -> list[str]:
    if kin is None:
        return ["", f"{title}: cavitation sweep skipped"]
    lines = [
        "",
        title,
        f"  {'rpm':>8} {'U_m/s':>10} {'D2_mm':>10} {'omega_s':>10} {'NPSHr_m':>10} {'margin_m':>10}",
    ]
    for i, rpm in enumerate(kin["rpm"]):
        lines.append(
            f"  {rpm:8.0f} {kin['u'][i]:10.2f} {kin['d2'][i] * 1e3:10.2f} "
            f"{kin['omega_s'][i]:10.3f} {kin['npshr'][i]:10.3f} {kin['margin'][i]:10.3f}"
        )
    return lines


def _csv_column(side, key: str, scale: float, n: int) -> list[str]:
    if side.rpm.size == 0:
        return [""] * n
    return [f"{float(value) * scale:.8g}" for value in getattr(side, key)]


def _bar(pascals: float) -> float:
    return pascals / 1e5


if __name__ == "__main__":
    raise SystemExit(main())
