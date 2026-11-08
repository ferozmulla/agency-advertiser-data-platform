# Multi-Tenant Agency-Advertisers Data Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a functional multi-tenant, isolated Agency-Advertisers Medallion Data Platform across `agency-platform-123` (centralized admin/orchestration plane), `advertiser-01`, and `advertiser-02` (isolated advertiser tenant projects) using Terraform, Dataform, Cloud Workflows, BigQuery (External Bronze, Native Silver/Gold, Managed Iceberg Gold Share), Analytics Hub, and Python synthetic data tooling.

**Architecture:** A centralized Agency Admin GCP project (`agency-platform-123`) hosts the control plane (`platform_admin` dataset), a single Dataform SQLX repository (`medallion-pipeline`), and Cloud Workflows parent/child fan-out orchestration. Each advertiser (`advertiser-01`, `advertiser-02`) resides in an isolated GCP project provisioned via a Terraform "Tenant Factory" module with its own GCS landing/Iceberg bucket, BigLake connection, `bronze`/`silver`/`gold` BigQuery datasets, Analytics Hub listing, and dedicated service account (`sa-dataform@<tenant_project>`). Dataform compiles dynamically per tenant and executes transformations as that tenant's service account.

**Tech Stack:** Terraform (`hashicorp/google` & `hashicorp/google-beta` ~> 5.0), BigQuery (Native, BigLake External, BigLake Apache Iceberg, Analytics Hub), Dataform (`v1beta1` SQLX), Cloud Workflows, Cloud Scheduler, Python 3 (`google-cloud-bigquery`, `google-cloud-storage`, `google-auth`, `requests`, `pyyaml`, `pytest`).

## Global Constraints

- **Target GCP Projects:**
  - Agency Admin Project: `agency-platform-123`
  - Advertiser Tenant 1 Project: `advertiser-01`
  - Advertiser Tenant 2 Project: `advertiser-02`
- **Default Region / BigQuery Location:** `us-central1`
- **Table Count Constraint:** Strictly `< 10` tables per tenant project (9 tables total per tenant: 3 Bronze BigLake External, 3 Silver Native, 2 Gold Native Marts, 1 Gold BigLake Managed Apache Iceberg table).
- **No Live GMP or 3P Ad API Connectors:** Do not deploy live Google Marketing Platform or 3P Ad API ingestion jobs; keep their definitions in feature-flagged Terraform (`enable_dts_connectors = false`) and land synthetic CSV feeds directly in each tenant's GCS landing bucket.
- **No Blocking VPC-SC in Live Build:** Keep VPC Service Controls (`enable_vpc_sc = false`), CMEK (`enable_cmek = false`), Dataplex governance (`enable_dataplex_governance = false`), Monitoring alerts (`enable_monitoring_alerts = false`), and Cloud Build triggers (`enable_cloudbuild_cicd = false`) in modular Terraform scripts disabled by default.
- **No Secrets in Git:** Never commit service account keys, OAuth tokens, or `.terraform/` state binaries to Git.

---

## File Map

- `.gitignore` — Excludes `.terraform/`, `*.tfstate*`, `__pycache__/`, `.venv/`, and temporary credentials.
- `workflows/tenant_child_workflow.yaml` — Per-tenant Cloud Workflow executing run logging, Dataform compilation with project/var overrides, Dataform invocation as `sa-dataform@<tenant>`, polling, and error capture.
- `workflows/parent_orchestrator.yaml` — Parent Cloud Workflow reading active tenants from `agency-platform-123.platform_admin.tenants` and fanning out in parallel to `medallion-tenant-child-workflow`.
- `dataform/workflow_settings.yaml` — Central Dataform project config with default `vars` (`tenant_id`, `landing_bucket`, `biglake_connection`).
- `dataform/definitions/bronze/raw_ad_spend_daily.sqlx` — Dataform source declaration for `bronze.raw_ad_spend_daily`.
- `dataform/definitions/bronze/raw_crm_customers.sqlx` — Dataform source declaration for `bronze.raw_crm_customers`.
- `dataform/definitions/bronze/raw_conversions.sqlx` — Dataform source declaration for `bronze.raw_conversions`.
- `dataform/definitions/silver/stg_ad_spend_daily.sqlx` — Silver SQLX table deduplicating ad spend, standardizing channels, normalizing FX to USD, with Dataform assertions.
- `dataform/definitions/silver/stg_crm_customers.sqlx` — Silver SQLX table deduplicating customers and hashing PII (`email_hash`, `phone_hash`) with Dataform assertions.
- `dataform/definitions/silver/stg_conversions.sqlx` — Silver SQLX table deduplicating conversions, normalizing timestamps and USD revenue, hashing PII, with Dataform assertions.
- `dataform/definitions/gold/mart_cross_channel_performance.sqlx` — Gold SQLX native mart calculating daily ROAS, CPA, CTR, and budget pacing by channel/campaign.
- `dataform/definitions/gold/mart_customer_attribution.sqlx` — Gold SQLX native mart joining hashed customers, conversions, and campaign channels.
- `dataform/definitions/gold/share_cross_channel_performance_iceberg.sqlx` — Gold SQLX `operations` definition creating and refreshing the BigLake Managed Apache Iceberg table backed by GCS Parquet/Iceberg metadata.
- `terraform/versions.tf` — Terraform & provider version constraints.
- `terraform/variables.tf` — Root variables including `admin_project_id`, `region`, `tenants` map, and enterprise feature flags.
- `terraform/terraform.tfvars` — Concrete configuration for `agency-platform-123`, `advertiser-01`, and `advertiser-02`.
- `terraform/main.tf` — Root orchestration wiring `agency_admin`, `tenant_factory` (`for_each = var.tenants`), and `enterprise_reference`.
- `terraform/outputs.tf` — Outputs for admin resources and per-tenant buckets, service accounts, datasets, and Analytics Hub listings.
- `terraform/modules/agency_admin/{variables.tf,main.tf,outputs.tf}` — Provisions `platform_admin` dataset & tables, `sa-orchestrator`, Dataform repository, Cloud Workflows, and Cloud Scheduler.
- `terraform/modules/tenant_factory/{variables.tf,main.tf,outputs.tf}` — Provisions per-tenant GCS landing/Iceberg bucket, `bronze`/`silver`/`gold` datasets, BigLake connection, `sa-dataform@<tenant>`, cross-project Dataform impersonation IAM, and Analytics Hub exchange/listing.
- `terraform/modules/enterprise_reference/{variables.tf,vpc_sc.tf,cmek.tf,dts_connectors.tf,governance.tf,monitoring.tf,cicd_cloudbuild.tf}` — Production reference HCL modules behind feature flags.
- `scripts/generate_and_load_synthetic_data.py` — Generates deterministic, realistic multi-channel ad spend, CRM customer, and conversion CSV feeds for `advertiser-01` and `advertiser-02`, uploads to GCS, creates the 3 Bronze BigLake external tables per tenant, and seeds `platform_admin` tables.
- `scripts/seed_dataform_workspace.py` — Uploads all local `dataform/` files into the `agency-platform-123` Dataform `default` workspace via the Dataform REST API and verifies compilation.
- `scripts/verify_platform.py` — Triggers `medallion-parent-orchestrator`, waits for completion, and verifies `platform_admin.run_log`, all 9 Medallion tables per tenant, GCS Iceberg metadata/Parquet files, Analytics Hub listings, and cross-tenant IAM isolation.
- `tests/test_workflows_and_dataform.py` — Unit tests verifying Cloud Workflows YAML structure and Dataform SQLX completeness, PII removal, and assertion presence.
- `tests/test_synthetic_data.py` — Unit tests verifying synthetic dataset schemas, intentional duplicates, multi-currency rows, and tenant differentiation.
- `README.md` — Comprehensive guide explaining the architecture, live demo queries, and how to onboard `advertiser-03`.

---

### Task 1: Cloud Workflows YAML Definitions & Static Validation Tests

**Files:**
- Create: `.gitignore`
- Create: `workflows/tenant_child_workflow.yaml`
- Create: `workflows/parent_orchestrator.yaml`
- Create: `tests/test_workflows_and_dataform.py`

**Interfaces:**
- Produces:
  - `workflows/tenant_child_workflow.yaml` (accepts `{admin_project_id, region, dataform_repo_id, dataform_workspace_id, parent_execution_id, tenant}` and returns `{tenant_id, project_id, status, invocation_name}`)
  - `workflows/parent_orchestrator.yaml` (queries `platform_admin.tenants` and invokes `medallion-tenant-child-workflow` in parallel)

- [ ] **Step 1: Write `.gitignore` and the failing workflow validation test in `tests/test_workflows_and_dataform.py`**

Create `.gitignore`:
```gitignore
.terraform/
*.tfstate
*.tfstate.*
crash.log
*.tfvars.backup
.terraform.lock.hcl
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
```

Create `tests/test_workflows_and_dataform.py`:
```python
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
```

- [ ] **Step 2: Run `pytest` to verify the test fails**

Run: `pytest tests/test_workflows_and_dataform.py -v`
Expected: FAIL with `AssertionError: parent_orchestrator.yaml must exist`

- [ ] **Step 3: Write `workflows/tenant_child_workflow.yaml` and `workflows/parent_orchestrator.yaml`**

Create `workflows/tenant_child_workflow.yaml`:
```yaml
main:
  params: [args]
  steps:
    - init_vars:
        assign:
          - admin_project_id: ${args.admin_project_id}
          - region: ${args.region}
          - dataform_repo_id: ${args.dataform_repo_id}
          - dataform_workspace_id: ${args.dataform_workspace_id}
          - parent_execution_id: ${args.parent_execution_id}
          - tenant: ${args.tenant}
          - tenant_id: ${tenant.tenant_id}
          - tenant_project_id: ${tenant.project_id}
          - tenant_sa: ${tenant.service_account_email}
          - landing_bucket: ${tenant.landing_bucket}
          - biglake_connection_id: ${tenant.biglake_connection_id}
          - run_id: ${sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")}
          - repo_base_url: ${"https://dataform.googleapis.com/v1beta1/projects/" + admin_project_id + "/locations/" + region + "/repositories/" + dataform_repo_id}
          - workspace_path: ${"projects/" + admin_project_id + "/locations/" + region + "/repositories/" + dataform_repo_id + "/workspaces/" + dataform_workspace_id}
          - compilation_name: "NONE"
          - invocation_name: "NONE"

    - log_run_start:
        call: googleapis.bigquery.v2.jobs.query
        args:
          projectId: ${admin_project_id}
          body:
            useLegacySql: false
            query: ${"INSERT INTO `" + admin_project_id + ".platform_admin.run_log` (run_id, parent_execution_id, tenant_id, project_id, status, dataform_compilation_id, dataform_invocation_id, started_at, completed_at, notes) VALUES ('" + run_id + "', '" + parent_execution_id + "', '" + tenant_id + "', '" + tenant_project_id + "', 'RUNNING', NULL, NULL, CURRENT_TIMESTAMP(), NULL, 'Started per-tenant child workflow')"}
        result: log_start_res

    - execute_pipeline:
        try:
          steps:
            - compile_dataform:
                call: http.post
                args:
                  url: ${repo_base_url + "/compilationResults"}
                  auth:
                    type: OAuth2
                  body:
                    workspace: ${workspace_path}
                    codeCompilationConfig:
                      defaultDatabase: ${tenant_project_id}
                      defaultSchema: "silver"
                      assertionSchema: "silver"
                      vars:
                        tenant_id: ${tenant_id}
                        landing_bucket: ${landing_bucket}
                        biglake_connection: ${biglake_connection_id}
                result: compile_res

            - save_compilation:
                assign:
                  - compilation_name: ${compile_res.body.name}

            - invoke_dataform:
                call: http.post
                args:
                  url: ${repo_base_url + "/workflowInvocations"}
                  auth:
                    type: OAuth2
                  body:
                    compilationResult: ${compilation_name}
                    invocationConfig:
                      serviceAccount: ${tenant_sa}
                      transitiveDependenciesIncluded: true
                      transitiveDependentsIncluded: true
                result: invoke_res

            - save_invocation:
                assign:
                  - invocation_name: ${invoke_res.body.name}
                  - invocation_state: ${default(map.get(invoke_res.body, "state"), "RUNNING")}

            - poll_loop:
                switch:
                  - condition: ${invocation_state == "RUNNING" or invocation_state == "CANCELING"}
                    steps:
                      - wait_5s:
                          call: sys.sleep
                          args:
                            seconds: 5
                      - check_status:
                          call: http.get
                          args:
                            url: ${"https://dataform.googleapis.com/v1beta1/" + invocation_name}
                            auth:
                              type: OAuth2
                          result: status_res
                      - update_state:
                          assign:
                            - invocation_state: ${status_res.body.state}
                          next: poll_loop
                  - condition: ${invocation_state == "SUCCEEDED"}
                    next: log_run_success
                next: raise_invocation_failure

            - raise_invocation_failure:
                raise: ${"Dataform invocation ended in state: " + invocation_state}

            - log_run_success:
                call: googleapis.bigquery.v2.jobs.query
                args:
                  projectId: ${admin_project_id}
                  body:
                    useLegacySql: false
                    query: ${"UPDATE `" + admin_project_id + ".platform_admin.run_log` SET status = 'SUCCEEDED', dataform_compilation_id = '" + compilation_name + "', dataform_invocation_id = '" + invocation_name + "', completed_at = CURRENT_TIMESTAMP(), notes = 'Medallion Bronze->Silver->Gold+Iceberg pipeline succeeded' WHERE run_id = '" + run_id + "'"}
                result: log_success_res

            - return_success:
                return:
                  run_id: ${run_id}
                  tenant_id: ${tenant_id}
                  project_id: ${tenant_project_id}
                  status: "SUCCEEDED"
                  compilation_name: ${compilation_name}
                  invocation_name: ${invocation_name}

        except:
          as: e
          steps:
            - log_run_failure:
                call: googleapis.bigquery.v2.jobs.query
                args:
                  projectId: ${admin_project_id}
                  body:
                    useLegacySql: false
                    query: ${"UPDATE `" + admin_project_id + ".platform_admin.run_log` SET status = 'FAILED', dataform_compilation_id = '" + compilation_name + "', dataform_invocation_id = '" + invocation_name + "', completed_at = CURRENT_TIMESTAMP(), notes = 'Pipeline failed during execution' WHERE run_id = '" + run_id + "'"}
                result: log_fail_res
            - return_failure:
                return:
                  run_id: ${run_id}
                  tenant_id: ${tenant_id}
                  project_id: ${tenant_project_id}
                  status: "FAILED"
                  error: ${e}
```

Create `workflows/parent_orchestrator.yaml`:
```yaml
main:
  params: [args]
  steps:
    - init_defaults:
        assign:
          - admin_project_id: ${sys.get_env("GOOGLE_CLOUD_PROJECT_ID")}
          - region: "us-central1"
          - dataform_repo_id: "medallion-pipeline"
          - dataform_workspace_id: "default"
          - child_workflow_id: "medallion-tenant-child-workflow"
          - parent_execution_id: ${sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")}
          - tenant_list: []
          - tenant_outcomes: {}

    - query_active_tenants:
        call: googleapis.bigquery.v2.jobs.query
        args:
          projectId: ${admin_project_id}
          body:
            useLegacySql: false
            query: ${"SELECT tenant_id, project_id, tenant_name, service_account_email, landing_bucket, biglake_connection_id FROM `" + admin_project_id + ".platform_admin.tenants` WHERE is_active = TRUE ORDER BY tenant_id"}
        result: bq_res

    - parse_tenant_rows:
        for:
          value: row
          in: ${default(map.get(bq_res, "rows"), [])}
          steps:
            - append_tenant:
                assign:
                  - tenant_obj:
                      tenant_id: ${row.f[0].v}
                      project_id: ${row.f[1].v}
                      tenant_name: ${row.f[2].v}
                      service_account_email: ${row.f[3].v}
                      landing_bucket: ${row.f[4].v}
                      biglake_connection_id: ${row.f[5].v}
                  - tenant_list: ${list.concat(tenant_list, tenant_obj)}

    - fan_out_tenants:
        parallel:
          shared: [tenant_outcomes]
          for:
            value: tenant_item
            in: ${tenant_list}
            steps:
              - run_child_workflow:
                  call: googleapis.workflowexecutions.v1.projects.locations.workflows.executions.run
                  args:
                    workflow_id: ${child_workflow_id}
                    location: ${region}
                    project_id: ${admin_project_id}
                    connector_params:
                      timeout: 1800
                    argument:
                      admin_project_id: ${admin_project_id}
                      region: ${region}
                      dataform_repo_id: ${dataform_repo_id}
                      dataform_workspace_id: ${dataform_workspace_id}
                      parent_execution_id: ${parent_execution_id}
                      tenant: ${tenant_item}
                  result: child_res
              - record_outcome:
                  assign:
                    - tenant_outcomes[tenant_item.tenant_id]: ${child_res}

    - return_summary:
        return:
          parent_execution_id: ${parent_execution_id}
          tenants_processed: ${len(tenant_list)}
          outcomes: ${tenant_outcomes}
```

- [ ] **Step 4: Run `pytest` to verify workflow tests pass**

Run: `pytest tests/test_workflows_and_dataform.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit Task 1**

```bash
git add .gitignore workflows/tenant_child_workflow.yaml workflows/parent_orchestrator.yaml tests/test_workflows_and_dataform.py
git commit -m "feat(workflows): add parent fan-out and per-tenant child Cloud Workflows"
```

---

### Task 2: Single-Repo Dataform Medallion SQLX Codebase (`dataform/`)

**Files:**
- Create: `dataform/workflow_settings.yaml`
- Create: `dataform/definitions/bronze/raw_ad_spend_daily.sqlx`
- Create: `dataform/definitions/bronze/raw_crm_customers.sqlx`
- Create: `dataform/definitions/bronze/raw_conversions.sqlx`
- Create: `dataform/definitions/silver/stg_ad_spend_daily.sqlx`
- Create: `dataform/definitions/silver/stg_crm_customers.sqlx`
- Create: `dataform/definitions/silver/stg_conversions.sqlx`
- Create: `dataform/definitions/gold/mart_cross_channel_performance.sqlx`
- Create: `dataform/definitions/gold/mart_customer_attribution.sqlx`
- Create: `dataform/definitions/gold/share_cross_channel_performance_iceberg.sqlx`
- Modify: `tests/test_workflows_and_dataform.py`

**Interfaces:**
- Consumes: Compilation override variables `defaultDatabase`, `vars.tenant_id`, `vars.landing_bucket`, `vars.biglake_connection` passed by `workflows/tenant_child_workflow.yaml`.
- Produces: 3 Bronze declaration sources, 3 Silver native tables + assertions, 2 Gold native marts + assertions, and 1 Gold Managed Apache Iceberg table (`gold.share_cross_channel_performance_iceberg`).

- [ ] **Step 1: Add failing Dataform SQLX verification tests to `tests/test_workflows_and_dataform.py`**

Append to `tests/test_workflows_and_dataform.py`:
```python
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
```

- [ ] **Step 2: Run `pytest` to verify the new Dataform tests fail**

Run: `pytest tests/test_workflows_and_dataform.py -v`
Expected: FAIL with `AssertionError: workflow_settings.yaml must exist`

- [ ] **Step 3: Create `dataform/workflow_settings.yaml` and all 9 SQLX files in `dataform/definitions/`**

Create `dataform/workflow_settings.yaml`:
```yaml
defaultProject: advertiser-01
defaultLocation: us-central1
defaultDataset: silver
defaultAssertionDataset: silver
dataformCoreVersion: 3.0.0
vars:
  tenant_id: advertiser_01
  landing_bucket: advertiser-01-landing
  biglake_connection: advertiser-01.us-central1.lakehouse-connection
```

Create `dataform/definitions/bronze/raw_ad_spend_daily.sqlx`:
```sql
config {
  type: "declaration",
  database: dataform.projectConfig.defaultDatabase,
  schema: "bronze",
  name: "raw_ad_spend_daily",
  description: "External BigLake table over GCS raw daily ad spend feed"
}
```

Create `dataform/definitions/bronze/raw_crm_customers.sqlx`:
```sql
config {
  type: "declaration",
  database: dataform.projectConfig.defaultDatabase,
  schema: "bronze",
  name: "raw_crm_customers",
  description: "External BigLake table over GCS 1P CRM customers feed"
}
```

Create `dataform/definitions/bronze/raw_conversions.sqlx`:
```sql
config {
  type: "declaration",
  database: dataform.projectConfig.defaultDatabase,
  schema: "bronze",
  name: "raw_conversions",
  description: "External BigLake table over GCS 1P online and offline conversions feed"
}
```

Create `dataform/definitions/silver/stg_ad_spend_daily.sqlx`:
```sql
config {
  type: "table",
  schema: "silver",
  name: "stg_ad_spend_daily",
  description: "Cleansed, deduplicated, channel-standardized, USD-normalized daily ad spend",
  bigquery: {
    partitionBy: "report_date",
    clusterBy: ["channel", "campaign_id"]
  },
  assertions: {
    uniqueKey: ["report_date", "campaign_id", "channel"],
    nonNull: ["tenant_id", "report_date", "campaign_id", "channel", "spend_usd"],
    rowConditions: [
      "spend_usd >= 0",
      "impressions >= clicks"
    ]
  }
}

WITH deduplicated AS (
  SELECT
    feed_id,
    PARSE_DATE('%Y-%m-%d', TRIM(report_date)) AS report_date,
    TRIM(campaign_id) AS campaign_id,
    TRIM(campaign_name) AS campaign_name,
    CASE
      WHEN UPPER(TRIM(channel)) IN ('GOOGLE_ADS', 'GOOGLE ADS', 'GADS', 'SEARCH') THEN 'GOOGLE_ADS'
      WHEN UPPER(TRIM(channel)) IN ('META', 'FACEBOOK', 'INSTAGRAM', 'META_ADS') THEN 'META'
      WHEN UPPER(TRIM(channel)) IN ('TIKTOK', 'TIKTOK_ADS') THEN 'TIKTOK'
      WHEN UPPER(TRIM(channel)) IN ('DV360', 'DISPLAY_VIDEO_360') THEN 'DV360'
      ELSE UPPER(TRIM(channel))
    END AS channel,
    CAST(impressions AS INT64) AS impressions,
    CAST(clicks AS INT64) AS clicks,
    CAST(spend_raw AS FLOAT64) AS spend_raw,
    UPPER(TRIM(currency)) AS original_currency,
    CAST(daily_budget_usd AS FLOAT64) AS daily_budget_usd,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(ingested_at)) AS ingested_at
  FROM ${ref("raw_ad_spend_daily")}
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY PARSE_DATE('%Y-%m-%d', TRIM(report_date)), TRIM(campaign_id),
      CASE
        WHEN UPPER(TRIM(channel)) IN ('GOOGLE_ADS', 'GOOGLE ADS', 'GADS', 'SEARCH') THEN 'GOOGLE_ADS'
        WHEN UPPER(TRIM(channel)) IN ('META', 'FACEBOOK', 'INSTAGRAM', 'META_ADS') THEN 'META'
        WHEN UPPER(TRIM(channel)) IN ('TIKTOK', 'TIKTOK_ADS') THEN 'TIKTOK'
        WHEN UPPER(TRIM(channel)) IN ('DV360', 'DISPLAY_VIDEO_360') THEN 'DV360'
        ELSE UPPER(TRIM(channel))
      END
    ORDER BY PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(ingested_at)) DESC
  ) = 1
)
SELECT
  '${dataform.projectConfig.vars.tenant_id}' AS tenant_id,
  report_date,
  campaign_id,
  campaign_name,
  channel,
  impressions,
  clicks,
  spend_raw,
  original_currency,
  ROUND(
    spend_raw * CASE original_currency
      WHEN 'USD' THEN 1.0
      WHEN 'EUR' THEN 1.08
      WHEN 'GBP' THEN 1.27
      WHEN 'CAD' THEN 0.74
      ELSE 1.0
    END,
    2
  ) AS spend_usd,
  daily_budget_usd,
  ingested_at,
  CURRENT_TIMESTAMP() AS processed_at
FROM deduplicated
```

Create `dataform/definitions/silver/stg_crm_customers.sqlx`:
```sql
config {
  type: "table",
  schema: "silver",
  name: "stg_crm_customers",
  description: "Deduplicated 1P CRM customers with SHA-256 hashed PII and cleartext PII dropped",
  assertions: {
    uniqueKey: ["customer_id"],
    nonNull: ["tenant_id", "customer_id", "email_hash", "phone_hash"]
  }
}

SELECT
  '${dataform.projectConfig.vars.tenant_id}' AS tenant_id,
  TRIM(customer_id) AS customer_id,
  TO_HEX(SHA256(LOWER(TRIM(email)))) AS email_hash,
  TO_HEX(SHA256(REGEXP_REPLACE(TRIM(phone), r'[^0-9]', ''))) AS phone_hash,
  UPPER(TRIM(loyalty_tier)) AS loyalty_tier,
  UPPER(TRIM(country)) AS country,
  PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(signup_ts)) AS signup_ts,
  PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(updated_at)) AS updated_at,
  CURRENT_TIMESTAMP() AS processed_at
FROM ${ref("raw_crm_customers")}
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY TRIM(customer_id)
  ORDER BY PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(updated_at)) DESC
) = 1
```

Create `dataform/definitions/silver/stg_conversions.sqlx`:
```sql
config {
  type: "table",
  schema: "silver",
  name: "stg_conversions",
  description: "Deduplicated 1P conversions with UTC timestamps, USD revenue, and SHA-256 hashed email",
  bigquery: {
    partitionBy: "conversion_date",
    clusterBy: ["channel", "campaign_id"]
  },
  assertions: {
    uniqueKey: ["conversion_id"],
    nonNull: ["tenant_id", "conversion_id", "customer_id", "email_hash", "revenue_usd"],
    rowConditions: [
      "revenue_usd >= 0"
    ]
  }
}

WITH deduplicated AS (
  SELECT
    TRIM(conversion_id) AS conversion_id,
    TRIM(customer_id) AS customer_id,
    TO_HEX(SHA256(LOWER(TRIM(email)))) AS email_hash,
    TRIM(campaign_id) AS campaign_id,
    CASE
      WHEN UPPER(TRIM(channel)) IN ('GOOGLE_ADS', 'GOOGLE ADS', 'GADS', 'SEARCH') THEN 'GOOGLE_ADS'
      WHEN UPPER(TRIM(channel)) IN ('META', 'FACEBOOK', 'INSTAGRAM', 'META_ADS') THEN 'META'
      WHEN UPPER(TRIM(channel)) IN ('TIKTOK', 'TIKTOK_ADS') THEN 'TIKTOK'
      WHEN UPPER(TRIM(channel)) IN ('DV360', 'DISPLAY_VIDEO_360') THEN 'DV360'
      ELSE UPPER(TRIM(channel))
    END AS channel,
    UPPER(TRIM(conversion_type)) AS conversion_type,
    CAST(revenue_raw AS FLOAT64) AS revenue_raw,
    UPPER(TRIM(currency)) AS original_currency,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(event_ts)) AS event_ts,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(ingested_at)) AS ingested_at
  FROM ${ref("raw_conversions")}
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY TRIM(conversion_id)
    ORDER BY PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TRIM(ingested_at)) DESC
  ) = 1
)
SELECT
  '${dataform.projectConfig.vars.tenant_id}' AS tenant_id,
  conversion_id,
  customer_id,
  email_hash,
  campaign_id,
  channel,
  conversion_type,
  DATE(event_ts) AS conversion_date,
  event_ts,
  revenue_raw,
  original_currency,
  ROUND(
    revenue_raw * CASE original_currency
      WHEN 'USD' THEN 1.0
      WHEN 'EUR' THEN 1.08
      WHEN 'GBP' THEN 1.27
      WHEN 'CAD' THEN 0.74
      ELSE 1.0
    END,
    2
  ) AS revenue_usd,
  ingested_at,
  CURRENT_TIMESTAMP() AS processed_at
FROM deduplicated
```

Create `dataform/definitions/gold/mart_cross_channel_performance.sqlx`:
```sql
config {
  type: "table",
  schema: "gold",
  name: "mart_cross_channel_performance",
  description: "Gold business-ready mart for cross-channel daily performance, pacing, CPA, and ROAS",
  bigquery: {
    partitionBy: "report_date",
    clusterBy: ["channel", "campaign_id"]
  },
  assertions: {
    uniqueKey: ["report_date", "campaign_id", "channel"],
    nonNull: ["tenant_id", "report_date", "campaign_id", "channel", "spend_usd"]
  }
}

WITH conversions_by_day AS (
  SELECT
    conversion_date AS report_date,
    campaign_id,
    channel,
    COUNT(DISTINCT conversion_id) AS conversions_count,
    ROUND(SUM(revenue_usd), 2) AS attributed_revenue_usd
  FROM ${ref("stg_conversions")}
  GROUP BY 1, 2, 3
)
SELECT
  s.tenant_id,
  s.report_date,
  s.campaign_id,
  s.campaign_name,
  s.channel,
  s.impressions,
  s.clicks,
  s.spend_usd,
  s.daily_budget_usd,
  COALESCE(c.conversions_count, 0) AS conversions_count,
  COALESCE(c.attributed_revenue_usd, 0.0) AS attributed_revenue_usd,
  ROUND(SAFE_DIVIDE(s.clicks, s.impressions), 4) AS ctr,
  ROUND(SAFE_DIVIDE(s.spend_usd, COALESCE(c.conversions_count, 0)), 2) AS cpa_usd,
  ROUND(SAFE_DIVIDE(COALESCE(c.attributed_revenue_usd, 0.0), s.spend_usd), 2) AS roas,
  ROUND(SAFE_DIVIDE(s.spend_usd, s.daily_budget_usd) * 100.0, 2) AS budget_pacing_pct,
  CURRENT_TIMESTAMP() AS refreshed_at
FROM ${ref("stg_ad_spend_daily")} s
LEFT JOIN conversions_by_day c
  ON s.report_date = c.report_date
  AND s.campaign_id = c.campaign_id
  AND s.channel = c.channel
```

Create `dataform/definitions/gold/mart_customer_attribution.sqlx`:
```sql
config {
  type: "table",
  schema: "gold",
  name: "mart_customer_attribution",
  description: "Gold privacy-safe customer attribution and LTV mart joining hashed CRM profiles with conversion touchpoints",
  assertions: {
    uniqueKey: ["customer_id"],
    nonNull: ["tenant_id", "customer_id", "email_hash", "loyalty_tier"]
  }
}

WITH customer_touchpoints AS (
  SELECT
    customer_id,
    COUNT(DISTINCT conversion_id) AS total_conversions,
    ROUND(SUM(revenue_usd), 2) AS lifetime_attributed_revenue_usd,
    ARRAY_AGG(channel ORDER BY event_ts ASC LIMIT 1)[OFFSET(0)] AS first_touch_channel,
    ARRAY_AGG(channel ORDER BY event_ts DESC LIMIT 1)[OFFSET(0)] AS last_touch_channel,
    MIN(event_ts) AS first_conversion_ts,
    MAX(event_ts) AS last_conversion_ts
  FROM ${ref("stg_conversions")}
  GROUP BY customer_id
)
SELECT
  crm.tenant_id,
  crm.customer_id,
  crm.email_hash,
  crm.phone_hash,
  crm.loyalty_tier,
  crm.country,
  crm.signup_ts,
  COALESCE(ct.total_conversions, 0) AS total_conversions,
  COALESCE(ct.lifetime_attributed_revenue_usd, 0.0) AS lifetime_attributed_revenue_usd,
  COALESCE(ct.first_touch_channel, 'UNATTRIBUTED') AS first_touch_channel,
  COALESCE(ct.last_touch_channel, 'UNATTRIBUTED') AS last_touch_channel,
  ct.first_conversion_ts,
  ct.last_conversion_ts,
  CURRENT_TIMESTAMP() AS refreshed_at
FROM ${ref("stg_crm_customers")} crm
LEFT JOIN customer_touchpoints ct
  ON crm.customer_id = ct.customer_id
```

Create `dataform/definitions/gold/share_cross_channel_performance_iceberg.sqlx`:
```sql
config {
  type: "operations",
  schema: "gold",
  name: "share_cross_channel_performance_iceberg",
  hasOutput: true,
  dependencies: ["mart_cross_channel_performance"],
  description: "BigLake Managed Apache Iceberg table stored in Parquet on GCS for cross-cloud lakehouse sharing"
}

CREATE TABLE IF NOT EXISTS ${self()}
(
  tenant_id STRING,
  report_date DATE,
  campaign_id STRING,
  campaign_name STRING,
  channel STRING,
  impressions INT64,
  clicks INT64,
  spend_usd FLOAT64,
  daily_budget_usd FLOAT64,
  conversions_count INT64,
  attributed_revenue_usd FLOAT64,
  ctr FLOAT64,
  cpa_usd FLOAT64,
  roas FLOAT64,
  budget_pacing_pct FLOAT64,
  refreshed_at TIMESTAMP
)
WITH CONNECTION `${dataform.projectConfig.defaultDatabase}.us-central1.lakehouse-connection`
OPTIONS (
  file_format = 'PARQUET',
  table_format = 'ICEBERG',
  storage_uri = 'gs://${dataform.projectConfig.vars.landing_bucket}/iceberg/cross_channel_performance'
);

DELETE FROM ${self()} WHERE TRUE;

INSERT INTO ${self()}
SELECT
  tenant_id,
  report_date,
  campaign_id,
  campaign_name,
  channel,
  impressions,
  clicks,
  spend_usd,
  daily_budget_usd,
  conversions_count,
  attributed_revenue_usd,
  ctr,
  cpa_usd,
  roas,
  budget_pacing_pct,
  refreshed_at
FROM ${ref("mart_cross_channel_performance")};
```

- [ ] **Step 4: Run `pytest` to verify all Dataform & Workflow tests pass**

Run: `pytest tests/test_workflows_and_dataform.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit Task 2**

```bash
git add dataform/ tests/test_workflows_and_dataform.py
git commit -m "feat(dataform): add single-repo Medallion SQLX models with PII hashing, assertions, and Gold Iceberg table"
```

---

### Task 3: Modular Terraform Configuration — Agency Admin, Tenant Factory & Feature-Flagged Enterprise Reference (`terraform/`)

**Files:**
- Create: `terraform/versions.tf`
- Create: `terraform/variables.tf`
- Create: `terraform/terraform.tfvars`
- Create: `terraform/main.tf`
- Create: `terraform/outputs.tf`
- Create: `terraform/modules/agency_admin/variables.tf`
- Create: `terraform/modules/agency_admin/main.tf`
- Create: `terraform/modules/agency_admin/outputs.tf`
- Create: `terraform/modules/tenant_factory/variables.tf`
- Create: `terraform/modules/tenant_factory/main.tf`
- Create: `terraform/modules/tenant_factory/outputs.tf`
- Create: `terraform/modules/enterprise_reference/variables.tf`
- Create: `terraform/modules/enterprise_reference/vpc_sc.tf`
- Create: `terraform/modules/enterprise_reference/cmek.tf`
- Create: `terraform/modules/enterprise_reference/dts_connectors.tf`
- Create: `terraform/modules/enterprise_reference/governance.tf`
- Create: `terraform/modules/enterprise_reference/monitoring.tf`
- Create: `terraform/modules/enterprise_reference/cicd_cloudbuild.tf`

**Interfaces:**
- Consumes: `workflows/parent_orchestrator.yaml` and `workflows/tenant_child_workflow.yaml` from Task 1.
- Produces: Validated Terraform modules ready for `terraform apply` across `agency-platform-123`, `advertiser-01`, and `advertiser-02`.

- [ ] **Step 1: Create root Terraform files (`versions.tf`, `variables.tf`, `terraform.tfvars`, `main.tf`, `outputs.tf`)**

Create `terraform/versions.tf`:
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.20.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.20.0"
    }
  }
}

provider "google" {
  region = var.region
}

provider "google-beta" {
  region = var.region
}
```

Create `terraform/variables.tf`:
```hcl
variable "admin_project_id" {
  description = "Centralized Agency Admin GCP project ID"
  type        = string
  default     = "agency-platform-123"
}

variable "region" {
  description = "Default GCP region for BigQuery, Dataform, Workflows, and GCS"
  type        = string
  default     = "us-central1"
}

variable "tenants" {
  description = "Map of advertiser tenants to provision via the Tenant Factory"
  type = map(object({
    tenant_id        = string
    project_id       = string
    tenant_name      = string
    industry         = string
    sla_tier         = string
    default_currency = string
    default_timezone = string
  }))
}

variable "enable_vpc_sc" {
  description = "Enable VPC Service Controls per-tenant perimeters (disabled in demo to prevent lockout)"
  type        = bool
  default     = false
}

variable "enable_cmek" {
  description = "Enable Cloud KMS Customer-Managed Encryption Keys per tenant"
  type        = bool
  default     = false
}

variable "enable_dts_connectors" {
  description = "Enable BigQuery Data Transfer Service (GMP) and 3P Ad API Cloud Run connector jobs"
  type        = bool
  default     = false
}

variable "enable_dataplex_governance" {
  description = "Enable Dataplex / Knowledge Catalog governance and DQ scans"
  type        = bool
  default     = false
}

variable "enable_monitoring_alerts" {
  description = "Enable Cloud Monitoring SLA alert policies and FinOps chargeback views"
  type        = bool
  default     = false
}

variable "enable_cloudbuild_cicd" {
  description = "Enable Cloud Build GitOps trigger for PR-driven tenant onboarding"
  type        = bool
  default     = false
}

variable "access_context_manager_policy_id" {
  description = "Optional Organization Access Context Manager Policy ID when enable_vpc_sc is true"
  type        = string
  default     = ""
}
```

Create `terraform/terraform.tfvars`:
```hcl
admin_project_id = "agency-platform-123"
region           = "us-central1"

tenants = {
  advertiser_01 = {
    tenant_id        = "advertiser_01"
    project_id       = "advertiser-01"
    tenant_name      = "Apex Apparel"
    industry         = "Retail & E-Commerce"
    sla_tier         = "TIER_1_DAILY_0600"
    default_currency = "USD"
    default_timezone = "America/New_York"
  }
  advertiser_02 = {
    tenant_id        = "advertiser_02"
    project_id       = "advertiser-02"
    tenant_name      = "Nova FinTech"
    industry         = "Financial Services"
    sla_tier         = "TIER_1_DAILY_0600"
    default_currency = "USD"
    default_timezone = "America/New_York"
  }
}

enable_vpc_sc              = false
enable_cmek                = false
enable_dts_connectors      = false
enable_dataplex_governance = false
enable_monitoring_alerts   = false
enable_cloudbuild_cicd     = false
```

Create `terraform/main.tf`:
```hcl
module "agency_admin" {
  source = "./modules/agency_admin"

  admin_project_id         = var.admin_project_id
  region                   = var.region
  parent_workflow_yaml     = file("${path.module}/../workflows/parent_orchestrator.yaml")
  child_workflow_yaml      = file("${path.module}/../workflows/tenant_child_workflow.yaml")
}

module "tenant_factory" {
  source   = "./modules/tenant_factory"
  for_each = var.tenants

  admin_project_id              = var.admin_project_id
  region                        = var.region
  tenant_id                     = each.value.tenant_id
  project_id                    = each.value.project_id
  tenant_name                   = each.value.tenant_name
  industry                      = each.value.industry
  sla_tier                      = each.value.sla_tier
  orchestrator_sa_email         = module.agency_admin.orchestrator_sa_email
  admin_dataform_service_agent  = module.agency_admin.dataform_service_agent_email
}

module "enterprise_reference" {
  source = "./modules/enterprise_reference"

  admin_project_id                 = var.admin_project_id
  region                           = var.region
  tenants                          = var.tenants
  enable_vpc_sc                    = var.enable_vpc_sc
  enable_cmek                      = var.enable_cmek
  enable_dts_connectors            = var.enable_dts_connectors
  enable_dataplex_governance       = var.enable_dataplex_governance
  enable_monitoring_alerts         = var.enable_monitoring_alerts
  enable_cloudbuild_cicd           = var.enable_cloudbuild_cicd
  access_context_manager_policy_id = var.access_context_manager_policy_id
}
```

Create `terraform/outputs.tf`:
```hcl
output "agency_admin_summary" {
  description = "Summary of Agency Admin control plane resources"
  value = {
    admin_project_id             = var.admin_project_id
    platform_admin_dataset       = module.agency_admin.platform_admin_dataset_id
    dataform_repository_name     = module.agency_admin.dataform_repository_name
    orchestrator_sa_email        = module.agency_admin.orchestrator_sa_email
    dataform_service_agent_email = module.agency_admin.dataform_service_agent_email
    parent_workflow_name         = module.agency_admin.parent_workflow_name
    child_workflow_name          = module.agency_admin.child_workflow_name
  }
}

output "tenants_summary" {
  description = "Per-tenant isolated resources provisioned by Tenant Factory"
  value = {
    for k, m in module.tenant_factory : k => {
      project_id              = m.project_id
      landing_bucket          = m.landing_bucket_name
      tenant_dataform_sa      = m.tenant_dataform_sa_email
      biglake_connection_id   = m.biglake_connection_id
      biglake_service_account = m.biglake_connection_sa
      datasets                = m.dataset_ids
      analytics_hub_listing   = m.analytics_hub_listing_id
    }
  }
}
```

- [ ] **Step 2: Create `terraform/modules/agency_admin/` (`variables.tf`, `main.tf`, `outputs.tf`)**

Create `terraform/modules/agency_admin/variables.tf`:
```hcl
variable "admin_project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "parent_workflow_yaml" {
  type = string
}

variable "child_workflow_yaml" {
  type = string
}
```

Create `terraform/modules/agency_admin/main.tf`:
```hcl
locals {
  required_apis = [
    "bigquery.googleapis.com",
    "dataform.googleapis.com",
    "workflows.googleapis.com",
    "workflowexecutions.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ]
}

resource "google_project_service" "admin_apis" {
  for_each           = toset(local.required_apis)
  project            = var.admin_project_id
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "admin" {
  project_id = var.admin_project_id
  depends_on = [google_project_service.admin_apis]
}

resource "google_project_service_identity" "dataform_agent" {
  provider   = google-beta
  project    = var.admin_project_id
  service    = "dataform.googleapis.com"
  depends_on = [google_project_service.admin_apis]
}

resource "google_service_account" "orchestrator" {
  project      = var.admin_project_id
  account_id   = "sa-orchestrator"
  display_name = "Agency Platform Cloud Workflows & Scheduler Orchestrator"
  depends_on   = [google_project_service.admin_apis]
}

resource "google_project_iam_member" "orchestrator_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/dataform.admin",
    "roles/workflows.invoker",
    "roles/logging.logWriter"
  ])
  project = var.admin_project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_bigquery_dataset" "platform_admin" {
  project                    = var.admin_project_id
  dataset_id                 = "platform_admin"
  friendly_name              = "Agency Platform Admin Metadata & Run Logs"
  description                = "Centralized tenant registry, source registry, schedules, and workflow run logs"
  location                   = var.region
  delete_contents_on_destroy = true

  labels = {
    env       = "demo"
    component = "control-plane"
  }
  depends_on = [google_project_service.admin_apis]
}

resource "google_bigquery_table" "tenants" {
  project             = var.admin_project_id
  dataset_id          = google_bigquery_dataset.platform_admin.dataset_id
  table_id            = "tenants"
  deletion_protection = false

  schema = jsonencode([
    { name = "tenant_id", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "REQUIRED" },
    { name = "tenant_name", type = "STRING", mode = "REQUIRED" },
    { name = "industry", type = "STRING", mode = "NULLABLE" },
    { name = "sla_tier", type = "STRING", mode = "REQUIRED" },
    { name = "service_account_email", type = "STRING", mode = "REQUIRED" },
    { name = "landing_bucket", type = "STRING", mode = "REQUIRED" },
    { name = "biglake_connection_id", type = "STRING", mode = "REQUIRED" },
    { name = "default_currency", type = "STRING", mode = "REQUIRED" },
    { name = "default_timezone", type = "STRING", mode = "REQUIRED" },
    { name = "is_active", type = "BOOL", mode = "REQUIRED" },
    { name = "onboarded_at", type = "TIMESTAMP", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "sources" {
  project             = var.admin_project_id
  dataset_id          = google_bigquery_dataset.platform_admin.dataset_id
  table_id            = "sources"
  deletion_protection = false

  schema = jsonencode([
    { name = "tenant_id", type = "STRING", mode = "REQUIRED" },
    { name = "source_name", type = "STRING", mode = "REQUIRED" },
    { name = "source_type", type = "STRING", mode = "REQUIRED" },
    { name = "gcs_uri", type = "STRING", mode = "REQUIRED" },
    { name = "target_bronze_table", type = "STRING", mode = "REQUIRED" },
    { name = "is_enabled", type = "BOOL", mode = "REQUIRED" }
  ])
}

resource "google_bigquery_table" "schedules" {
  project             = var.admin_project_id
  dataset_id          = google_bigquery_dataset.platform_admin.dataset_id
  table_id            = "schedules"
  deletion_protection = false

  schema = jsonencode([
    { name = "schedule_id", type = "STRING", mode = "REQUIRED" },
    { name = "sla_tier", type = "STRING", mode = "REQUIRED" },
    { name = "cron_schedule", type = "STRING", mode = "REQUIRED" },
    { name = "description", type = "STRING", mode = "NULLABLE" }
  ])
}

resource "google_bigquery_table" "run_log" {
  project             = var.admin_project_id
  dataset_id          = google_bigquery_dataset.platform_admin.dataset_id
  table_id            = "run_log"
  deletion_protection = false

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "parent_execution_id", type = "STRING", mode = "REQUIRED" },
    { name = "tenant_id", type = "STRING", mode = "REQUIRED" },
    { name = "project_id", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "dataform_compilation_id", type = "STRING", mode = "NULLABLE" },
    { name = "dataform_invocation_id", type = "STRING", mode = "NULLABLE" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "completed_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "notes", type = "STRING", mode = "NULLABLE" }
  ])
}

resource "google_dataform_repository" "medallion" {
  provider     = google-beta
  project      = var.admin_project_id
  region       = var.region
  name         = "medallion-pipeline"
  display_name = "Multi-Tenant Medallion SQLX Pipeline"

  labels = {
    env       = "demo"
    component = "medallion-dataform"
  }
  depends_on = [google_project_service_identity.dataform_agent]
}

resource "google_workflows_workflow" "tenant_child" {
  project         = var.admin_project_id
  region          = var.region
  name            = "medallion-tenant-child-workflow"
  description     = "Per-tenant child workflow: compiles Dataform with overrides and runs as sa-dataform@tenant"
  service_account = google_service_account.orchestrator.id
  source_contents = var.child_workflow_yaml
  depends_on      = [google_project_iam_member.orchestrator_roles]
}

resource "google_workflows_workflow" "parent_orchestrator" {
  project         = var.admin_project_id
  region          = var.region
  name            = "medallion-parent-orchestrator"
  description     = "Parent fan-out workflow: reads active tenants from platform_admin.tenants and runs child workflows in parallel"
  service_account = google_service_account.orchestrator.id
  source_contents = var.parent_workflow_yaml
  depends_on      = [google_workflows_workflow.tenant_child]
}

resource "google_cloud_scheduler_job" "daily_medallion_trigger" {
  project     = var.admin_project_id
  region      = var.region
  name        = "medallion-daily-schedule"
  description = "Triggers medallion-parent-orchestrator for TIER_1_DAILY_0600 tenants"
  schedule    = "0 6 * * *"
  time_zone   = "America/New_York"
  paused      = false

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.admin_project_id}/locations/${var.region}/workflows/${google_workflows_workflow.parent_orchestrator.name}/executions"
    body        = base64encode(jsonencode({ argument = "{}" }))
    oauth_token {
      service_account_email = google_service_account.orchestrator.email
    }
  }

  depends_on = [google_project_service.admin_apis]
}
```

Create `terraform/modules/agency_admin/outputs.tf`:
```hcl
output "platform_admin_dataset_id" {
  value = google_bigquery_dataset.platform_admin.dataset_id
}

output "dataform_repository_name" {
  value = google_dataform_repository.medallion.name
}

output "orchestrator_sa_email" {
  value = google_service_account.orchestrator.email
}

output "dataform_service_agent_email" {
  value = "service-${data.google_project.admin.number}@gcp-sa-dataform.iam.gserviceaccount.com"
}

output "parent_workflow_name" {
  value = google_workflows_workflow.parent_orchestrator.name
}

output "child_workflow_name" {
  value = google_workflows_workflow.tenant_child.name
}
```

- [ ] **Step 3: Create `terraform/modules/tenant_factory/` (`variables.tf`, `main.tf`, `outputs.tf`)**

Create `terraform/modules/tenant_factory/variables.tf`:
```hcl
variable "admin_project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "project_id" {
  type = string
}

variable "tenant_name" {
  type = string
}

variable "industry" {
  type = string
}

variable "sla_tier" {
  type = string
}

variable "orchestrator_sa_email" {
  type = string
}

variable "admin_dataform_service_agent" {
  type = string
}
```

Create `terraform/modules/tenant_factory/main.tf`:
```hcl
locals {
  tenant_apis = [
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "analyticshub.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "dataform.googleapis.com"
  ]
  common_labels = {
    env       = "demo"
    tenant_id = var.tenant_id
    project   = var.project_id
    sla_tier  = lower(var.sla_tier)
  }
}

resource "google_project_service" "tenant_apis" {
  for_each           = toset(local.tenant_apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "tenant_dataform" {
  project      = var.project_id
  account_id   = "sa-dataform"
  display_name = "Isolated Dataform Execution SA (${var.tenant_name})"
  description  = "Executes Medallion Bronze->Silver->Gold transformations strictly inside ${var.project_id}"
  depends_on   = [google_project_service.tenant_apis]
}

# Least-privilege IAM strictly inside the tenant's own project
resource "google_project_iam_member" "tenant_sa_local_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/bigquery.connectionUser",
    "roles/bigquery.connectionAdmin",
    "roles/storage.objectAdmin"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.tenant_dataform.email}"
}

# Allow central Agency Admin Dataform Service Agent to execute as this tenant's SA
resource "google_service_account_iam_member" "admin_dataform_token_creator" {
  service_account_id = google_service_account.tenant_dataform.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${var.admin_dataform_service_agent}"
}

resource "google_service_account_iam_member" "admin_dataform_sa_user" {
  service_account_id = google_service_account.tenant_dataform.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.admin_dataform_service_agent}"
}

# Allow Agency Admin Orchestrator SA to specify this tenant SA in workflowInvocations.create
resource "google_service_account_iam_member" "orchestrator_sa_user" {
  service_account_id = google_service_account.tenant_dataform.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.orchestrator_sa_email}"
}

resource "google_storage_bucket" "landing" {
  project                     = var.project_id
  name                        = "${var.project_id}-landing"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  labels                      = local.common_labels
  depends_on                  = [google_project_service.tenant_apis]
}

resource "google_bigquery_connection" "lakehouse" {
  project       = var.project_id
  location      = var.region
  connection_id = "lakehouse-connection"
  friendly_name = "BigLake & Iceberg Connection (${var.tenant_name})"
  description   = "Cloud Resource connection for Bronze external tables and Gold Apache Iceberg tables"
  cloud_resource {}
  depends_on = [google_project_service.tenant_apis]
}

resource "google_storage_bucket_iam_member" "biglake_bucket_access" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_bigquery_connection.lakehouse.cloud_resource[0].service_account_id}"
}

resource "google_storage_bucket_iam_member" "tenant_sa_bucket_access" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.tenant_dataform.email}"
}

resource "google_bigquery_dataset" "medallion" {
  for_each = {
    bronze = "Bronze Raw Layer - External tables over GCS landing files"
    silver = "Silver Cleansed & Conformed Layer - Deduplicated, FX normalized, PII hashed"
    gold   = "Gold Business-Ready Marts & Apache Iceberg Sharing Layer"
  }
  project                    = var.project_id
  dataset_id                 = each.key
  friendly_name              = "${upper(each.key)} (${var.tenant_name})"
  description                = each.value
  location                   = var.region
  delete_contents_on_destroy = true
  labels                     = merge(local.common_labels, { layer = each.key })
  depends_on                 = [google_project_service.tenant_apis]
}

resource "google_bigquery_analytics_hub_data_exchange" "tenant_exchange" {
  project          = var.project_id
  location         = var.region
  data_exchange_id = "${var.tenant_id}_exchange"
  display_name     = "${var.tenant_name} Gold Data Exchange"
  description      = "Zero-copy BigQuery Sharing exchange for ${var.tenant_name}"
  depends_on       = [google_project_service.tenant_apis]
}

resource "google_bigquery_analytics_hub_listing" "gold_listing" {
  project          = var.project_id
  location         = var.region
  data_exchange_id = google_bigquery_analytics_hub_data_exchange.tenant_exchange.data_exchange_id
  listing_id       = "${var.tenant_id}_gold_listing"
  display_name     = "${var.tenant_name} Gold Medallion Marts & Iceberg Share"
  description      = "Zero-copy shared Gold dataset for ${var.tenant_name} subscriber orgs"

  bigquery_dataset {
    dataset = google_bigquery_dataset.medallion["gold"].id
  }
}
```

Create `terraform/modules/tenant_factory/outputs.tf`:
```hcl
output "project_id" {
  value = var.project_id
}

output "landing_bucket_name" {
  value = google_storage_bucket.landing.name
}

output "tenant_dataform_sa_email" {
  value = google_service_account.tenant_dataform.email
}

output "biglake_connection_id" {
  value = "${var.project_id}.${var.region}.${google_bigquery_connection.lakehouse.connection_id}"
}

output "biglake_connection_sa" {
  value = google_bigquery_connection.lakehouse.cloud_resource[0].service_account_id
}

output "dataset_ids" {
  value = [for k, d in google_bigquery_dataset.medallion : d.dataset_id]
}

output "analytics_hub_listing_id" {
  value = google_bigquery_analytics_hub_listing.gold_listing.id
}
```

- [ ] **Step 4: Create `terraform/modules/enterprise_reference/` (`variables.tf`, `vpc_sc.tf`, `cmek.tf`, `dts_connectors.tf`, `governance.tf`, `monitoring.tf`, `cicd_cloudbuild.tf`)**

Create `terraform/modules/enterprise_reference/variables.tf`:
```hcl
variable "admin_project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "tenants" {
  type = map(object({
    tenant_id        = string
    project_id       = string
    tenant_name      = string
    industry         = string
    sla_tier         = string
    default_currency = string
    default_timezone = string
  }))
}

variable "enable_vpc_sc" {
  type    = bool
  default = false
}

variable "enable_cmek" {
  type    = bool
  default = false
}

variable "enable_dts_connectors" {
  type    = bool
  default = false
}

variable "enable_dataplex_governance" {
  type    = bool
  default = false
}

variable "enable_monitoring_alerts" {
  type    = bool
  default = false
}

variable "enable_cloudbuild_cicd" {
  type    = bool
  default = false
}

variable "access_context_manager_policy_id" {
  type    = string
  default = ""
}
```

Create `terraform/modules/enterprise_reference/vpc_sc.tf`:
```hcl
# Reference Architecture Box C: Per-Tenant VPC Service Controls Perimeter & Admin Bridge
# Controlled by var.enable_vpc_sc (default = false in demo environment)

resource "google_access_context_manager_service_perimeter" "tenant_perimeter" {
  for_each       = var.enable_vpc_sc && var.access_context_manager_policy_id != "" ? var.tenants : {}
  parent         = "accessPolicies/${var.access_context_manager_policy_id}"
  name           = "accessPolicies/${var.access_context_manager_policy_id}/servicePerimeters/${each.value.tenant_id}_perimeter"
  title          = "${each.value.tenant_name} Isolated VPC-SC Perimeter"
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  status {
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "dataform.googleapis.com",
      "secretmanager.googleapis.com"
    ]

    ingress_policies {
      ingress_from {
        identities = [
          "serviceAccount:sa-orchestrator@${var.admin_project_id}.iam.gserviceaccount.com"
        ]
        sources {
          resource = "projects/${var.admin_project_id}"
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "bigquery.googleapis.com"
          method_selectors {
            method = "*"
          }
        }
      }
    }
  }
}
```

Create `terraform/modules/enterprise_reference/cmek.tf`:
```hcl
# Reference Architecture Box C: Per-Tenant Cloud KMS CMEK Encryption
# Controlled by var.enable_cmek (default = false in demo environment)

resource "google_kms_key_ring" "tenant_keyring" {
  for_each = var.enable_cmek ? var.tenants : {}
  project  = each.value.project_id
  name     = "${each.value.tenant_id}-cmek-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "tenant_bq_gcs_key" {
  for_each        = var.enable_cmek ? var.tenants : {}
  name            = "${each.value.tenant_id}-data-key"
  key_ring        = google_kms_key_ring.tenant_keyring[each.key].id
  rotation_period = "7776000s" # 90 days
}
```

Create `terraform/modules/enterprise_reference/dts_connectors.tf`:
```hcl
# Reference Architecture Ingestion Plane: BigQuery Data Transfer Service (GMP) & Cloud Run 3P Ad Connectors
# Controlled by var.enable_dts_connectors (default = false in demo environment)

resource "google_bigquery_data_transfer_config" "google_ads_transfer" {
  for_each               = var.enable_dts_connectors ? var.tenants : {}
  project                = each.value.project_id
  location               = var.region
  display_name           = "${each.value.tenant_name} - Google Ads & GMP Daily Transfer"
  data_source_id         = "google_ads"
  destination_dataset_id = "bronze"
  schedule               = "every 24 hours"

  params = {
    customer_id = "000-000-0000"
  }
}

resource "google_secret_manager_secret" "third_party_ad_api_key" {
  for_each  = var.enable_dts_connectors ? var.tenants : {}
  project   = each.value.project_id
  secret_id = "${each.value.tenant_id}-3p-ads-api-credentials"

  replication {
    auto {}
  }
}
```

Create `terraform/modules/enterprise_reference/governance.tf`:
```hcl
# Reference Architecture Governance Plane: Dataplex / Knowledge Catalog Lake & Asset Discovery
# Controlled by var.enable_dataplex_governance (default = false in demo environment)

resource "google_dataplex_lake" "agency_governance_lake" {
  count        = var.enable_dataplex_governance ? 1 : 0
  project      = var.admin_project_id
  location     = var.region
  name         = "agency-advertisers-governance-lake"
  display_name = "Agency Cross-Tenant Knowledge Catalog & Lineage Lake"
}

resource "google_dataplex_zone" "tenant_curated_zone" {
  for_each     = var.enable_dataplex_governance ? var.tenants : {}
  project      = var.admin_project_id
  location     = var.region
  lake         = google_dataplex_lake.agency_governance_lake[0].name
  name         = "${replace(each.value.tenant_id, "_", "-")}-gold-zone"
  display_name = "${each.value.tenant_name} Gold Curated Zone"
  type         = "CURATED"

  discovery_spec {
    enabled = true
  }

  resource_spec {
    location_type = "SINGLE_REGION"
  }
}
```

Create `terraform/modules/enterprise_reference/monitoring.tf`:
```hcl
# Reference Architecture Ops & FinOps Plane: Cloud Monitoring SLA Alerts & Per-Tenant Cost Views
# Controlled by var.enable_monitoring_alerts (default = false in demo environment)

resource "google_monitoring_alert_policy" "workflow_failure_sla_alert" {
  count        = var.enable_monitoring_alerts ? 1 : 0
  project      = var.admin_project_id
  display_name = "Agency Medallion Pipeline Tenant Run Failure Alert"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Workflow Execution Failed"
    condition_threshold {
      filter          = "resource.type = \"workflows.googleapis.com/Workflow\" AND metric.type = \"workflows.googleapis.com/finished_execution_count\" AND metric.labels.status = \"FAILED\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}
```

Create `terraform/modules/enterprise_reference/cicd_cloudbuild.tf`:
```hcl
# Reference Architecture Box B: Cloud Build Tenant Factory GitOps Trigger ("Onboard Advertiser N+1")
# Controlled by var.enable_cloudbuild_cicd (default = false in demo environment)

resource "google_cloudbuild_trigger" "tenant_factory_gitops" {
  count       = var.enable_cloudbuild_cicd ? 1 : 0
  project     = var.admin_project_id
  location    = var.region
  name        = "tenant-factory-onboard-advertiser"
  description = "Provisions new advertiser project resources and registers tenant config on PR merge to main"

  included_files = [
    "terraform/**",
    "dataform/**",
    "workflows/**"
  ]

  build {
    step {
      name = "hashicorp/terraform:1.6"
      args = ["init"]
      dir  = "terraform"
    }
    step {
      name = "hashicorp/terraform:1.6"
      args = ["apply", "-auto-approve"]
      dir  = "terraform"
    }
  }
}
```

- [ ] **Step 5: Run `terraform init` and `terraform validate` to verify HCL syntax and module wiring**

Run: `terraform -chdir=terraform init -backend=false && terraform -chdir=terraform validate`
Expected: `Success! The configuration is valid.`

- [ ] **Step 6: Commit Task 3**

```bash
git add terraform/
git commit -m "feat(terraform): add agency_admin, tenant_factory, and feature-flagged enterprise_reference modules"
```

---

### Task 4: Synthetic Media & 1P Data Generator, Dataform Workspace Seeder & Platform Verification Scripts (`scripts/`)

**Files:**
- Create: `scripts/generate_and_load_synthetic_data.py`
- Create: `scripts/seed_dataform_workspace.py`
- Create: `scripts/verify_platform.py`
- Create: `tests/test_synthetic_data.py`

**Interfaces:**
- Consumes: Provisioned GCP projects (`agency-platform-123`, `advertiser-01`, `advertiser-02`), buckets (`gs://<project>-landing`), BigLake connection (`<project>.us-central1.lakehouse-connection`), and `dataform/` SQLX files.
- Produces:
  - `generate_tenant_datasets(tenant_id: str) -> dict[str, list[dict]]` (tested offline by `tests/test_synthetic_data.py` and uploaded online to GCS + Bronze external tables + `platform_admin` registry)
  - `seed_dataform_workspace.py` (pushes all 10 `dataform/` files into the Dataform workspace in `agency-platform-123` and runs a test compilation)
  - `verify_platform.py` (triggers `medallion-parent-orchestrator` and validates all acceptance criteria end-to-end)

- [ ] **Step 1: Write the failing unit tests in `tests/test_synthetic_data.py`**

Create `tests/test_synthetic_data.py`:
```python
from scripts.generate_and_load_synthetic_data import generate_tenant_datasets, TENANT_CONFIGS


def test_tenant_configs_cover_both_advertisers():
    project_ids = [t["project_id"] for t in TENANT_CONFIGS]
    assert project_ids == ["advertiser-01", "advertiser-02"]


def test_generate_tenant_datasets_has_duplicates_currencies_and_pii():
    for cfg in TENANT_CONFIGS:
        data = generate_tenant_datasets(cfg["tenant_id"])
        assert set(data.keys()) == {
            "raw_ad_spend_daily",
            "raw_crm_customers",
            "raw_conversions",
        }

        spend_rows = data["raw_ad_spend_daily"]
        assert len(spend_rows) >= 20
        currencies = {r["currency"] for r in spend_rows}
        assert len(currencies) >= 2, "Must contain multiple currencies to test FX normalization"
        keys = [(r["report_date"], r["campaign_id"], r["channel"].upper().replace(" ", "_")) for r in spend_rows]
        assert len(keys) > len(set(keys)), "Must include intentional duplicate rows for Silver deduplication"

        crm_rows = data["raw_crm_customers"]
        assert len(crm_rows) >= 15
        assert all("@" in r["email"] for r in crm_rows), "Raw CRM must include cleartext email PII"
        cust_ids = [r["customer_id"] for r in crm_rows]
        assert len(cust_ids) > len(set(cust_ids)), "Must include duplicate customer update snapshots"

        conv_rows = data["raw_conversions"]
        assert len(conv_rows) >= 20
        conv_ids = [r["conversion_id"] for r in conv_rows]
        assert len(conv_ids) > len(set(conv_ids)), "Must include duplicate conversion retry rows"
```

- [ ] **Step 2: Run `pytest` to verify `tests/test_synthetic_data.py` fails**

Run: `pytest tests/test_synthetic_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_and_load_synthetic_data'`

- [ ] **Step 3: Create `scripts/generate_and_load_synthetic_data.py`, `scripts/seed_dataform_workspace.py`, and `scripts/verify_platform.py`**

Create `scripts/generate_and_load_synthetic_data.py`:
```python
#!/usr/bin/env python3
"""Generates synthetic Media & 1P datasets for advertiser-01 and advertiser-02,
uploads CSVs to GCS landing buckets, creates the 3 Bronze BigLake external tables
per tenant, and seeds agency-platform-123.platform_admin control tables.
"""

import csv
import io
import random
from datetime import date, timedelta
from google.cloud import bigquery, storage

ADMIN_PROJECT_ID = "agency-platform-123"
REGION = "us-central1"

TENANT_CONFIGS = [
    {
        "tenant_id": "advertiser_01",
        "project_id": "advertiser-01",
        "tenant_name": "Apex Apparel",
        "industry": "Retail & E-Commerce",
        "sla_tier": "TIER_1_DAILY_0600",
        "service_account_email": "sa-dataform@advertiser-01.iam.gserviceaccount.com",
        "landing_bucket": "advertiser-01-landing",
        "biglake_connection_id": "advertiser-01.us-central1.lakehouse-connection",
        "default_currency": "USD",
        "default_timezone": "America/New_York",
        "campaigns": [
            ("CMP-A01-101", "Apex Spring Footwear Launch", "Google Ads", "USD", 1200.0),
            ("CMP-A01-102", "Apex Athleisure Retargeting", "META", "EUR", 950.0),
            ("CMP-A01-103", "Apex GenZ Streetwear Video", "TikTok", "CAD", 800.0),
            ("CMP-A01-104", "Apex Connected TV Brand Halo", "DV360", "USD", 1500.0),
        ],
    },
    {
        "tenant_id": "advertiser_02",
        "project_id": "advertiser-02",
        "tenant_name": "Nova FinTech",
        "industry": "Financial Services",
        "sla_tier": "TIER_1_DAILY_0600",
        "service_account_email": "sa-dataform@advertiser-02.iam.gserviceaccount.com",
        "landing_bucket": "advertiser-02-landing",
        "biglake_connection_id": "advertiser-02.us-central1.lakehouse-connection",
        "default_currency": "USD",
        "default_timezone": "America/New_York",
        "campaigns": [
            ("CMP-A02-201", "Nova High-Yield Savings Search", "google_ads", "USD", 2200.0),
            ("CMP-A02-202", "Nova Wealth Management Acquisition", "DV360", "GBP", 1800.0),
            ("CMP-A02-203", "Nova Mobile Card App Install", "META", "USD", 1400.0),
            ("CMP-A02-204", "Nova Millennial Investing Shorts", "TikTok", "EUR", 900.0),
        ],
    },
]


def generate_tenant_datasets(tenant_id: str) -> dict[str, list[dict]]:
    rng = random.Random(42 if tenant_id == "advertiser_01" else 99)
    cfg = next(t for t in TENANT_CONFIGS if t["tenant_id"] == tenant_id)
    base_date = date(2026, 10, 25)

    # 1. raw_ad_spend_daily (7 days x 4 campaigns = 28 rows + 4 duplicate late-arriving corrections = 32 rows)
    spend_rows = []
    for day_offset in range(7):
        rep_date = (base_date + timedelta(days=day_offset)).isoformat()
        for cmp_id, cmp_name, channel, currency, budget_usd in cfg["campaigns"]:
            impressions = rng.randint(15000, 95000)
            clicks = rng.randint(300, int(impressions * 0.06))
            spend_raw = round(budget_usd * rng.uniform(0.75, 1.12), 2)
            spend_rows.append(
                {
                    "feed_id": f"FD-{tenant_id[-2:]}-{day_offset:02d}-{cmp_id}",
                    "report_date": rep_date,
                    "campaign_id": cmp_id,
                    "campaign_name": cmp_name,
                    "channel": channel,
                    "impressions": impressions,
                    "clicks": clicks,
                    "spend_raw": spend_raw,
                    "currency": currency,
                    "daily_budget_usd": budget_usd,
                    "ingested_at": f"{rep_date}T04:00:00Z",
                }
            )
            # Add intentional duplicate row on day 0 across all campaigns with later ingested_at
            if day_offset == 0:
                spend_rows.append(
                    {
                        "feed_id": f"FD-{tenant_id[-2:]}-{day_offset:02d}-{cmp_id}-RETRY",
                        "report_date": rep_date,
                        "campaign_id": cmp_id,
                        "campaign_name": cmp_name,
                        "channel": channel,
                        "impressions": impressions + 250,
                        "clicks": clicks + 12,
                        "spend_raw": round(spend_raw + 18.50, 2),
                        "currency": currency,
                        "daily_budget_usd": budget_usd,
                        "ingested_at": f"{rep_date}T06:30:00Z",
                    }
                )

    # 2. raw_crm_customers (20 unique customers + 3 duplicate update rows = 23 rows)
    tiers = ["BRONZE", "SILVER", "GOLD", "PLATINUM"]
    countries = ["US", "CA", "GB", "DE"]
    crm_rows = []
    for idx in range(1, 21):
        cust_id = f"CUST-{tenant_id[-2:]}-{idx:03d}"
        email = f"customer{idx:03d}.{tenant_id}@example-client.com"
        phone = f"+1-555-01{idx:02d}-{rng.randint(1000, 9999)}"
        crm_rows.append(
            {
                "customer_id": cust_id,
                "email": email,
                "phone": phone,
                "first_name": f"First{idx}",
                "last_name": f"Last{idx}",
                "loyalty_tier": tiers[idx % len(tiers)],
                "country": countries[idx % len(countries)],
                "signup_ts": "2026-09-15T10:00:00Z",
                "updated_at": "2026-10-20T12:00:00Z",
            }
        )
        if idx <= 3:
            # Later snapshot upgrading loyalty tier to PLATINUM
            crm_rows.append(
                {
                    "customer_id": cust_id,
                    "email": email.upper(),  # mixed case to test normalization prior to hashing
                    "phone": phone,
                    "first_name": f"First{idx}",
                    "last_name": f"Last{idx}",
                    "loyalty_tier": "PLATINUM",
                    "country": countries[idx % len(countries)],
                    "signup_ts": "2026-09-15T10:00:00Z",
                    "updated_at": "2026-10-28T18:30:00Z",
                }
            )

    # 3. raw_conversions (35 unique conversions + 4 duplicate retries = 39 rows)
    conv_types = ["ONLINE_PURCHASE", "OFFLINE_STORE_POS", "APP_SUBSCRIPTION"]
    conv_rows = []
    for c_idx in range(1, 36):
        conv_id = f"CONV-{tenant_id[-2:]}-{c_idx:04d}"
        cust_num = ((c_idx - 1) % 20) + 1
        cust_id = f"CUST-{tenant_id[-2:]}-{cust_num:03d}"
        email = f"customer{cust_num:03d}.{tenant_id}@example-client.com"
        cmp_id, _, channel, currency, _ = cfg["campaigns"][c_idx % len(cfg["campaigns"])]
        day_offset = c_idx % 7
        ev_date = (base_date + timedelta(days=day_offset)).isoformat()
        rev_raw = round(rng.uniform(45.0, 480.0), 2)
        conv_rows.append(
            {
                "conversion_id": conv_id,
                "customer_id": cust_id,
                "email": email,
                "campaign_id": cmp_id,
                "channel": channel,
                "conversion_type": conv_types[c_idx % len(conv_types)],
                "revenue_raw": rev_raw,
                "currency": currency,
                "event_ts": f"{ev_date}T14:{c_idx % 60:02d}:00Z",
                "ingested_at": f"{ev_date}T23:00:00Z",
            }
        )
        if c_idx <= 4:
            conv_rows.append(
                {
                    "conversion_id": conv_id,
                    "customer_id": cust_id,
                    "email": email,
                    "campaign_id": cmp_id,
                    "channel": channel,
                    "conversion_type": conv_types[c_idx % len(conv_types)],
                    "revenue_raw": round(rev_raw + 10.0, 2),
                    "currency": currency,
                    "event_ts": f"{ev_date}T14:{c_idx % 60:02d}:00Z",
                    "ingested_at": f"{ev_date}T23:45:00Z",
                }
            )

    return {
        "raw_ad_spend_daily": spend_rows,
        "raw_crm_customers": crm_rows,
        "raw_conversions": conv_rows,
    }


def rows_to_csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def upload_and_create_bronze_tables(cfg: dict, datasets: dict[str, list[dict]]) -> None:
    project_id = cfg["project_id"]
    bucket_name = cfg["landing_bucket"]
    conn_id = cfg["biglake_connection_id"]

    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)

    for table_name, rows in datasets.items():
        blob_path = f"raw/{table_name}.csv"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(rows_to_csv_bytes(rows), content_type="text/csv")
        print(f"[{project_id}] Uploaded {len(rows)} rows to gs://{bucket_name}/{blob_path}")

    bq_client = bigquery.Client(project=project_id, location=REGION)

    ddls = [
        f"""
        CREATE OR REPLACE EXTERNAL TABLE `{project_id}.bronze.raw_ad_spend_daily`
        (
          feed_id STRING,
          report_date STRING,
          campaign_id STRING,
          campaign_name STRING,
          channel STRING,
          impressions INT64,
          clicks INT64,
          spend_raw FLOAT64,
          currency STRING,
          daily_budget_usd FLOAT64,
          ingested_at STRING
        )
        WITH CONNECTION `{conn_id}`
        OPTIONS (
          format = 'CSV',
          uris = ['gs://{bucket_name}/raw/raw_ad_spend_daily.csv'],
          skip_leading_rows = 1
        )
        """,
        f"""
        CREATE OR REPLACE EXTERNAL TABLE `{project_id}.bronze.raw_crm_customers`
        (
          customer_id STRING,
          email STRING,
          phone STRING,
          first_name STRING,
          last_name STRING,
          loyalty_tier STRING,
          country STRING,
          signup_ts STRING,
          updated_at STRING
        )
        WITH CONNECTION `{conn_id}`
        OPTIONS (
          format = 'CSV',
          uris = ['gs://{bucket_name}/raw/raw_crm_customers.csv'],
          skip_leading_rows = 1
        )
        """,
        f"""
        CREATE OR REPLACE EXTERNAL TABLE `{project_id}.bronze.raw_conversions`
        (
          conversion_id STRING,
          customer_id STRING,
          email STRING,
          campaign_id STRING,
          channel STRING,
          conversion_type STRING,
          revenue_raw FLOAT64,
          currency STRING,
          event_ts STRING,
          ingested_at STRING
        )
        WITH CONNECTION `{conn_id}`
        OPTIONS (
          format = 'CSV',
          uris = ['gs://{bucket_name}/raw/raw_conversions.csv'],
          skip_leading_rows = 1
        )
        """,
    ]

    for ddl in ddls:
        bq_client.query(ddl).result()
    print(f"[{project_id}] Created 3 Bronze BigLake external tables.")


def seed_platform_admin_tables() -> None:
    bq_client = bigquery.Client(project=ADMIN_PROJECT_ID, location=REGION)

    bq_client.query(f"TRUNCATE TABLE `{ADMIN_PROJECT_ID}.platform_admin.tenants`").result()
    bq_client.query(f"TRUNCATE TABLE `{ADMIN_PROJECT_ID}.platform_admin.sources`").result()
    bq_client.query(f"TRUNCATE TABLE `{ADMIN_PROJECT_ID}.platform_admin.schedules`").result()

    for cfg in TENANT_CONFIGS:
        tenant_insert = f"""
        INSERT INTO `{ADMIN_PROJECT_ID}.platform_admin.tenants`
        (tenant_id, project_id, tenant_name, industry, sla_tier, service_account_email, landing_bucket, biglake_connection_id, default_currency, default_timezone, is_active, onboarded_at)
        VALUES (
          '{cfg["tenant_id"]}',
          '{cfg["project_id"]}',
          '{cfg["tenant_name"]}',
          '{cfg["industry"]}',
          '{cfg["sla_tier"]}',
          '{cfg["service_account_email"]}',
          '{cfg["landing_bucket"]}',
          '{cfg["biglake_connection_id"]}',
          '{cfg["default_currency"]}',
          '{cfg["default_timezone"]}',
          TRUE,
          CURRENT_TIMESTAMP()
        )
        """
        bq_client.query(tenant_insert).result()

        for table_name, src_type in [
            ("raw_ad_spend_daily", "MULTI_CHANNEL_AD_FEED_GCS"),
            ("raw_crm_customers", "1P_CRM_GCS"),
            ("raw_conversions", "1P_CONVERSIONS_GCS"),
        ]:
            source_insert = f"""
            INSERT INTO `{ADMIN_PROJECT_ID}.platform_admin.sources`
            (tenant_id, source_name, source_type, gcs_uri, target_bronze_table, is_enabled)
            VALUES (
              '{cfg["tenant_id"]}',
              '{table_name}',
              '{src_type}',
              'gs://{cfg["landing_bucket"]}/raw/{table_name}.csv',
              '{cfg["project_id"]}.bronze.{table_name}',
              TRUE
            )
            """
            bq_client.query(source_insert).result()

    schedule_insert = f"""
    INSERT INTO `{ADMIN_PROJECT_ID}.platform_admin.schedules`
    (schedule_id, sla_tier, cron_schedule, description)
    VALUES
      ('SCHED-01', 'TIER_1_DAILY_0600', '0 6 * * *', 'Daily 6:00 AM ET SLA fan-out for Tier 1 advertisers')
    """
    bq_client.query(schedule_insert).result()
    print(f"[{ADMIN_PROJECT_ID}] Seeded platform_admin.tenants, sources, and schedules.")


def main() -> None:
    for cfg in TENANT_CONFIGS:
        datasets = generate_tenant_datasets(cfg["tenant_id"])
        upload_and_create_bronze_tables(cfg, datasets)
    seed_platform_admin_tables()


if __name__ == "__main__":
    main()
```

Create `scripts/seed_dataform_workspace.py`:
```python
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
```

Create `scripts/verify_platform.py`:
```python
#!/usr/bin/env python3
"""Triggers the parent Cloud Workflow in agency-platform-123, waits for completion,
and verifies platform_admin.run_log, all 9 Medallion tables in advertiser-01 and
advertiser-02, GCS Iceberg Parquet/metadata files, and cross-tenant IAM isolation.
"""

import json
import subprocess
import time
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
```

- [ ] **Step 4: Run `pytest` to verify all unit tests pass**

Run: `pytest -v`
Expected: PASS (6 passed across `tests/test_workflows_and_dataform.py` and `tests/test_synthetic_data.py`)

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/ tests/test_synthetic_data.py
git commit -m "feat(scripts): add synthetic data generator, Dataform workspace seeder, and end-to-end verification suite"
```

---

### Task 5: Live GCP Deployment, End-to-End Execution & Documentation (`README.md`)

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: `terraform/`, `dataform/`, `workflows/`, `scripts/` from Tasks 1–4.
- Produces: Live deployed infrastructure and populated Medallion tables across `agency-platform-123`, `advertiser-01`, and `advertiser-02`, verified end-to-end, plus `README.md`.

- [ ] **Step 1: Apply Terraform across `agency-platform-123`, `advertiser-01`, and `advertiser-02`**

Run: `terraform -chdir=terraform init && terraform -chdir=terraform apply -auto-approve`
Expected: `Apply complete!` with outputs for `agency_admin_summary` and `tenants_summary`.
*(Note: If an Organization Policy `constraints/iam.disableCrossProjectServiceAccountUsage` blocks cross-project service account impersonation on `advertiser-01` or `advertiser-02`, update the project-level org policy on `advertiser-01` and `advertiser-02` via `gcloud resource-manager org-policies disable-enforce iam.disableCrossProjectServiceAccountUsage --project=<project_id>` so `agency-platform-123` Dataform can impersonate `sa-dataform@<tenant>` as designed in the reference architecture.)*

- [ ] **Step 2: Generate & upload synthetic data, create Bronze BigLake external tables, and seed `platform_admin` control tables**

Run: `python3 scripts/generate_and_load_synthetic_data.py`
Expected:
- Uploads 3 CSV files each to `gs://advertiser-01-landing/raw/` and `gs://advertiser-02-landing/raw/`
- Creates `bronze.raw_ad_spend_daily`, `bronze.raw_crm_customers`, and `bronze.raw_conversions` in `advertiser-01` and `advertiser-02`
- Seeds `agency-platform-123.platform_admin.{tenants,sources,schedules}`

- [ ] **Step 3: Seed the central Dataform workspace in `agency-platform-123` and verify per-tenant compilation**

Run: `python3 scripts/seed_dataform_workspace.py`
Expected:
- Uploads `workflow_settings.yaml` and all 9 SQLX files to `projects/agency-platform-123/locations/us-central1/repositories/medallion-pipeline/workspaces/default`
- Prints `Verified clean Dataform compilation for advertiser-01` and `Verified clean Dataform compilation for advertiser-02`

- [ ] **Step 4: Execute the parent Cloud Workflow fan-out and run the full verification script**

Run: `python3 scripts/verify_platform.py`
Expected:
- `medallion-parent-orchestrator` completes with `state=SUCCEEDED`
- `agency-platform-123.platform_admin.run_log` shows `SUCCEEDED` for both `advertiser_01` and `advertiser_02`
- All 9 tables in `advertiser-01` and `advertiser-02` match exact expected deduplicated row counts
- Iceberg Parquet and metadata files are verified in `gs://advertiser-01-landing/iceberg/` and `gs://advertiser-02-landing/iceberg/`
- Prints `ALL END-TO-END PLATFORM VERIFICATIONS PASSED!`

- [ ] **Step 5: Create `README.md` with Architecture Walkthrough, Demo Queries & "Onboard Advertiser N+1" Guide**

Create `README.md`:
```markdown
# Multi-Tenant, Isolated Agency-Advertisers Data Platform (GCP Demo)

A live reference implementation of a **Multi-Tenant, Isolated Advertiser Medallion Data Platform** on Google Cloud for media agencies.

## 1. Architecture Overview

- **Agency Admin Project (`agency-platform-123`) — Single Pane of Glass Control Plane:**
  - **BigQuery `platform_admin` dataset:** Central metadata (`tenants`, `sources`, `schedules`) and operational audit log (`run_log`).
  - **Dataform (`medallion-pipeline`):** One shared SQLX repository compiled dynamically per tenant using `defaultDatabase = <tenant_project_id>` and `vars.tenant_id`, and executed as each tenant's isolated service account (`sa-dataform@<tenant_project>`).
  - **Cloud Workflows (`medallion-parent-orchestrator` & `medallion-tenant-child-workflow`):** Parallel fan-out orchestration across all active advertiser tenants.
  - **Cloud Scheduler (`medallion-daily-schedule`):** Automated SLA-tier trigger.

- **Isolated Advertiser Tenant Projects (`advertiser-01` "Apex Apparel", `advertiser-02` "Nova FinTech"):**
  - **GCS Landing & Iceberg Bucket (`gs://<tenant>-landing`):** `/raw/*.csv` for incoming feeds and `/iceberg/*` for open Apache Iceberg Parquet + metadata snapshots.
  - **BigLake Connection (`us-central1.lakehouse-connection`):** Scoped exclusively to the tenant's bucket.
  - **9 Medallion Tables per Tenant:**
    - **Bronze (3 BigLake External Tables):** `bronze.raw_ad_spend_daily`, `bronze.raw_crm_customers`, `bronze.raw_conversions`
    - **Silver (3 Native BigQuery Tables + Dataform Assertions):** `silver.stg_ad_spend_daily`, `silver.stg_crm_customers` (SHA-256 hashed PII, raw PII dropped), `silver.stg_conversions`
    - **Gold (2 Native Marts + 1 Managed Apache Iceberg Sharing Table):** `gold.mart_cross_channel_performance`, `gold.mart_customer_attribution`, `gold.share_cross_channel_performance_iceberg`
  - **BigQuery Analytics Hub (`<tenant_id>_exchange` / `<tenant_id>_gold_listing`):** Zero-copy dataset sharing per advertiser.

## 2. Quick Start & Demo Commands

### Trigger Parallel Multi-Tenant Pipeline Run
```bash
python3 scripts/verify_platform.py
```

### Sample Demo Queries

**1. Single Pane of Glass — Check Cross-Tenant Pipeline Status (`agency-platform-123`):**
```sql
SELECT
  run_id,
  tenant_id,
  project_id,
  status,
  TIMESTAMP_DIFF(completed_at, started_at, SECOND) AS duration_sec,
  dataform_invocation_id,
  notes
FROM `agency-platform-123.platform_admin.run_log`
ORDER BY started_at DESC;
```

**2. Compare Bronze Raw vs. Silver Deduplicated & FX-Normalized Spend (`advertiser-01`):**
```sql
SELECT
  '1_BRONZE_RAW' AS layer,
  COUNT(*) AS row_count,
  COUNT(DISTINCT currency) AS distinct_currencies
FROM `advertiser-01.bronze.raw_ad_spend_daily`
UNION ALL
SELECT
  '2_SILVER_CLEANSED' AS layer,
  COUNT(*) AS row_count,
  1 AS distinct_currencies
FROM `advertiser-01.silver.stg_ad_spend_daily`;
```

**3. Inspect Gold Cross-Channel ROAS, CPA & Pacing (`advertiser-01` vs. `advertiser-02`):**
```sql
SELECT
  tenant_id,
  channel,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  ROUND(SUM(spend_usd), 2) AS total_spend_usd,
  SUM(conversions_count) AS total_conversions,
  ROUND(SUM(attributed_revenue_usd), 2) AS total_revenue_usd,
  ROUND(SAFE_DIVIDE(SUM(attributed_revenue_usd), SUM(spend_usd)), 2) AS blended_roas
FROM `advertiser-01.gold.mart_cross_channel_performance`
GROUP BY 1, 2
ORDER BY total_spend_usd DESC;
```

**4. Query the Gold Managed Apache Iceberg Table (`share_cross_channel_performance_iceberg`):**
```sql
SELECT *
FROM `advertiser-01.gold.share_cross_channel_performance_iceberg`
ORDER BY report_date DESC, spend_usd DESC
LIMIT 10;
```

## 3. Onboard Advertiser N+1 (Zero Pipeline Code Change)

1. Add `advertiser_03` to the `tenants` map in `terraform/terraform.tfvars`.
2. Run `terraform -chdir=terraform apply`.
3. Insert the new tenant record into `agency-platform-123.platform_admin.tenants`.
4. The next scheduled execution of `medallion-parent-orchestrator` automatically compiles and runs the shared Dataform Medallion pipeline inside the new advertiser's project.
```

- [ ] **Step 6: Commit `README.md`**

```bash
git add README.md
git commit -m "docs: add architecture guide, demo SQL queries, and tenant onboarding instructions"
```
