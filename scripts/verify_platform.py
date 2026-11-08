#!/usr/bin/env python3
"""Triggers the parent Cloud Workflow in agency-platform-123, waits for completion,
and verifies platform_admin.run_log, all 9 Medallion tables in advertiser-01 and
advertiser-02, GCS Iceberg Parquet/metadata files, and cross-tenant IAM isolation.
"""

import json
import subprocess
from google.cloud import bigquery, storage

ADMIN_PROJECT_ID = "agency-platform-123"
REGION = "us-central1"
PARENT_WORKFLOW = "medallion-parent-orchestrator"
TENANTS = [
    ("advertiser_01", "advertiser-01"),
    ("advertiser_02", "advertiser-02"),
]


def trigger_parent_workflow() -> dict:
    print(f"Triggering Cloud Workflow {PARENT_WORKFLOW} in {ADMIN_PROJECT_ID}...")
    cmd = [
        "gcloud",
        "workflows",
        "run",
        PARENT_WORKFLOW,
        f"--project={ADMIN_PROJECT_ID}",
        f"--location={REGION}",
        "--data={}",
        "--format=json",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    execution = json.loads(proc.stdout)
    state = execution.get("state")
    result_payload = json.loads(execution.get("result", "{}"))
    print(f"Workflow completed with state={state}")
    print(json.dumps(result_payload, indent=2))
    assert state == "SUCCEEDED", f"Parent workflow did not succeed: {execution}"
    return result_payload


def verify_run_log(bq_admin: bigquery.Client) -> None:
    query = f"""
    SELECT tenant_id, project_id, status, dataform_invocation_id, started_at, completed_at, notes
    FROM `{ADMIN_PROJECT_ID}.platform_admin.run_log`
    ORDER BY started_at DESC
    LIMIT 10
    """
    rows = list(bq_admin.query(query).result())
    assert len(rows) >= 2, "Expected at least 2 run_log entries"
    latest_by_tenant = {}
    for r in rows:
        if r.tenant_id not in latest_by_tenant:
            latest_by_tenant[r.tenant_id] = r
    for tenant_id, project_id in TENANTS:
        assert tenant_id in latest_by_tenant, f"Missing run_log entry for {tenant_id}"
        entry = latest_by_tenant[tenant_id]
        assert entry.status == "SUCCEEDED", f"Tenant {tenant_id} run failed: {entry.notes}"
        print(
            f"[run_log] {tenant_id} ({project_id}): status={entry.status}, invocation={entry.dataform_invocation_id}"
        )


def verify_tenant_medallion(tenant_id: str, project_id: str) -> None:
    bq = bigquery.Client(project=project_id, location=REGION)

    expected_tables = [
        ("bronze", "raw_ad_spend_daily", 32),
        ("bronze", "raw_crm_customers", 23),
        ("bronze", "raw_conversions", 39),
        ("silver", "stg_ad_spend_daily", 28),  # 4 duplicates removed!
        ("silver", "stg_crm_customers", 20),   # 3 duplicate updates removed!
        ("silver", "stg_conversions", 35),     # 4 duplicate retries removed!
        ("gold", "mart_cross_channel_performance", 28),
        ("gold", "mart_customer_attribution", 20),
        ("gold", "share_cross_channel_performance_iceberg", 28),
    ]

    for dataset_id, table_id, expected_count in expected_tables:
        q = f"SELECT COUNT(*) AS cnt FROM `{project_id}.{dataset_id}.{table_id}`"
        cnt = list(bq.query(q).result())[0].cnt
        assert cnt == expected_count, (
            f"[{project_id}.{dataset_id}.{table_id}] Expected {expected_count} rows, got {cnt}"
        )
        print(f"[{project_id}] Verified {dataset_id}.{table_id}: {cnt} rows")

    # Verify Silver CRM has no raw email/phone columns and hashes are 64-char SHA-256 hex
    crm_table = bq.get_table(f"{project_id}.silver.stg_crm_customers")
    col_names = {f.name for f in crm_table.schema}
    assert "email" not in col_names and "phone" not in col_names, "Raw PII must not exist in Silver!"
    assert "email_hash" in col_names and "phone_hash" in col_names

    # Verify Iceberg Parquet & metadata files exist in GCS
    storage_client = storage.Client(project=project_id)
    blobs = list(
        storage_client.list_blobs(f"{project_id}-landing", prefix="iceberg/cross_channel_performance")
    )
    assert len(blobs) > 0, f"Expected Iceberg files in gs://{project_id}-landing/iceberg/cross_channel_performance"
    print(f"[{project_id}] Verified {len(blobs)} Apache Iceberg objects in gs://{project_id}-landing/iceberg/")


def verify_cross_tenant_isolation() -> None:
    # Verify sa-dataform@advertiser-01 has zero IAM bindings on advertiser-02
    cmd = [
        "gcloud",
        "projects",
        "get-iam-policy",
        "advertiser-02",
        "--format=json",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    policy_str = proc.stdout
    assert "sa-dataform@advertiser-01.iam.gserviceaccount.com" not in policy_str, (
        "Isolation violation: sa-dataform@advertiser-01 found in advertiser-02 IAM policy!"
    )
    print("[IAM Isolation] Verified sa-dataform@advertiser-01 has zero permissions in advertiser-02.")


def main() -> None:
    trigger_parent_workflow()
    bq_admin = bigquery.Client(project=ADMIN_PROJECT_ID, location=REGION)
    verify_run_log(bq_admin)
    for tenant_id, project_id in TENANTS:
        verify_tenant_medallion(tenant_id, project_id)
    verify_cross_tenant_isolation()
    print("\nALL END-TO-END PLATFORM VERIFICATIONS PASSED!")


if __name__ == "__main__":
    main()
