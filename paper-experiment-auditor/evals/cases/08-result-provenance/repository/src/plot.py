from pathlib import Path


RESULTS = Path("results/final.csv")


def load_plot_source() -> str:
    return RESULTS.read_text(encoding="utf-8")
