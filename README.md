# UiPath Developer Console

[![PyPI downloads](https://img.shields.io/pypi/dm/uipath-dev.svg)](https://pypi.org/project/uipath-dev/)
[![Python versions](https://img.shields.io/pypi/pyversions/uipath-dev.svg)](https://pypi.org/project/uipath-dev/)


Interactive terminal application for building, testing, and debugging UiPath Python runtimes, agents, and automation scripts.

## Overview

The Developer Console provides a local environment for developers who are building or experimenting with Python-based UiPath runtimes.
It integrates with the [`uipath-runtime`](https://pypi.org/project/uipath-runtime/) SDK to execute agents and visualize their behavior in real time using the [`textual`](https://github.com/Textualize/textual) framework.

This tool is designed for:
- Developers building **UiPath agents** or **custom runtime integrations**
- Python engineers testing **standalone automation scripts** before deployment
- Contributors exploring **runtime orchestration** and **execution traces**

![Runtime Trace Demo](https://raw.githubusercontent.com/UiPath/uipath-dev-python/main/docs/demo_traces.svg)

## Features

- Run and inspect Python runtimes interactively
- View structured logs, output, and OpenTelemetry traces
- Export and review execution history

## Installation

```bash
uv add uipath-dev
```

## Development

Launch the Developer Console with mocked data:

```bash
uv run uipath-dev
```

To run tests:

```bash
pytest
```
