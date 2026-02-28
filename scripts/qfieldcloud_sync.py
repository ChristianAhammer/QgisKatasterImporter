#!/usr/bin/env python3
"""Reliable QFieldCloud sync helper using qfieldcloud_sdk.Client.

This script uploads a local project folder, creates the remote project if needed,
triggers processing/package jobs, and verifies remote files.
"""

import argparse
import getpass
import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

from qfieldcloud_sdk.sdk import Client, FileTransferType, JobTypes


def normalize_project_id(value: str) -> str:
    value = value.strip()
    value = value.replace("https://app.qfield.cloud/", "")
    value = value.replace("http://app.qfield.cloud/", "")
    value = value.strip("/")
    return value


def parse_owner_name(project_id: str) -> Tuple[Optional[str], str]:
    parts = project_id.split("/")
    if len(parts) == 3 and parts[0] == "a":
        return parts[1], parts[2]
    return None, project_id


def resolve_project_uuid(client: Client, project_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    owner, name = parse_owner_name(project_id)
    try:
        projects = client.list_projects()
    except Exception:
        return None, None

    for project in projects:
        if not isinstance(project, dict):
            continue
        project_name = str(project.get("name") or "")
        project_owner = str(project.get("owner") or "")
        if owner:
            if project_name == name and project_owner == owner:
                return str(project.get("id") or ""), project
        else:
            if project_name == name:
                return str(project.get("id") or ""), project
    return None, None


def extract_id(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in ("id", "job_id", "uuid"):
            if key in payload and payload[key]:
                return str(payload[key])
        for value in payload.values():
            found = extract_id(value)
            if found:
                return found
    return None


def wait_for_job(client: Client, job_id: str, timeout: int, poll_seconds: int) -> Tuple[bool, Dict[str, Any]]:
    ok_states = {"finished", "success", "succeeded", "done", "completed"}
    bad_states = {"failed", "error", "cancelled", "canceled"}
    start = time.time()
    last: Dict[str, Any] = {}

    while time.time() - start <= timeout:
        status = client.job_status(job_id)
        last = status if isinstance(status, dict) else {"raw": status}
        state = str(last.get("status") or last.get("state") or "").lower()
        if state in ok_states:
            return True, last
        if state in bad_states:
            return False, last
        time.sleep(poll_seconds)

    return False, last


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Sync local project folder to QFieldCloud.")
    parser.add_argument("--url", default="https://app.qfield.cloud/api/v1/")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--token")
    parser.add_argument("--username")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--auto-create", action="store_true")
    parser.add_argument("--wait-timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--summary-json")
    args = parser.parse_args(argv)

    token = args.token or os.environ.get("QFIELDCLOUD_TOKEN", "")
    username = args.username or os.environ.get("QFIELDCLOUD_USERNAME", "")
    email = args.email or os.environ.get("QFIELDCLOUD_EMAIL", "")
    login_user = username or email
    password = args.password or os.environ.get("QFIELDCLOUD_PASSWORD", "")

    summary: Dict[str, Any] = {
        "ok": False,
        "project_id_input": args.project_id,
        "project_id": normalize_project_id(args.project_id),
        "project_path": args.project_path,
        "created_project": False,
        "upload_result": None,
        "process_job": None,
        "package_job": None,
        "remote_file_count": 0,
        "errors": [],
    }

    try:
        project_id = summary["project_id"]
        if not os.path.isdir(args.project_path):
            raise RuntimeError(f"Project path not found: {args.project_path}")

        project_files = sorted(
            name for name in os.listdir(args.project_path) if name.lower().endswith((".qgs", ".qgz"))
        )
        summary["project_files"] = project_files
        if not project_files:
            raise RuntimeError(
                "Missing QGIS project file (.qgs/.qgz) in upload folder. "
                "Please include a project file next to the GeoPackage before syncing."
            )

        client = Client(url=args.url, verify_ssl=True, token=token)
        if not token:
            if login_user and not password:
                try:
                    password = getpass.getpass("QFieldCloud password: ")
                except Exception:
                    password = input("QFieldCloud password: ")

            if login_user and password:
                login_result = client.login(login_user, password)
                summary["login_result"] = login_result
                token = None
                if isinstance(login_result, dict):
                    token = login_result.get("token")
                if token:
                    client = Client(url=args.url, verify_ssl=True, token=str(token))
            else:
                raise RuntimeError("No token provided. Use token or username/email login.")

        status = client.check_server_status()
        summary["server_status"] = status
        print(f"QFieldCloud status: {status}")

        owner, name = parse_owner_name(project_id)
        resolved_uuid, resolved_project = resolve_project_uuid(client, project_id)
        if resolved_uuid:
            summary["project_id_resolved"] = resolved_uuid
            summary["project"] = resolved_project
            print(f"Project resolved to UUID: {resolved_uuid}")
            project_id = resolved_uuid

        project_exists = True
        try:
            project = client.get_project(project_id)
            summary["project"] = project
            print(f"Project found: {project_id}")
        except Exception:
            project_exists = False

        if not project_exists:
            if not args.auto_create:
                raise RuntimeError(f"Project not found: {project_id}")
            print(f"Project not found. Creating: name={name} owner={owner or '(default)'}")
            try:
                created = client.create_project(name, owner=owner)
                summary["created_project"] = True
                summary["created_project_response"] = created
            except Exception as err:
                if "project_already_exists" not in str(err):
                    raise
                # Race or slug lookup mismatch: resolve the existing project.
                resolved_uuid, resolved_project = resolve_project_uuid(client, summary["project_id"])
                if not resolved_uuid:
                    raise
                summary["project_id_resolved"] = resolved_uuid
                summary["project"] = resolved_project
                project_id = resolved_uuid
                print(f"Existing project resolved after create conflict: {project_id}")

            if summary.get("created_project"):
                # Newly created projects are looked up again to get a stable UUID.
                resolved_uuid, resolved_project = resolve_project_uuid(client, summary["project_id"])
                if resolved_uuid:
                    summary["project_id_resolved"] = resolved_uuid
                    summary["project"] = resolved_project
                    project_id = resolved_uuid

        print(f"Uploading local folder: {args.project_path}")
        upload_result = client.upload_files(
            project_id=project_id,
            upload_type=FileTransferType.PROJECT,
            project_path=args.project_path,
            filter_glob="*",
            throw_on_error=True,
            show_progress=False,
            force=True,
        )
        summary["upload_result"] = upload_result
        print("Upload finished.")

        process_resp = client.job_trigger(project_id, JobTypes.PROCESS_PROJECTFILE, force=True)
        package_resp = client.job_trigger(project_id, JobTypes.PACKAGE, force=True)
        summary["process_trigger"] = process_resp
        summary["package_trigger"] = package_resp

        process_id = extract_id(process_resp)
        package_id = extract_id(package_resp)
        if process_id:
            ok, proc_status = wait_for_job(client, process_id, args.wait_timeout, args.poll_seconds)
            summary["process_job"] = {"id": process_id, "ok": ok, "status": proc_status}
            print(f"process_projectfile job {'OK' if ok else 'FAILED'}: {process_id}")
            if not ok:
                raise RuntimeError("process_projectfile job did not complete successfully")

        if package_id:
            ok, pkg_status = wait_for_job(client, package_id, args.wait_timeout, args.poll_seconds)
            summary["package_job"] = {"id": package_id, "ok": ok, "status": pkg_status}
            print(f"package job {'OK' if ok else 'FAILED'}: {package_id}")
            if not ok:
                raise RuntimeError("package job did not complete successfully")

        remote_files = client.list_remote_files(project_id, skip_metadata=False)
        summary["remote_file_count"] = len(remote_files)
        summary["remote_files_sample"] = remote_files[:20]
        gpkg_name = os.path.basename(os.path.normpath(args.project_path)) + ".gpkg"
        has_gpkg = any(
            str(item.get("name") or item.get("path") or "").lower().endswith(gpkg_name.lower())
            for item in remote_files
            if isinstance(item, dict)
        )
        summary["has_expected_gpkg"] = has_gpkg
        print(f"Remote files: {len(remote_files)}; expected GPKG present: {has_gpkg}")

        summary["ok"] = True
        if args.summary_json:
            with open(args.summary_json, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
        return 0

    except Exception as err:
        summary["errors"].append(str(err))
        print(f"Cloud sync error: {err}", file=sys.stderr)
        if args.summary_json:
            with open(args.summary_json, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
