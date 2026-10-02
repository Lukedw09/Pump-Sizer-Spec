# Few-kN pump-fed sizer

Meanline sizing for the oxidizer and fuel pumps of a few-kilonewton pump-fed engine. v1 covers LOX/RP-1 and LOX/ethanol. It reports mass flow, pressure rise, shaft power, impeller diameter, and the shaft speed where cavitation margin crosses zero.

The decision the tool is built to show: power does not depend on rpm in this model, diameter shrinks as rpm rises, and the highest rpm with positive cavitation margin on **both** pumps is the answer. That limit is almost always the LOX pump.

Open [Pump Sizer.html](<Pump Sizer.html>) to use it. Double-click the file, or attach that same file to an email.

Formulas, defaults, and the sanity case are specified in [pump_sizer_spec.md](pump_sizer_spec.md).

## Units

Physics functions use SI only: Pa, m^3/s, W, m, rad/s. The CLI converts to bar, kW, mm, and rpm when it prints and plots. `c*` and `Cf` are ballpark CEA values tabulated in `constants.py`, not the output of a thermochemistry solver. Ideal thrust coefficient is a fixed input (`Cf_ideal = 1.50` at expansion ratio 8). v1 does not solve the isentropic area-Mach relation. If mixture ratio moves more than 0.3 from the tabulated point, the tool warns and does **not** retune `c*`.

## Out of scope

Turbine geometry, gas generator, blade angles, eye diameter, volute, materials, two-phase inlet, water-hammer, and CAD/CFD. A regen-jacket pressure drop and an inlet-velocity head are the only additions the spec leaves open for a later version. Shaft power is reported so a turbine can be sized elsewhere; this tool does not size one.

`eta_p = 0.55` is already optimistic for a small machined impeller at a few kilonewtons. The figure says so. Dimensionless specific speed is checked against about 0.4–1.5 and a warning is printed outside that band. `psi` is not retuned to force the result inside the band.

## Open

Double-click `Pump Sizer.html`. The sizer opens in your browser, with inputs, results, and the figure on one page. Edits recompute as you change them.

To share it, attach that file to an email. The recipient saves the attachment and opens it in Chrome, Edge, or Firefox. Open the saved file itself; a preview inside the mail program leaves the calculator blank.

## Install

The command-line report and the tests need a local Python install:

```bash
pip install -e ".[dev]"
```

## Command line

Defaults are the LOX/RP-1 sanity case (3 kN, 2.0 MPa, r = 2.3, both tanks at 0.40 MPa):

```bash
pump-sizer
```

or:

```bash
python -m pump_sizer
```

`python -m pump_sizer.ui` serves the same screen at `http://127.0.0.1:8765/` for development. The file to open and email is `Pump Sizer.html`.

The zero-crossing search extends past the requested rpm window when margin is still positive there, so the cavitation limit is still reported. The table and the figure stay on the requested window (default 10,000–60,000 rpm).

```bash
pump-sizer --thrust 3000 --pc 2e6 --pair LOX/ethanol --p-tank-ox 0.4e6 --p-tank-f 0.4e6
pump-sizer --csv sweep.csv --plot pump_sizer.png
pump-sizer --no-plot
```

Assumption flags: `--eta-cstar`, `--eta-cf`, `--cf-ideal`, `--eps`, `--f-inj`, `--f-line`, `--dp-suction`, `--eta-p`, `--psi`, `--suction-specific-speed`, `--rpm-min`, `--rpm-max`.

## Tests

```bash
pytest
```

`tests/test_sanity_case.py` locks the LOX/RP-1 default: delivered velocity near 2330 m/s, mass flow near 1.3 kg/s, oxidizer volume flow under 1 L/s, oxidizer shaft power of a few kilowatts, and a LOX cavitation limit well below the fuel limit.

## Layout

```
Pump Sizer.html   double-click to open the sizer; this is the file to email
src/pump_sizer/
  constants.py    propellant and performance tables, assumption defaults
  engine.py       c*, Cf, ve, Isp, propellant split, volume flow
  pumps.py        discharge/suction pressures, head, power, diameter, NPSH
  sweep.py        rpm grid, margin zero-crossing, limiting rpm
  plot.py         margin and diameter figure
  cli.py          argparse entrypoint
  ui.py           development server for the same page
```
