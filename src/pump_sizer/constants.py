"""Tabulated propellant properties, pair performance, and assumption defaults.

Densities and vapor pressures are inputs, not property-model outputs. Ideal c*
and gamma are ballpark CEA values, not the output of a thermochemistry solver.
"""

from dataclasses import dataclass

G0 = 9.80665  # m/s^2

# Comfortable band for a centrifugal impeller with an inducer.
# Outside the band the sweep warns; psi is not retuned.
OMEGA_S_MIN = 0.4
OMEGA_S_MAX = 1.5

# |r - r_nominal| above this means the tabulated c* is the wrong mixture.
R_WARN_DELTA = 0.3

# Cf_ideal = 1.50 is stated for this expansion ratio. v1 does not recompute it.
EPS_REFERENCE = 8.0

# Zero-crossing search bounds. The plotted window can be narrower.
RPM_SEARCH_FLOOR = 1_000.0
RPM_SEARCH_CAP = 2_000_000.0
RPM_SEARCH_POINTS = 5_000
PLOT_POINTS = 401


@dataclass(frozen=True)
class Propellant:
    name: str
    density: float  # kg/m^3
    vapor_pressure: float  # Pa


@dataclass(frozen=True)
class PairPerformance:
    name: str
    oxidizer: str
    fuel: str
    r_nominal: float
    cstar_ideal: float  # m/s
    gamma: float


PROPELLANTS: dict[str, Propellant] = {
    "LOX": Propellant("LOX", density=1141.0, vapor_pressure=101325.0),
    "RP-1": Propellant("RP-1", density=810.0, vapor_pressure=200.0),
    "ethanol": Propellant("ethanol", density=789.0, vapor_pressure=5800.0),
}

PAIRS: dict[str, PairPerformance] = {
    "LOX/RP-1": PairPerformance(
        name="LOX/RP-1",
        oxidizer="LOX",
        fuel="RP-1",
        r_nominal=2.3,
        cstar_ideal=1780.0,
        gamma=1.20,
    ),
    "LOX/ethanol": PairPerformance(
        name="LOX/ethanol",
        oxidizer="LOX",
        fuel="ethanol",
        r_nominal=1.6,
        cstar_ideal=1650.0,
        gamma=1.18,
    ),
}

# Overridable assumption defaults. Not buried inside the formulas.
ETA_CSTAR = 0.92
ETA_CF = 0.95
EPS = 8.0
F_INJ = 0.20
F_LINE = 0.05
DP_SUCTION = 0.5e5  # Pa
ETA_P = 0.55
PSI = 0.50
SUCTION_SPECIFIC_SPEED = 8.0
CF_IDEAL = 1.50
HUB_RATIO = 0.3  # unused in v1

RPM_MIN = 10_000.0
RPM_MAX = 60_000.0
