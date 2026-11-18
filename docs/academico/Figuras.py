"""Reproduce las figuras del informe a partir del CSV publicado."""
import csv
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, FuncFormatter

root = Path(__file__).resolve().parent
with (root / "Episodios-A0.csv").open(newline="") as source:
    rows = [row for row in csv.DictReader(source) if row["in_matched_subset"] == "1"]

scenarios = {
    "nominal": "Plano nominal",
    "friction": "Baja fricción",
    "impulse": "Empujón",
    "sensor_noise": "Ruido de sensores",
    "mass_delay": "Masa y retardo",
    "rough": "Terreno rugoso",
    "slope": "Pendiente de 5°",
}
colors = {"E1": "#17506B", "E5": "#187B62"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "text.color": "#193045", "axes.labelcolor": "#193045",
    "axes.spines.top": False, "axes.spines.right": False,
})

fig, ax = plt.subplots(figsize=(7.1, 3.48), layout="constrained")
ax.set_axisbelow(True)
ax.grid(axis="x", color="#DCE5EB")
for name, offset in (("E1", -.19), ("E5", .19)):
    for index, condition in enumerate(scenarios):
        selection = [row for row in rows if row["training"] == name and row["scenario"] == condition]
        count = sum(int(row["pass"]) for row in selection)
        fraction = count / len(selection)
        ax.barh(index + offset, fraction, height=.32, color=colors[name], label=name if index == 0 else None)
        ax.text(fraction + .022, index + offset, f"{count}/{len(selection)}", va="center", fontsize=9)
ax.invert_yaxis()
ax.set_yticks(range(len(scenarios)), list(scenarios.values()))
ax.set_xlim(0, 1.147)
ax.set_xticks([0, .25, .5, .75, 1])
ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
ax.set_xlabel("Episodios aprobados")
ax.legend(loc="lower right", frameon=False)
fig.savefig(root / "Resultados-por-escenario.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.1, 2.65), layout="constrained")
ax.set_axisbelow(True)
ax.grid(axis="y", color="#DCE5EB")
ax.axhline(.10, color="#A34224", linestyle="--", lw=1.35, label="Límite lineal")
for name, offset in (("E1", -.12), ("E5", .12)):
    values = [
        median(float(row["linear_rmse_m_s"]) for row in rows
               if row["training"] == name and row["scenario"] == condition and row["command"] == "forward")
        for condition in ("nominal", "mass_delay")
    ]
    ax.bar([offset, 1 + offset], values, width=.21, color=colors[name], label=name)
    for x, value in enumerate(values):
        ax.text(x + offset, value + .005, f"{value:.4f}".replace(".", ","), ha="center", fontsize=9)
ax.set_ylim(0, .136)
ax.set_yticks([0, .025, .05, .075, .10, .125])
ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.3f}".replace(".", ",")))
ax.set_ylabel("RMSE lineal (m/s)")
ax.set_xticks([0, 1], ["Plano nominal", "Masa y retardo"])
ax.legend(loc="upper left", frameon=False, ncol=3)
fig.savefig(root / "Error-de-avance.png", dpi=200)
