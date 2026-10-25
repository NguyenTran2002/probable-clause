"""The API and the run lifecycle (contract §4.H, §5). Owned by builder H.

`create_app(deps_factory)` builds the FastAPI app; `Run` is the `RunContext` given to the loop; `RunRegistry`
holds this instance's runs. `api/main.py` wires the real dependencies.
"""

from api.server.app import AppDeps, clean_question, create_app
from api.server.clock import Clock, RealClock
from api.server.registry import RunRegistry
from api.server.run import Run

__all__ = ["AppDeps", "Clock", "RealClock", "Run", "RunRegistry", "clean_question", "create_app"]
