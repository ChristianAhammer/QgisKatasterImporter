#!/usr/bin/env python3
"""Black-box QGIS project validation via a running QGIS MCP plugin server.

This script intentionally treats QGIS as an external system and talks to the
QGIS MCP socket endpoint (default: localhost:9876). It validates that a
generated project can be loaded and inspected through the MCP boundary.
"""

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class QgisMcpClient:
    host: str = "localhost"
    port: int = 9876
    timeout_seconds: float = 10.0
    sock: Optional[socket.socket] = None

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout_seconds)
        self.sock.connect((self.host, self.port))

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.sock:
            raise RuntimeError("Client is not connected")

        payload = {"type": command_type, "params": params or {}}
        self.sock.sendall(json.dumps(payload).encode("utf-8"))

        response_data = b""
        while True:
            chunk = self.sock.recv(8192)
            if not chunk:
                break
            response_data += chunk
            try:
                parsed = json.loads(response_data.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise RuntimeError(f"Unexpected response payload for {command_type}: {parsed!r}")
                return parsed
            except json.JSONDecodeError:
                continue

        raise RuntimeError(f"No valid JSON response for command: {command_type}")


def _as_success_result(response: Dict[str, Any], command_name: str) -> Any:
    status = str(response.get("status") or "").lower()
    if status != "success":
        raise RuntimeError(f"{command_name} failed: {response.get('message') or response}")
    return response.get("result")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a black-box MCP smoke test against a generated QGIS project."
    )
    parser.add_argument("--project", required=True, help="Path to .qgs/.qgz file to load via MCP.")
    parser.add_argument("--host", default="localhost", help="QGIS MCP host (default: localhost)")
    parser.add_argument("--port", type=int, default=9876, help="QGIS MCP port (default: 9876)")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Socket timeout for MCP commands (default: 10)",
    )
    parser.add_argument(
        "--expected-crs",
        default="EPSG:25833",
        help="Expected project CRS auth id (default: EPSG:25833)",
    )
    parser.add_argument(
        "--min-layers",
        type=int,
        default=1,
        help="Minimum expected total layer count after project load (default: 1)",
    )
    parser.add_argument(
        "--min-vector-layers",
        type=int,
        default=1,
        help="Minimum expected vector layer count (default: 1)",
    )
    parser.add_argument(
        "--render-path",
        default="",
        help="Optional output PNG path for render probe. Default: <project>_mcp_render.png",
    )
    parser.add_argument(
        "--keep-render",
        action="store_true",
        help="Keep rendered PNG file (default behavior removes auto-generated file).",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=5,
        help="Max features for vector sample probe (default: 5)",
    )
    parser.add_argument(
        "--prompt-start-server",
        action="store_true",
        help="If MCP server is unreachable, ask user to start it and retry.",
    )
    parser.add_argument(
        "--server-wait-seconds",
        type=float,
        default=60.0,
        help="How long to wait after each prompt for MCP server startup (default: 60).",
    )
    parser.add_argument(
        "--server-poll-seconds",
        type=float,
        default=1.0,
        help="Polling interval while waiting for server (default: 1).",
    )
    parser.add_argument(
        "--start-server-retries",
        type=int,
        default=2,
        help="Number of interactive retry prompts if server is unreachable (default: 2).",
    )
    parser.add_argument("--summary-json", default="", help="Optional path to write JSON summary.")
    return parser.parse_args(argv)


def _wait_for_server(host: str, port: int, timeout_seconds: float, poll_seconds: float) -> bool:
    timeout_seconds = max(0.0, float(timeout_seconds))
    poll_seconds = max(0.1, float(poll_seconds))
    deadline = time.time() + timeout_seconds
    while time.time() <= deadline:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.settimeout(min(1.5, poll_seconds))
            probe.connect((host, port))
            return True
        except OSError:
            pass
        finally:
            probe.close()
        time.sleep(poll_seconds)
    return False


def _ensure_server_available(args: argparse.Namespace, summary: Dict[str, Any]) -> None:
    reachable = _wait_for_server(args.host, args.port, timeout_seconds=0.1, poll_seconds=0.1)
    summary["checks"]["server_reachable_initial"] = reachable
    if reachable:
        return

    if not args.prompt_start_server:
        raise RuntimeError(
            f"MCP server is not reachable at {args.host}:{args.port}. "
            "Start it in QGIS: Plugins -> QGIS MCP -> QGIS MCP -> Start Server."
        )

    if not sys.stdin.isatty():
        raise RuntimeError(
            f"MCP server is not reachable at {args.host}:{args.port} and interactive prompt is unavailable."
        )

    attempts = max(1, int(args.start_server_retries))
    for attempt in range(1, attempts + 1):
        print(
            f"MCP server is not reachable at {args.host}:{args.port}.",
            file=sys.stderr,
        )
        print(
            "Please start it in QGIS: Plugins -> QGIS MCP -> QGIS MCP -> Start Server.",
            file=sys.stderr,
        )
        answer = input(
            f"Attempt {attempt}/{attempts}: press Enter to retry, or type 'q' to abort: "
        ).strip().lower()
        if answer in {"q", "quit", "exit", "n", "no"}:
            raise RuntimeError("Aborted by user before MCP server startup.")

        if _wait_for_server(
            args.host,
            args.port,
            timeout_seconds=args.server_wait_seconds,
            poll_seconds=args.server_poll_seconds,
        ):
            summary["checks"]["server_reachable_after_prompt"] = True
            return

    summary["checks"]["server_reachable_after_prompt"] = False
    raise RuntimeError(
        f"MCP server still unreachable at {args.host}:{args.port} after {attempts} prompt attempt(s)."
    )


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    project_path = os.path.abspath(args.project)
    summary: Dict[str, Any] = {
        "ok": False,
        "project_path": project_path,
        "host": args.host,
        "port": args.port,
        "checks": {},
        "errors": [],
    }
    created_render = False

    try:
        if not os.path.isfile(project_path):
            raise RuntimeError(f"Project file not found: {project_path}")
        if not project_path.lower().endswith((".qgs", ".qgz")):
            raise RuntimeError("Project path must end with .qgs or .qgz")

        expected_gpkg = os.path.splitext(project_path)[0] + ".gpkg"
        expected_report = os.path.splitext(project_path)[0] + "_report.txt"
        summary["checks"]["expected_gpkg_exists"] = os.path.isfile(expected_gpkg)
        summary["checks"]["expected_report_exists"] = os.path.isfile(expected_report)
        if not summary["checks"]["expected_gpkg_exists"]:
            raise RuntimeError(f"Expected sidecar GeoPackage not found: {expected_gpkg}")

        render_path = args.render_path.strip() or (os.path.splitext(project_path)[0] + "_mcp_render.png")
        render_path = os.path.abspath(render_path)

        _ensure_server_available(args, summary)

        client = QgisMcpClient(host=args.host, port=args.port, timeout_seconds=args.timeout_seconds)
        try:
            client.connect()

            ping = _as_success_result(client.send_command("ping"), "ping")
            summary["checks"]["ping"] = ping

            qgis_info = _as_success_result(client.send_command("get_qgis_info"), "get_qgis_info")
            summary["checks"]["qgis_info"] = qgis_info

            load_result = _as_success_result(client.send_command("load_project", {"path": project_path}), "load_project")
            summary["checks"]["load_project"] = load_result

            project_info = _as_success_result(client.send_command("get_project_info"), "get_project_info")
            summary["checks"]["project_info"] = project_info

            loaded_crs = str(project_info.get("crs") or "")
            layer_count = int(project_info.get("layer_count") or 0)
            if args.expected_crs and loaded_crs != args.expected_crs:
                raise RuntimeError(f"CRS mismatch: expected {args.expected_crs}, got {loaded_crs or '<empty>'}")
            if layer_count < args.min_layers:
                raise RuntimeError(
                    f"Layer count check failed: expected >= {args.min_layers}, got {layer_count}"
                )

            layers = _as_success_result(client.send_command("get_layers"), "get_layers")
            if not isinstance(layers, list):
                raise RuntimeError(f"Unexpected get_layers payload: {layers!r}")
            vector_layers = [layer for layer in layers if str(layer.get("type") or "").startswith("vector_")]
            summary["checks"]["layer_count_total"] = len(layers)
            summary["checks"]["layer_count_vector"] = len(vector_layers)
            if len(vector_layers) < args.min_vector_layers:
                raise RuntimeError(
                    f"Vector layer count check failed: expected >= {args.min_vector_layers}, got {len(vector_layers)}"
                )

            sample_layer_id = str(vector_layers[0].get("id") or "")
            if not sample_layer_id:
                raise RuntimeError("First vector layer has no id")
            features = _as_success_result(
                client.send_command("get_layer_features", {"layer_id": sample_layer_id, "limit": args.sample_limit}),
                "get_layer_features",
            )
            summary["checks"]["sample_features"] = {
                "layer_id": sample_layer_id,
                "feature_count": int(features.get("feature_count") or 0) if isinstance(features, dict) else None,
            }

            render_result = _as_success_result(
                client.send_command("render_map", {"path": render_path, "width": 1280, "height": 720}),
                "render_map",
            )
            summary["checks"]["render_map"] = render_result
            created_render = os.path.isfile(render_path)
            if not created_render:
                raise RuntimeError(f"Render probe reported success but file not found: {render_path}")

            summary["ok"] = True
            print("MCP black-box check PASSED")
            print(f"- Project: {project_path}")
            print(f"- CRS: {loaded_crs}")
            print(f"- Layers: total={len(layers)} vector={len(vector_layers)}")
            print(f"- Render: {render_path}")
        finally:
            client.close()

        if created_render and not args.keep_render and not args.render_path:
            try:
                os.remove(render_path)
            except OSError:
                pass
            summary["checks"]["render_removed"] = True

        return 0

    except Exception as err:
        summary["errors"].append(str(err))
        print(f"MCP black-box check FAILED: {err}", file=sys.stderr)
        return 1

    finally:
        if args.summary_json:
            try:
                with open(args.summary_json, "w", encoding="utf-8") as handle:
                    json.dump(summary, handle, indent=2, ensure_ascii=False)
            except OSError as err:
                print(f"Failed to write summary JSON: {err}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
