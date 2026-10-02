"""The browser page feeds display units into the same sanity case."""

import base64

import pytest

from pump_sizer.ui import evaluate_payload, field_schema


def test_default_form_matches_sanity_case():
    form = {field["key"]: field["default"] for field in field_schema()}
    body = evaluate_payload(form)
    assert body["ok"] is True
    assert body["engine"]["ve_m_s"] == pytest.approx(1780.0 * 0.92 * 1.50 * 0.95)
    assert body["engine"]["m_dot_kg_s"] == pytest.approx(1.3, abs=0.05)
    assert body["engine"]["q_ox_l_s"] < 1.0
    assert 1.0 < body["ox"]["power_kw"] < 10.0
    assert body["limiting_side"] == "ox"
    assert body["fuel"]["zero_rpm"] > 1.8 * body["ox"]["zero_rpm"]
    png = base64.b64decode(body["plot_png"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_bad_efficiency_is_an_error_not_a_result():
    form = {field["key"]: field["default"] for field in field_schema()}
    form["eta_p"] = 1.5
    body = evaluate_payload(form, with_plot=False)
    assert body["ok"] is False
    assert "eta_p" in body["error"]
