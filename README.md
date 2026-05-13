# UniVis

UniVis is the experimental web viewer for synchronized `PolicyEpisode` data.

Phase 00 uses fake in-memory episodes to validate the FastAPI + React
visualization flow before real HDF5 or PIKA adapters are connected.

## Run

```bash
uv run univis --host 0.0.0.0 --port 8010
```

Then open `http://127.0.0.1:8010`.

If `uv` is not installed yet:

```bash
python3.10 -m pip install --user uv
```

## Test

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --extra dev pytest
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated system pytest plugins, such
as ROS launch testing plugins, from affecting this project.
