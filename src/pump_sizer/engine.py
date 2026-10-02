"""Delivered c*, thrust coefficient, specific impulse, and propellant flows."""

from dataclasses import dataclass

from pump_sizer.constants import G0


@dataclass(frozen=True)
class EngineResult:
    cstar_ideal: float
    cstar: float
    cf_ideal: float
    cf: float
    ve: float
    isp: float
    m_dot: float
    m_dot_ox: float
    m_dot_f: float
    q_ox: float
    q_f: float


def engine_performance(
    thrust: float,
    mixture_ratio: float,
    cstar_ideal: float,
    rho_ox: float,
    rho_fuel: float,
    eta_cstar: float,
    eta_cf: float,
    cf_ideal: float,
) -> EngineResult:
    """Chain from the spec. Mass flow does not depend on the pumps.

    For the default LOX/RP-1 case this is ve ≈ 2330 m/s, Isp ≈ 238 s,
    and m_dot ≈ 1.3 kg/s. Check that before trusting a pump number.
    """
    cstar = eta_cstar * cstar_ideal
    cf = eta_cf * cf_ideal
    ve = cstar * cf
    isp = ve / G0
    m_dot = thrust / ve
    m_dot_ox = m_dot * mixture_ratio / (1.0 + mixture_ratio)
    m_dot_f = m_dot / (1.0 + mixture_ratio)
    return EngineResult(
        cstar_ideal=cstar_ideal,
        cstar=cstar,
        cf_ideal=cf_ideal,
        cf=cf,
        ve=ve,
        isp=isp,
        m_dot=m_dot,
        m_dot_ox=m_dot_ox,
        m_dot_f=m_dot_f,
        q_ox=m_dot_ox / rho_ox,
        q_f=m_dot_f / rho_fuel,
    )
