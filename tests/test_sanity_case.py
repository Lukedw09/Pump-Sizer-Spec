"""Sanity case from pump_sizer_spec.md: LOX/RP-1, 3 kN, 2.0 MPa, r = 2.3."""

import pytest

from pump_sizer.plot import render_plot
from pump_sizer.sweep import CaseInputs, evaluate

# ve = 1780 * 0.92 * 1.50 * 0.95
EXPECTED_VE = 1780.0 * 0.92 * 1.50 * 0.95


def test_delivered_velocity_and_impulse():
    result = evaluate(CaseInputs())
    assert result.engine.ve == pytest.approx(EXPECTED_VE)
    assert result.engine.ve == pytest.approx(2330.0, rel=0.01)
    assert result.engine.isp == pytest.approx(238.0, abs=1.0)


def test_mass_flow_near_1_3_kg_s():
    result = evaluate(CaseInputs())
    assert result.engine.m_dot == pytest.approx(3000.0 / EXPECTED_VE)
    assert result.engine.m_dot == pytest.approx(1.3, abs=0.05)


def test_oxidizer_flow_and_power_scale():
    result = evaluate(CaseInputs())
    # Under 1 L/s. A few kilowatts: the ~100 kW answer is a unit error.
    assert result.ox.duty.q < 1.0e-3
    assert result.ox.duty.q > 0.3e-3
    assert 1_000.0 < result.ox.duty.power < 10_000.0
    assert result.power_total == pytest.approx(result.power_ox + result.power_fuel)


def test_lox_cavitation_limit_is_below_fuel():
    result = evaluate(CaseInputs())
    assert result.ox.zero_rpm is not None
    assert result.fuel.zero_rpm is not None
    assert result.limiting_side == "ox"
    assert result.limiting_rpm == pytest.approx(result.ox.zero_rpm)
    assert result.fuel.zero_rpm > 1.8 * result.ox.zero_rpm
    assert result.ox_at_limit is not None
    assert result.fuel_at_limit is not None
    assert result.ox_at_limit.margin == pytest.approx(0.0, abs=0.01)
    assert result.fuel_at_limit.margin > 0.0
    # Margin falls and diameter shrinks across the default window, and LOX is tighter.
    assert result.ox.margin[0] > result.ox.margin[-1] > 0.0
    assert result.fuel.margin[0] > result.fuel.margin[-1]
    assert result.ox.margin[-1] < result.fuel.margin[-1]
    assert result.ox.d2[0] > result.ox.d2[-1]
    assert result.fuel.d2[0] > result.fuel.d2[-1]


def test_plot_writes_figure(tmp_path):
    result = evaluate(CaseInputs())
    path = tmp_path / "figure.png"
    written = render_plot(result, path, show=False)
    data = written.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 5_000
