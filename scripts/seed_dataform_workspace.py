#!/usr/bin/env python3
"""Creates/updates the 'default' Dataform workspace inside agency-platform-123,
uploads all files from dataform/, and runs a compilation verification check.
"""

import base64
from pathlib import Path
import google.auth
from google.auth.transport.requests import Request
import requests

ADMIN_PROJECT_ID = "agency-platform-123"
REGION = "us-central1"
REPO_ID = "medallion-pipeline"
WORKSPACE_ID = "default"
ROOT = Path(__file__).resolve().parent.parent
DATAFORM_DIR = ROOT / "dataform"


def get_headers() -> dict[str, str]:
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "x-goog-user-project": ADMIN_PROJECT_ID,
    }


def main() -> None:
    headers = get_headers()
    repo_url = f"https://dataform.googleapis.com/v1beta1/projects/{ADMIN_PROJECT_ID}/locations/{REGION}/repositories/{REPO_ID}"
    ws_url = f"{repo_url}/workspaces/{WORKSPACE_ID}"

    # 1. Ensure workspace exists
    res = requests.get(ws_url, headers=headers, timeout=30)
    if res.status_code == 404:
        create_res = requests.post(
            f"{repo_url}/workspaces",
            params={"workspaceId": WORKSPACE_ID},
            json={},
            headers=headers,
            timeout=30,
        )
        create_res.raise_for_status()
        print(f"Created Dataform workspace: {WORKSPACE_ID}")
    else:
        res.raise_for_status()
        print(f"Using existing Dataform workspace: {WORKSPACE_ID}")

    # 2. Upload all files from dataform/
    files_to_upload = sorted(
        p for p in DATAFORM_DIR.rglob("*") if p.is_file() and (p.suffix in {".yaml", ".sqlx", ".js"})
    )
    for file_path in files_to_upload:
        rel_path = file_path.relative_to(DATAFORM_DIR).as_posix()
        b64_contents = base64.b64encode(file_path.read_bytes()).decode("ascii")
        write_res = requests.post(
            f"{ws_url}:writeFile",
            json={"path": rel_path, "contents": b64_contents},
            headers=headers,
            timeout=30,
        )
        write_res.raise_for_status()
        print(f"Uploaded to Dataform workspace: {rel_path}")

    # 3. Verify compilation for advertiser-01 and advertiser-02
    for tenant_id, project_id in [("advertiser_01", "advertiser-01"), ("advertiser_02", "advertiser-02")]:
        comp_res = requests.post(
            f"{repo_url}/compilationResults",
            json={
                "workspace": f"projects/{ADMIN_PROJECT_ID}/locations/{REGION}/repositories/{REPO_ID}/workspaces/{WORKSPACE_ID}",
                "codeCompilationConfig": {
                    "defaultDatabase": project_id,
                    "defaultSchema": "silver",
                    "assertionSchema": "silver",
                    "vars": {
                        "tenant_id": tenant_id,
                        "landing_bucket": f"{project_id}-landing",
                        "biglake_connection": f"{project_id}.{REGION}.lakehouse-connection",
                    },
                },
            },
            headers=headers,
            timeout=60,
        )
        comp_res.raise_for_status()
        body = comp_res.json()
        errors = body.get("compilationErrors", [])
        if errors:
            raise RuntimeError(f"Dataform compilation errors for {project_id}: {errors}")
        print(f"Verified clean Dataform compilation for {project_id}: {body['name']}")


if __name__ == "__main__":
    main()
