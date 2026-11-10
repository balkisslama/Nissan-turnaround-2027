"""
chart_style.py
==============
Purpose : One shared "look" for every chart in the project (colours, fonts,
          sizes) plus a helper that saves a figure into reports/figures/.
          Keeping the style in one place makes all charts look consistent,
          like a company template.

          This file is not run on its own; other scripts import it.
"""

import matplotlib

matplotlib.use("Agg")          # draw straight into image files, no pop-up windows
import matplotlib.pyplot as plt

from db_utils import PROJECT_ROOT

FIGURES_DIR = PROJECT_ROOT / "reports" / "figures"

COLORS = {
    "navy": "#1F3A5F",      # totals and main series
    "red": "#C0392B",       # losses, headwinds, declines
    "green": "#2E8B57",     # gains, tailwinds, increases
    "grey": "#8A8D91",      # secondary information
    "light": "#B8C4D6",     # forecasts and context
    "amber": "#D98E04",     # highlights and warnings
}


def apply_style() -> None:
    """Set the default look of all charts."""
    plt.rcParams.update({
        "figure.dpi": 100,
        "font.family": "DejaVu Sans",      # ships with matplotlib: same look on every computer
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": "#E3E5E8",
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "legend.frameon": False,
    })


def save_figure(figure, file_name: str):
    """Save a figure as a PNG in reports/figures/ and return its path."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / file_name
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return path