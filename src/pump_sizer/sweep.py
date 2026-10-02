"""RPM sweep, cavitation-margin zero-crossing, and the limiting shaft speed."""

from dataclasses import dataclass

import numpy as np

from pump_sizer.constants import (
    CF_IDEAL,
    DP_SUCTION,
    EPS,
    EPS_REFERENCE,
    ETA_CF,
    ETA_CSTAR,
    ETA_P,
    F_INJ,
    F_LINE,
    OMEGA_S_MAX,
    OMEGA_S_MIN,
    PAIRS,
    PLOT_POINTS,
    PROPELLANTS,
    PSI,
    R_WARN_DELTA,
    RPM_MAX,
    RPM_MIN,
    RPM_SEARCH_CAP,
    RPM_SEARCH_FLOOR,
    RPM_SEARCH_POINTS,
    SUCTION_SPECIFIC_SPEED,
)
from pump_sizer.engine import EngineResult, engine_performance
from pump_sizer.pumps import PumpDuty, pump_duty, sweep_kinematics

STATUS_CROSSED = "crossed"


@dataclass(frozen=True)
class CaseInputs:
    thrust: float = 3000.0
    p_c: float = 2.0e6
    mixture_ratio: float = 2.3
    pair: str = "LOX/RP-1"
    p_tank_ox: float = 0.40e6
    p_tank_f: float = 0.40e6
    rpm_min: float = RPM_MIN
    rpm_max: float = RPM_MAX
    eta_cstar: float = ETA_CSTAR
    eta_cf: float = ETA_CF
    eps: float = EPS
    f_inj: float = F_INJ
    f_line: float = F_LINE
    dp_suction: float = DP_SUCTION
    eta_p: float = ETA_P
    psi: float = PSI
    suction_specific_speed: float = SUCTION_SPECIFIC_SPEED
    cf_ideal: float = CF_IDEAL


@dataclass(frozen=True)
class SpeedPoint:
    rpm: float
    u: float
    d2: float
    omega_s: float
    npshr: float
    margin: float


@dataclass(frozen=True)
class SideSweep:
    duty: PumpDuty
    rpm: np.ndarray
    u: np.ndarray
    d2: np.ndarray
    omega_s: np.ndarray
    npshr: np.ndarray
    margin: np.ndarray
    zero_rpm: float | None
    zero_status: str


@dataclass(frozen=True)
class CaseResult:
    inputs: CaseInputs
    pair_name: str
    gamma: float
    r_nominal: float
    engine: EngineResult
    ox: SideSweep
    fuel: SideSweep
    warnings: tuple[str, ...]
    limiting_rpm: float | None
    limiting_side: str | None
    ox_at_limit: SpeedPoint | None
    fuel_at_limit: SpeedPoint | None

    @property
    def power_ox(self) -> float:
        return self.ox.duty.power

    @property
    def power_fuel(self) -> float:
        return self.fuel.duty.power

    @property
    def power_total(self) -> float:
        return self.power_ox + self.power_fuel


def evaluate(inputs: CaseInputs | None = None) -> CaseResult:
    """Size both pumps and find the rpm where cavitation margin hits zero."""
    if inputs is None:
        inputs = CaseInputs()
    _validate(inputs)

    pair = PAIRS[inputs.pair]
    ox_prop = PROPELLANTS[pair.oxidizer]
    fuel_prop = PROPELLANTS[pair.fuel]
    engine = engine_performance(
        thrust=inputs.thrust,
        mixture_ratio=inputs.mixture_ratio,
        cstar_ideal=pair.cstar_ideal,
        rho_ox=ox_prop.density,
        rho_fuel=fuel_prop.density,
        eta_cstar=inputs.eta_cstar,
        eta_cf=inputs.eta_cf,
        cf_ideal=inputs.cf_ideal,
    )

    ox_duty = pump_duty(
        side="ox",
        p_c=inputs.p_c,
        p_tank=inputs.p_tank_ox,
        m_dot=engine.m_dot_ox,
        rho=ox_prop.density,
        p_vapor=ox_prop.vapor_pressure,
        f_inj=inputs.f_inj,
        f_line=inputs.f_line,
        dp_suction=inputs.dp_suction,
        eta_p=inputs.eta_p,
    )
    fuel_duty = pump_duty(
        side="fuel",
        p_c=inputs.p_c,
        p_tank=inputs.p_tank_f,
        m_dot=engine.m_dot_f,
        rho=fuel_prop.density,
        p_vapor=fuel_prop.vapor_pressure,
        f_inj=inputs.f_inj,
        f_line=inputs.f_line,
        dp_suction=inputs.dp_suction,
        eta_p=inputs.eta_p,
    )

    rpm_grid = np.linspace(inputs.rpm_min, inputs.rpm_max, PLOT_POINTS)
    ox = _side_sweep(ox_duty, rpm_grid, inputs)
    fuel = _side_sweep(fuel_duty, rpm_grid, inputs)

    candidates = [
        (side.duty.side, side.zero_rpm)
        for side in (ox, fuel)
        if side.zero_rpm is not None
    ]
    if candidates:
        limiting_side, limiting_rpm = min(candidates, key=lambda item: item[1])
    else:
        limiting_side, limiting_rpm = None, None

    ox_at_limit = _point_at(ox.duty, limiting_rpm, inputs)
    fuel_at_limit = _point_at(fuel.duty, limiting_rpm, inputs)
    warnings = _warnings(inputs, pair.r_nominal, ox, fuel, ox_at_limit, fuel_at_limit)
    return CaseResult(
        inputs=inputs,
        pair_name=pair.name,
        gamma=pair.gamma,
        r_nominal=pair.r_nominal,
        engine=engine,
        ox=ox,
        fuel=fuel,
        warnings=tuple(warnings),
        limiting_rpm=limiting_rpm,
        limiting_side=limiting_side,
        ox_at_limit=ox_at_limit,
        fuel_at_limit=fuel_at_limit,
    )


def sample_speeds(
    result: CaseResult,
    count: int = 11,
) -> tuple[np.ndarray, dict[str, np.ndarray] | None, dict[str, np.ndarray] | None]:
    """Kinematics on a short grid inside the requested rpm window, for the text table."""
    rpm = np.linspace(result.inputs.rpm_min, result.inputs.rpm_max, count)
    ox = _sample_side(result.ox, rpm, result.inputs)
    fuel = _sample_side(result.fuel, rpm, result.inputs)
    return rpm, ox, fuel


def _sample_side(
    side: SideSweep,
    rpm: np.ndarray,
    inputs: CaseInputs,
) -> dict[str, np.ndarray] | None:
    if not side.duty.sweep_ok:
        return None
    return sweep_kinematics(side.duty, rpm, inputs.psi, inputs.suction_specific_speed)


def _side_sweep(duty: PumpDuty, rpm_grid: np.ndarray, inputs: CaseInputs) -> SideSweep:
    zero_rpm, zero_status = _zero_crossing(duty, inputs)
    if not duty.sweep_ok:
        empty = np.array([], dtype=float)
        return SideSweep(
            duty=duty,
            rpm=empty,
            u=empty,
            d2=empty,
            omega_s=empty,
            npshr=empty,
            margin=empty,
            zero_rpm=None,
            zero_status=zero_status,
        )
    kin = sweep_kinematics(duty, rpm_grid, inputs.psi, inputs.suction_specific_speed)
    return SideSweep(
        duty=duty,
        rpm=kin["rpm"],
        u=kin["u"],
        d2=kin["d2"],
        omega_s=kin["omega_s"],
        npshr=kin["npshr"],
        margin=kin["margin"],
        zero_rpm=zero_rpm,
        zero_status=zero_status,
    )


def _zero_crossing(duty: PumpDuty, inputs: CaseInputs) -> tuple[float | None, str]:
    """Linear interpolation of the margin sign change on a search grid.

    The requested window is what the plot shows. If margin does not change
    sign inside it, the search expands until it does, or until the cap.
    """
    if not duty.sweep_ok:
        return None, duty.note

    def margin_at(rpm: float) -> float:
        kin = sweep_kinematics(
            duty,
            np.array([rpm]),
            inputs.psi,
            inputs.suction_specific_speed,
        )
        return float(kin["margin"][0])

    m_at_min = margin_at(inputs.rpm_min)
    if m_at_min == 0.0:
        return inputs.rpm_min, STATUS_CROSSED
    if m_at_min < 0.0:
        lo = inputs.rpm_min
        m_lo = m_at_min
        while m_lo < 0.0 and lo > RPM_SEARCH_FLOOR:
            next_lo = max(RPM_SEARCH_FLOOR, lo / 2.0)
            if next_lo == lo:
                break
            lo = next_lo
            m_lo = margin_at(lo)
        if m_lo < 0.0:
            return None, (
                f"margin is non-positive from {RPM_SEARCH_FLOOR:.0f} rpm "
                "through the start of the sweep"
            )
        if m_lo == 0.0:
            return lo, STATUS_CROSSED
        hi = inputs.rpm_min
    else:
        lo = inputs.rpm_min
        hi = inputs.rpm_max
        m_hi = margin_at(hi)
        while m_hi > 0.0 and hi < RPM_SEARCH_CAP:
            next_hi = min(RPM_SEARCH_CAP, hi * 2.0)
            if next_hi <= hi:
                break
            hi = next_hi
            m_hi = margin_at(hi)
        if m_hi > 0.0:
            return None, f"margin is still positive at the search cap of {RPM_SEARCH_CAP:.0f} rpm"
        if m_hi == 0.0:
            return hi, STATUS_CROSSED

    rpms = np.linspace(lo, hi, RPM_SEARCH_POINTS)
    margin = sweep_kinematics(duty, rpms, inputs.psi, inputs.suction_specific_speed)["margin"]
    crossings = np.where((margin[:-1] > 0.0) & (margin[1:] <= 0.0))[0]
    if crossings.size == 0:
        return None, "no margin sign change on the search grid"
    i = int(crossings[0])
    m0 = float(margin[i])
    m1 = float(margin[i + 1])
    n0 = float(rpms[i])
    n1 = float(rpms[i + 1])
    frac = m0 / (m0 - m1)
    return n0 + frac * (n1 - n0), STATUS_CROSSED


def _point_at(duty: PumpDuty, rpm: float | None, inputs: CaseInputs) -> SpeedPoint | None:
    if rpm is None or not duty.sweep_ok:
        return None
    kin = sweep_kinematics(duty, np.array([rpm]), inputs.psi, inputs.suction_specific_speed)
    return SpeedPoint(
        rpm=rpm,
        u=float(kin["u"][0]),
        d2=float(kin["d2"][0]),
        omega_s=float(kin["omega_s"][0]),
        npshr=float(kin["npshr"][0]),
        margin=float(kin["margin"][0]),
    )


def _warnings(
    inputs: CaseInputs,
    r_nominal: float,
    ox: SideSweep,
    fuel: SideSweep,
    ox_at_limit: SpeedPoint | None,
    fuel_at_limit: SpeedPoint | None,
) -> list[str]:
    warnings: list[str] = []
    for side in (ox, fuel):
        if not side.duty.sweep_ok and side.duty.note:
            warnings.append(f"{side.duty.side}: {side.duty.note}")
    if abs(inputs.mixture_ratio - r_nominal) > R_WARN_DELTA:
        warnings.append(
            f"Mixture ratio {inputs.mixture_ratio:.3f} differs from the {inputs.pair} "
            f"nominal {r_nominal:.3f} by more than {R_WARN_DELTA:.1f}. "
            "c*_ideal was not retuned and is likely wrong for this mixture ratio."
        )
    if abs(inputs.eps - EPS_REFERENCE) > 1e-6:
        warnings.append(
            f"eps = {inputs.eps:g} differs from {EPS_REFERENCE:g}. "
            "v1 does not solve the area-Mach relation; Cf_ideal was not recomputed."
        )
    for side in (ox, fuel):
        if side.omega_s.size == 0:
            continue
        low = float(np.min(side.omega_s))
        high = float(np.max(side.omega_s))
        if low < OMEGA_S_MIN or high > OMEGA_S_MAX:
            warnings.append(
                f"{side.duty.side} omega_s spans {low:.3f} to {high:.3f} "
                f"from {inputs.rpm_min:.0f} to {inputs.rpm_max:.0f} rpm, which leaves "
                f"the {OMEGA_S_MIN:.1f}-{OMEGA_S_MAX:.1f} band. psi was not retuned."
            )
    for side in (ox, fuel):
        if side.zero_rpm is None:
            continue
        if side.zero_rpm > inputs.rpm_max or side.zero_rpm < inputs.rpm_min:
            warnings.append(
                f"{side.duty.side} margin crosses zero at {side.zero_rpm:.0f} rpm, "
                "outside the requested rpm window. The table and plot stay on that window."
            )
    for label, point in (("ox", ox_at_limit), ("fuel", fuel_at_limit)):
        if point is None:
            continue
        if point.omega_s < OMEGA_S_MIN or point.omega_s > OMEGA_S_MAX:
            warnings.append(
                f"{label} dimensionless specific speed omega_s = {point.omega_s:.3f} at "
                f"{point.rpm:.0f} rpm is outside {OMEGA_S_MIN:.1f}-{OMEGA_S_MAX:.1f}. "
                "psi was not retuned."
            )
    return warnings


def _validate(inputs: CaseInputs) -> None:
    if inputs.pair not in PAIRS:
        known = ", ".join(PAIRS)
        raise ValueError(f"Unknown propellant pair {inputs.pair!r}. Choose one of: {known}.")
    _positive("thrust", inputs.thrust)
    _positive("p_c", inputs.p_c)
    _positive("mixture_ratio", inputs.mixture_ratio)
    _positive("rpm_min", inputs.rpm_min)
    if inputs.rpm_max <= inputs.rpm_min:
        raise ValueError(
            f"rpm_max must be greater than rpm_min, got {inputs.rpm_min} to {inputs.rpm_max}."
        )
    for name, value in (
        ("eta_cstar", inputs.eta_cstar),
        ("eta_cf", inputs.eta_cf),
        ("eta_p", inputs.eta_p),
    ):
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be in (0, 1], got {value}.")
    _positive("psi", inputs.psi)
    _positive("suction_specific_speed", inputs.suction_specific_speed)
    _positive("cf_ideal", inputs.cf_ideal)
    _positive("eps", inputs.eps)
    if inputs.f_inj < 0.0 or inputs.f_line < 0.0:
        raise ValueError("f_inj and f_line must be >= 0.")


def _positive(name: str, value: float) -> None:
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}.")
