from __future__ import annotations

import importlib
import runpy
import sys
import types

import pytest

from ksef_link.main import _error_payload, entrypoint
from ksef_link.shared.errors import KsefLinkError
from ksef_link.shared.logging import LOGGER_NAME


def test_entrypoint_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ksef_link.main.main", lambda argv=None, environment=None: 7)

    with pytest.raises(SystemExit) as result:
        entrypoint()

    assert result.value.code == 7


def test_package_main_module_executes_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("ksef_link.main")

    def fake_entrypoint() -> None:
        raise SystemExit(0)

    fake_module.__dict__["entrypoint"] = fake_entrypoint
    monkeypatch.setitem(sys.modules, "ksef_link.main", fake_module)

    with pytest.raises(SystemExit) as result:
        runpy.run_module("ksef_link.__main__", run_name="__main__")

    assert result.value.code == 0


def test_package_main_module_imports_without_running_entrypoint() -> None:
    module = importlib.import_module("ksef_link.__main__")

    assert module is not None


def test_error_payload_for_generic_application_error() -> None:
    payload = _error_payload(KsefLinkError("generic"))

    assert payload == {"error": "generic"}


def test_logging_wrapper_exposes_logger_name() -> None:
    assert LOGGER_NAME == "ksef_link"
