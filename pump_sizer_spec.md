# Few-kN pump-fed sizer, v1

Meanline only. LOX/RP-1 and LOX/ethanol. No blades, no CAD, no CFD, no turbine geometry.

The decision the tool must show: highest rpm that keeps cavitation margin positive, because power does not depend on rpm in this model and diameter shrinks as rpm rises.

SI units only. Pressures in Pa, flows in m^3/s, power in W, speeds in rad/s internally. Convert to rpm, kW, mm, and bar only at the printout.

## Objective

Given thrust, chamber pressure, mixture ratio, and tank pressures, size the oxidizer pump and the fuel pump far enough to report:

- mass flow and volume flow of each propellant
- pressure rise and shaft power of each pump
- impeller tip speed and diameter at a chosen rpm
- available versus required NPSH, and the rpm where margin crosses zero

v1 does not size a turbine. It reports the shaft power the turbine must supply. v1 does not model a cooling jacket loss separately from a single fuel-side line loss.

## Inputs

Required:

| Symbol | Meaning | Suggested default | Unit |
| --- | --- | --- | --- |
| F | sea-level thrust | 3000 | N |
| p_c | chamber pressure | 2.0e6 | Pa |
| p_a | ambient pressure | 101325 | Pa |
| r | mixture ratio, ox/fuel by mass | 2.3 RP-1, 1.6 ethanol | - |
| p_tank_ox | oxidizer tank ullage | 0.40e6 | Pa |
| p_tank_f | fuel tank ullage | 0.40e6 | Pa |
| N | shaft speed, the sweep variable | 10000 to 60000 | rpm |

Assumptions, overridable, not hidden:

| Symbol | Meaning | Default | Unit |
| --- | --- | --- | --- |
| eta_cstar | c* efficiency | 0.92 | - |
| eta_cf | Cf efficiency | 0.95 | - |
| eps | nozzle expansion ratio | 8 | - |
| f_inj | injector drop as a fraction of p_c | 0.20 | - |
| f_line | discharge line and valve drop as a fraction of p_c | 0.05 | - |
| dp_suction | suction-line loss, each side | 0.5e5 | Pa |
| eta_p | pump efficiency, each side | 0.55 | - |
| psi | head coefficient, gH / U^2 | 0.50 | - |
| S | dimensionless suction specific speed | 8 | - |
| hub_ratio | hub diameter / eye diameter, unused in v1 | 0.3 | - |

Propellant defaults at the tank temperature you are assuming. Do not compute these. Table them.

| | LOX | RP-1 | ethanol |
| --- | --- | --- | --- |
| density, kg/m^3 | 1141 | 810 | 789 |
| vapor pressure, Pa | 101325 at 90 K | 200 | 5800 at 20 C |
| note | boiling in the tank unless subcooled | vapor pressure is negligible | room-temperature fuel |

Performance defaults, ideal c* before eta_cstar. These are ballpark CEA values, not a thermochemistry solver. State that in the README.

| | LOX/RP-1 at r=2.3 | LOX/ethanol at r=1.6 |
| --- | --- | --- |
| c*_ideal, m/s | 1780 | 1650 |
| gamma | 1.20 | 1.18 |

If the user changes r by more than about 0.3 from these points, the c* default is wrong. v1 should warn, not retune.

## Derived engine side

Characteristic velocity actually delivered:

c* = eta_cstar * c*_ideal

Ideal thrust coefficient for a frozen-gamma nozzle, pe from the expansion ratio via the isentropic area-Mach relation. For v1, skip the Mach solver and use a fixed ideal Cf, then apply efficiency:

Cf_ideal = 1.50 for eps = 8, sea level, both pairs. Overridable.

Cf = eta_cf * Cf_ideal

Delivered specific impulse and mass flow:

ve = c* * Cf

Isp = ve / g0

m_dot = F / ve

with g0 = 9.80665 m/s^2.

Split:

m_dot_ox = m_dot * r / (1 + r)

m_dot_f = m_dot / (1 + r)

Q = m_dot / rho

This mass flow is independent of the pumps. If the number is absurd, the c* or Cf default is absurd. Check that before touching the pump.

## Pump pressures

Discharge pressure, each side:

p_d_ox = p_c * (1 + f_inj + f_line)

p_d_f = p_c * (1 + f_inj + f_line)

v1 uses the same discharge model on both sides. A regen jacket would add loss on the fuel side only. Leave a comment, do not add the term.

Suction pressure:

p_s = p_tank - dp_suction

Pressure rise and head:

dp = p_d - p_s

H = dp / (rho * g0)

If p_s <= p_vapor, NPSHa is already non-positive. Return that and stop the cavitation sweep for that side.

## Power

Shaft power of one pump:

P = m_dot * dp / (rho * eta_p)

Same thing: P = Q * dp / eta_p

Total shaft power is the sum. It does not depend on rpm. Efficiency is a guess. At a few kilonewtons, 0.55 is already optimistic for a small machined impeller. Say so on the plot.

## Speed, diameter, specific speed

Convert the sweep variable once:

omega = 2 * pi * N / 60

Head coefficient, definition locked for this code:

psi = g0 * H / U^2 = dp / (rho * U^2)

so

U = sqrt(dp / (rho * psi))

Impeller diameter:

D2 = 2 * U / omega

Dimensionless specific speed:

omega_s = omega * sqrt(Q) / (g0 * H) ** 0.75

A centrifugal impeller with an inducer is comfortable somewhere around 0.4 to 1.5. Outside that, print a warning. Do not retune psi to force it inside the band. The warning is the result.

## Cavitation

Available NPSH, meters of fluid. Inlet velocity head is neglected in v1.

NPSHa = (p_s - p_vapor) / (rho * g0)

Required NPSH from a chosen suction specific speed. Definition locked:

S = omega * sqrt(Q) / (g0 * NPSHr) ** 0.75

so

NPSHr = (1 / g0) * (omega * sqrt(Q) / S) ** (4 / 3)

Margin:

margin = NPSHa - NPSHr

S = 8 is an inducer-class default, roughly a US suction specific speed of 20,000. A pump with no inducer is closer to S = 3. Both are inputs. Do not hardcode a US-unit Nss beside this or the exponents will get mixed.

Margin falls as rpm rises. Diameter falls as rpm rises. Power stays flat. The highest rpm with margin > 0 on both pumps is the v1 answer.

## Outputs

Scalar, one per case:

- c*, Cf, ve, Isp
- m_dot, m_dot_ox, m_dot_f
- Q_ox, Q_f
- p_d and p_s and dp for each side
- P_ox, P_f, P_total
- NPSHa for each side

Per rpm in the sweep:

- U, D2, omega_s, NPSHr, margin, for each pump

Printed answer:

- rpm where oxidizer margin crosses zero
- rpm where fuel margin crosses zero
- limiting rpm, the lower of the two
- D2 and power at that rpm

Plot, one figure, two panels or two y-axes:

- cavitation margin versus rpm, both pumps, zero line marked
- impeller diameter versus rpm, both pumps
- power annotated as a constant, not drawn as a fake curve

## Sanity case

LOX/RP-1, F = 3000 N, p_c = 2.0 MPa, r = 2.3, tanks at 0.40 MPa, defaults above.

ve should land near 1780 * 0.92 * 1.50 * 0.95, about 2330 m/s, Isp about 238 s.

m_dot = 3000 / 2330, about 1.3 kg/s.

Oxidizer volume flow is under 1 L/s. Oxidizer shaft power is a few kilowatts, not tens. If the code says 100 kW, a unit is wrong.

LOX is the side that cavitates first, because its vapor pressure is 1 atm and the tank is only a few bar above that. RP-1 and ethanol should show a much higher rpm limit. If the fuel dies first, p_vapor or p_s is wrong.

## Out of scope

Turbine, gas generator, blade angles, eye diameter, volute, materials, two-phase inlet, water-hammer, and anything in the garage. A regen pressure drop and an inlet-velocity head are the only legal v1.1 additions.
