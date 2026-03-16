"""Punto de entrada de PEO Promotion Center."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Lanza la aplicación Streamlit."""
    app_path = Path(__file__).parent / "frontend" / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=True,
    )


if __name__ == "__main__":
    main()
