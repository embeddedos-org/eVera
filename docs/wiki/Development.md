# Development

## Contribution source of truth

[CONTRIBUTING](https://github.com/embeddedos-org/eVera/blob/master/CONTRIBUTING.md)

Before proposing a change, also review the [README](https://github.com/embeddedos-org/eVera/blob/master/README.md). Keep changes scoped, add tests appropriate to the affected behavior, and follow the repository's current automation and review requirements.

## Build and dependency inputs found

`Dockerfile`, `Makefile`, `docker-compose.yml`, `docs/requirements.txt`, `electron/package-lock.json`, `electron/package.json`, `mobile/android/app/build.gradle`, `mobile/android/automotive/build.gradle`, `mobile/android/build.gradle`, `mobile/android/wear/build.gradle`, `mobile/package.json`, `pyproject.toml`, and 2 more.

## Tests found in the default-branch tree

`tests/__init__.py`, `tests/conftest.py`, `tests/functional/__init__.py`, `tests/functional/test_functional_e2e.py`, `tests/functional/test_gps_client.py`, `tests/performance/__init__.py`, `tests/performance/test_performance_benchmarks.py`, `tests/simulation/__init__.py`, `tests/simulation/test_emulation_simulation.py`, `tests/unit/__init__.py`, `tests/unit/test_new_agents.py`, `tests/unit/test_operating_mode.py`, and 2 more.

## Documented test commands

These commands are reproduced from the inspected root README or contributing guide:

```bash
pytest tests/ -v
```

```bash
python -m pytest tests/ -v
```

## Verification baseline

This inventory comes from `master` at [`4bc73c5a9b3d`](https://github.com/embeddedos-org/eVera/commit/4bc73c5a9b3df924a704e7a6282af3b1b05102d7) and found 14 test-related paths among 390 files. Re-check the source tree when that commit is no longer current.
