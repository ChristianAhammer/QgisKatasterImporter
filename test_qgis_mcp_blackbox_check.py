import json
import socket
import sys
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import qgis_mcp_blackbox_check as mcp_check


def sockets_available() -> bool:
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.close()
        return True
    except OSError:
        return False


SOCKETS_AVAILABLE = sockets_available()


class QgisMcpBlackboxCheckTests(unittest.TestCase):
    def test_as_success_result_returns_result_on_success(self):
        result = mcp_check._as_success_result({"status": "success", "result": {"ok": True}}, "ping")
        self.assertEqual(result, {"ok": True})

    def test_as_success_result_raises_on_failure(self):
        with self.assertRaises(RuntimeError):
            mcp_check._as_success_result({"status": "error", "message": "bad request"}, "ping")

    @unittest.skipUnless(SOCKETS_AVAILABLE, "Socket operations are blocked in this environment")
    def test_wait_for_server_true_when_port_is_listening(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        accepted = {"done": False}

        def _accept_once():
            conn, _ = listener.accept()
            accepted["done"] = True
            conn.close()

        thread = threading.Thread(target=_accept_once, daemon=True)
        thread.start()
        try:
            self.assertTrue(
                mcp_check._wait_for_server("127.0.0.1", port, timeout_seconds=0.8, poll_seconds=0.05)
            )
            thread.join(timeout=1.0)
            self.assertTrue(accepted["done"])
        finally:
            listener.close()

    @unittest.skipUnless(SOCKETS_AVAILABLE, "Socket operations are blocked in this environment")
    def test_wait_for_server_false_when_port_is_closed(self):
        temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp.bind(("127.0.0.1", 0))
        port = temp.getsockname()[1]
        temp.close()

        self.assertFalse(
            mcp_check._wait_for_server("127.0.0.1", port, timeout_seconds=0.25, poll_seconds=0.05)
        )

    @unittest.skipUnless(SOCKETS_AVAILABLE, "Socket operations are blocked in this environment")
    def test_qgis_mcp_client_send_command_roundtrip(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        errors = []

        def _server_once():
            try:
                conn, _ = listener.accept()
                data = conn.recv(8192)
                payload = json.loads(data.decode("utf-8"))
                if payload.get("type") != "ping":
                    raise AssertionError(f"Unexpected command type: {payload!r}")
                response = {"status": "success", "result": {"pong": True}}
                conn.sendall(json.dumps(response).encode("utf-8"))
                conn.close()
            except Exception as exc:
                errors.append(str(exc))
            finally:
                listener.close()

        thread = threading.Thread(target=_server_once, daemon=True)
        thread.start()

        client = mcp_check.QgisMcpClient(host="127.0.0.1", port=port, timeout_seconds=2.0)
        try:
            client.connect()
            response = client.send_command("ping")
        finally:
            client.close()

        thread.join(timeout=1.0)
        self.assertFalse(errors, f"Server thread errors: {errors}")
        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("result"), {"pong": True})


if __name__ == "__main__":
    unittest.main()
