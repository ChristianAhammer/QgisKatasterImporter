#!/usr/bin/env python3
"""Auto-start qgis_mcp server inside a QGIS session."""

from __future__ import annotations

import importlib
import os
import sys

from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsApplication, QgsMessageLog
from qgis.utils import iface, plugins, startPlugin


MCP_SERVER = None


def _log(message: str) -> None:
    QgsMessageLog.logMessage(message, "QGIS MCP")


def _ensure_plugin_path() -> None:
    plugins_parent = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")
    if plugins_parent not in sys.path:
        sys.path.insert(0, plugins_parent)


def _start_via_plugin_api() -> bool:
    try:
        if "qgis_mcp_plugin" not in plugins:
            startPlugin("qgis_mcp_plugin")

        plugin = plugins.get("qgis_mcp_plugin")
        if not plugin:
            _log("qgis_mcp_plugin not loaded via plugin API")
            return False

        if not getattr(plugin, "dock_widget", None):
            plugin.toggle_dock(True)

        dock = getattr(plugin, "dock_widget", None)
        if not dock:
            _log("qgis_mcp_plugin dock widget is unavailable")
            return False

        dock.start_server()
        _log("MCP server start requested via plugin dock API")
        return True
    except Exception as exc:
        _log(f"plugin API start failed: {exc}")
        return False


def _start_via_direct_server_class() -> bool:
    global MCP_SERVER

    try:
        module = importlib.import_module("qgis_mcp_plugin.qgis_mcp_plugin")
        if MCP_SERVER and getattr(MCP_SERVER, "running", False):
            _log("MCP server already running (direct class)")
            return True

        MCP_SERVER = module.QgisMCPServer(host="localhost", port=9876, iface=iface)
        ok = bool(MCP_SERVER.start())
        _log(f"MCP server direct class start result: {ok}")
        return ok
    except Exception as exc:
        _log(f"direct class start failed: {exc}")
        return False


def _start_server() -> None:
    _ensure_plugin_path()
    if _start_via_plugin_api():
        return
    _start_via_direct_server_class()


QTimer.singleShot(2500, _start_server)
