"""One figure: cavitation margin and impeller diameter versus shaft speed."""

import io
import sys
from pathlib import Path

from pump_sizer.sweep import CaseResult


def render_plot(result: CaseResult, path: Path | str, show: bool = False) -> Path:
    """Write the two-panel speed trade figure. Power is annotated, not plotted."""
    path = Path(path)
    import matplotlib

    interactive = False
    if show:
        try:
            matplotlib.use("TkAgg", force=True)
            interactive = True
        except Exception:
            matplotlib.use("Agg", force=True)
    else:
        matplotlib.use("Agg", force=True)

    import matplotlib.pyplot as plt

    fig = build_figure(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140, bbox_inches="tight")
    if interactive:
        plt.show()
    plt.close(fig)
    return path


def figure_png(result: CaseResult, dpi: int = 110, figsize: tuple[float, float] = (7.6, 5.6)) -> bytes:
    """PNG bytes of the same figure the CLI writes, sized for the page."""
    import matplotlib

    if "matplotlib.pyplot" not in sys.modules:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = build_figure(result, figsize=figsize)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def build_figure(result: CaseResult, figsize: tuple[float, float] = (8.2, 7.0)):
    import matplotlib.pyplot as plt

    fig, (ax_margin, ax_diameter) = plt.subplots(2, 1, sharex=True, figsize=figsize)
    _draw_margin(ax_margin, result)
    _draw_diameter(ax_diameter, result)
    ax_diameter.set_xlabel("Shaft speed (rpm)")
    ax_margin.set_xlim(result.inputs.rpm_min, result.inputs.rpm_max)

    limiting = result.limiting_rpm
    if limiting is not None and result.inputs.rpm_min <= limiting <= result.inputs.rpm_max:
        for axis in (ax_margin, ax_diameter):
            axis.axvline(limiting, color="0.25", ls="--", lw=1.0, label="Limiting rpm")

    ax_margin.legend(loc="best", fontsize=8)
    ax_diameter.legend(loc="best", fontsize=8)
    fig.suptitle(
        f"{result.pair_name}   {result.inputs.thrust:.0f} N   "
        f"p_c = {result.inputs.p_c / 1e5:.2f} bar"
    )
    note = (
        f"Total shaft power is constant at {result.power_total / 1e3:.2f} kW "
        f"(oxidizer {result.power_ox / 1e3:.2f} kW, fuel {result.power_fuel / 1e3:.2f} kW).\n"
        f"eta_p = {result.inputs.eta_p:.2f} is optimistic for few-kN machined impellers."
    )
    fig.text(0.5, -0.02, note, ha="center", va="top", fontsize=8)
    fig.tight_layout()
    return fig


def _draw_margin(axis, result: CaseResult) -> None:
    axis.set_ylabel("Cavitation margin (m)")
    axis.axhline(0.0, color="black", lw=0.8, label="Zero margin")
    axis.grid(True, alpha=0.35)
    if result.ox.rpm.size:
        axis.plot(result.ox.rpm, result.ox.margin, color="#0072B2", label="Oxidizer")
    if result.fuel.rpm.size:
        axis.plot(result.fuel.rpm, result.fuel.margin, color="#E69F00", label="Fuel")
    notes = _outside_window_notes(result)
    if notes:
        axis.text(
            0.98,
            0.95,
            "\n".join(notes),
            transform=axis.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85, "edgecolor": "0.8"},
        )
    if result.ox.rpm.size == 0 and result.fuel.rpm.size == 0:
        axis.text(0.5, 0.5, "Cavitation sweep skipped", transform=axis.transAxes, ha="center")


def _draw_diameter(axis, result: CaseResult) -> None:
    axis.set_ylabel("Impeller diameter (mm)")
    axis.grid(True, alpha=0.35)
    if result.ox.rpm.size:
        axis.plot(result.ox.rpm, result.ox.d2 * 1e3, color="#0072B2", label="Oxidizer")
    if result.fuel.rpm.size:
        axis.plot(result.fuel.rpm, result.fuel.d2 * 1e3, color="#E69F00", label="Fuel")


def _outside_window_notes(result: CaseResult) -> list[str]:
    notes = []
    low = result.inputs.rpm_min
    high = result.inputs.rpm_max
    for label, rpm in (("Oxidizer", result.ox.zero_rpm), ("Fuel", result.fuel.zero_rpm)):
        if rpm is not None and not (low <= rpm <= high):
            notes.append(f"{label} zero-cross {rpm:,.0f} rpm")
    return notes
