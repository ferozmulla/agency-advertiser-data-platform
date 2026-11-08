from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_parent_orchestrator_yaml_structure():
    path = ROOT / "workflows" / "parent_orchestrator.yaml"
    assert path.exists(), "parent_orchestrator.yaml must exist"
    content = yaml.safe_load(path.read_text())
    assert "main" in content
    steps = content["main"]["steps"]
    step_names = [list(s.keys())[0] for s in steps]
    assert "query_active_tenants" in step_names
    assert "fan_out_tenants" in step_names


def test_tenant_child_workflow_yaml_structure():
    path = ROOT / "workflows" / "tenant_child_workflow.yaml"
    assert path.exists(), "tenant_child_workflow.yaml must exist"
    raw_text = path.read_text()
    content = yaml.safe_load(raw_text)
    assert "main" in content
    assert "compilationResults" in raw_text
    assert "workflowInvocations" in raw_text
    assert "serviceAccount" in raw_text
    assert "run_log" in raw_text


def test_dataform_workflow_settings():
    ws_path = ROOT / "dataform" / "workflow_settings.yaml"
    assert ws_path.exists(), "workflow_settings.yaml must exist"
    cfg = yaml.safe_load(ws_path.read_text())
    assert "defaultProject" in cfg
    assert "vars" in cfg
    assert "tenant_id" in cfg["vars"]
    assert "landing_bucket" in cfg["vars"]


def test_dataform_sqlx_definitions_complete():
    expected_files = [
        "dataform/definitions/bronze/raw_ad_spend_daily.sqlx",
        "dataform/definitions/bronze/raw_crm_customers.sqlx",
        "dataform/definitions/bronze/raw_conversions.sqlx",
        "dataform/definitions/silver/stg_ad_spend_daily.sqlx",
        "dataform/definitions/silver/stg_crm_customers.sqlx",
        "dataform/definitions/silver/stg_conversions.sqlx",
        "dataform/definitions/gold/mart_cross_channel_performance.sqlx",
        "dataform/definitions/gold/mart_customer_attribution.sqlx",
        "dataform/definitions/gold/share_cross_channel_performance_iceberg.sqlx",
    ]
    for rel_path in expected_files:
        p = ROOT / rel_path
        assert p.exists(), f"Missing Dataform SQLX file: {rel_path}"

    crm_text = (ROOT / "dataform/definitions/silver/stg_crm_customers.sqlx").read_text()
    assert "SHA256" in crm_text
    assert "email_hash" in crm_text
    assert "assertions" in crm_text

    iceberg_text = (
        ROOT / "dataform/definitions/gold/share_cross_channel_performance_iceberg.sqlx"
    ).read_text()
    assert "table_format = 'ICEBERG'" in iceberg_text
    assert "file_format = 'PARQUET'" in iceberg_text

