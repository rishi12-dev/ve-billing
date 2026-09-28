from pathlib import Path

import pandas as pd


def export_rows(filename, rows, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    pd.DataFrame(rows).to_excel(path, index=False)
    return path
