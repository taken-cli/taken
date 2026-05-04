import os
from pathlib import Path

TAKEN_HOME: Path = Path(os.environ["TAKEN_HOME"]) if "TAKEN_HOME" in os.environ else Path.home() / ".taken"
