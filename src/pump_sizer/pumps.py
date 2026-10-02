"""Pump pressure rise, shaft power, impeller diameter, and NPSH.

Speeds stay in rad/s inside these functions. RPM conversion happens at the
sweep boundary and again only for printout.
"""

from dataclasses import dataclass

import numpy as np

from pump_sizer.constants import G0


@dataclass(frozen=True)
class PumpDuty:
    """Rpm-independent duty. Pressures in Pa, head in m, power in W, flow in m^3/s."""

    side: str
    p_d: float
    p_s: float
    dp: float
    head: float
    power: float
    q: float
    rho: float
    npsha: float
    sweep_ok: bool
    note: str


def pump_duty(
    side: str,
    p_c: float,
    p_tank: float,
    m_dot: float,
    rho: float,
    p_vapor: float,
    f_inj: float,
    f_line: float,
    dp_suction: float,
    eta_p: float,
) -> PumpDuty:
    """Discharge, suction, head, and shaft power for one propellant.

    v1 uses the same discharge model on both sides. A regen jacket would add
    loss on the fuel side only; that term is intentionally absent.
    """
    p_d = p_c * (1.0 + f_inj + f_line)
    p_s = p_tank - dp_suction
    dp = p_d - p_s
    q = m_dot / rho
    power = q * dp / eta_p
    # Inlet velocity head is neglected in v1.
    npsha = (p_s - p_vapor) / (rho * G0)

    if dp <= 0.0:
        return PumpDuty(
            side=side,
            p_d=p_d,
            p_s=p_s,
            dp=dp,
            head=dp / (rho * G0),
            power=power,
            q=q,
            rho=rho,
            npsha=npsha,
            sweep_ok=False,
            note="discharge pressure does not exceed suction pressure; cavitation sweep skipped",
        )
    head = dp / (rho * G0)
    if p_s <= p_vapor:
        return PumpDuty(
            side=side,
            p_d=p_d,
            p_s=p_s,
            dp=dp,
            head=head,
            power=power,
            q=q,
            rho=rho,
            npsha=npsha,
            sweep_ok=False,
            note="p_s <= p_vapor; NPSHa is non-positive; cavitation sweep skipped",
        )
    return PumpDuty(
        side=side,
        p_d=p_d,
        p_s=p_s,
        dp=dp,
        head=head,
        power=power,
        q=q,
        rho=rho,
        npsha=npsha,
        sweep_ok=True,
        note="",
    )


def sweep_kinematics(
    duty: PumpDuty,
    rpm: np.ndarray,
    psi: float,
    suction_specific_speed: float,
) -> dict[str, np.ndarray]:
    """Tip speed, diameter, specific speed, NPSHr, and margin at each rpm.

    Head coefficient is locked as psi = dp / (rho * U^2).
    Suction specific speed is locked as
    S = omega * sqrt(Q) / (g0 * NPSHr) ** 0.75
    with dimensionless S. Do not mix in a US-unit Nss.
    """
    if not duty.sweep_ok:
        raise ValueError(f"{duty.side} pump has no cavitation sweep ({duty.note})")

    rpm = np.asarray(rpm, dtype=float)
    omega = 2.0 * np.pi * rpm / 60.0
    u = np.full(rpm.shape, np.sqrt(duty.dp / (duty.rho * psi)))
    d2 = 2.0 * u / omega
    omega_s = omega * np.sqrt(duty.q) / (G0 * duty.head) ** 0.75
    group = omega * np.sqrt(duty.q) / suction_specific_speed
    npshr = (1.0 / G0) * np.power(group, 4.0 / 3.0)
    margin = duty.npsha - npshr
    return {
        "rpm": rpm,
        "omega": omega,
        "u": u,
        "d2": d2,
        "omega_s": omega_s,
        "npshr": npshr,
        "margin": margin,
    }
