# Customer Demo Walkthrough Guide: Multi-Tenant Agency-Advertisers Data Platform

This guide walks through a 15-minute live demonstration of the **Agency-Advertisers Client Data Platform** across the three GCP projects:

| Role | GCP Project ID | Persona / Description |
| :--- | :--- | :--- |
| **Control & Orchestration Plane** | `agency-platform-123` | Central metadata catalog (`platform_admin`), Cloud Scheduler, Cloud Workflows, and single-repo Dataform (`medallion-pipeline`) |
| **Advertiser Tenant 01 (Data Plane)** | `advertiser-01` | **Apex Apparel** (Retail & E-Commerce) — Isolated GCS landing bucket, BigLake connection, Bronze/Silver/Gold datasets, Iceberg & Analytics Hub |
| **Advertiser Tenant 02 (Data Plane)** | `advertiser-02` | **Nova FinTech** (Financial Services) — Isolated GCS landing bucket, BigLake connection, Bronze/Silver/Gold datasets, Iceberg & Analytics Hub |

---

## Act 1: The Control Plane & Metadata-Driven Registry (`agency-platform-123`)

**Talking Points:**
* Instead of deploying separate orchestrators or separate SQL repositories for every client, the agency operates a single **Control & Orchestration Plane** in `agency-platform-123`.
* Adding an advertiser to the daily orchestration run is metadata-driven via the `platform_admin` BigQuery dataset.

### 1. Inspect the Control Plane Tables in BigQuery
Open the [BigQuery Console for `agency-platform-123`](https://console.cloud.google.com/bigquery?project=agency-platform-123) and run:

```sql
-- 1A. View registered advertiser tenants and their dedicated execution identities
SELECT
  tenant_id,
  tenant_name,
  gcp_project_id,
  bq_location,
  landing_bucket,
  dataform_sa,
  is_active
FROM `agency-platform-123.platform_admin.tenants`
ORDER BY tenant_id;
```

```sql
-- 1B. View recent pipeline execution audit logs across all tenants
SELECT
  run_id,
  tenant_id,
  status,
  started_at,
  completed_at,
  TIMESTAMP_DIFF(completed_at, started_at, SECOND) AS duration_seconds,
  dataform_invocation_id
FROM `agency-platform-123.platform_admin.run_log`
ORDER BY started_at DESC
LIMIT 10;
```

---

## Act 2: Single-Repo Dataform Parameterization (`agency-platform-123`)

**Talking Points:**
* A major requirement from the architecture review is avoiding code duplication across 50+ advertisers.
* We maintain **one** Dataform repository (`medallion-pipeline`) in `agency-platform-123` ([`dataform/workflow_settings.yaml`](../dataform/workflow_settings.yaml)).
* At runtime, Cloud Workflows compiles this single repository with a compilation override (`defaultDatabase = <tenant_gcp_project_id>`) and executes the DAG using that tenant's isolated service account (`sa-dataform@<tenant_gcp_project_id>`).

### 1. Show the Dataform Repository in Console
Open the [Dataform Repository in `agency-platform-123`](https://console.cloud.google.com/bigquery/dataform/locations/us-central1/repositories/medallion-pipeline/details/workspaces?project=agency-platform-123):
* Open `default` workspace -> [`definitions/bronze/raw_ad_spend_daily.sqlx`](../dataform/definitions/bronze/raw_ad_spend_daily.sqlx) to show how `${dataform.projectConfig.defaultDatabase}` dynamically binds to `advertiser-01` or `advertiser-02` at compile time.
* Open [`definitions/silver/stg_crm_customers.sqlx`](../dataform/definitions/silver/stg_crm_customers.sqlx) to show built-in Dataform data quality assertions (`nonNull: ["customer_id", "email_hash"]`, `uniqueKey: ["customer_id"]`).

---

## Act 3: Parallel Fan-Out Orchestration (`agency-platform-123`)

**Talking Points:**
* Cloud Scheduler (`medallion-daily-schedule`) triggers `medallion-parent-orchestrator` daily at 06:00 UTC.
* The **Parent Workflow** ([`workflows/parent_orchestrator.yaml`](../workflows/parent_orchestrator.yaml)) queries `platform_admin.tenants WHERE is_active = TRUE` and fans out in parallel (`parallel: for: tenant in active_tenants`).
* Each parallel branch invokes `medallion-tenant-child-workflow` ([`workflows/tenant_child_workflow.yaml`](../workflows/tenant_child_workflow.yaml)), which logs `RUNNING`, compiles the shared Dataform repo for that specific advertiser project, executes the DAG under `sa-dataform@<advertiser-project>`, and updates `platform_admin.run_log` to `SUCCEEDED`.

### 1. Trigger a Live Orchestration Run (Console or CLI)
Open [Cloud Workflows in `agency-platform-123`](https://console.cloud.google.com/workflows?project=agency-platform-123), click `medallion-parent-orchestrator` -> **Execute**, or run from the terminal:

```bash
gcloud workflows run medallion-parent-orchestrator \
  --project=agency-platform-123 \
  --location=us-central1
```

* Click into `medallion-tenant-child-workflow` -> **Executions** tab to show the two concurrent child executions running in parallel for `advertiser-01` and `advertiser-02`.

---

## Act 4: Medallion Layers & PII Hashing (`advertiser-01` & `advertiser-02`)

**Talking Points:**
* Each advertiser's data stays inside their own GCP project from landing to Gold.
* **Bronze (`bronze.*`)**: BigLake external tables over raw CSV files in `gs://advertiser-01-landing/raw/`. Contains uncleaned rows, whitespace, duplicates, negative spend anomalies, and cleartext PII (`email`, `phone`).
* **Silver (`silver.*`)**: Deduplicated, type-cast native BigQuery tables. Cleartext `email` and `phone` are normalized and hashed with `SHA256`, and raw PII columns are excluded from Silver and Gold.
* **Gold (`gold.*`)**: Business-ready cross-channel ROAS/CPA performance and hashed customer LTV attribution marts.

### 1. Compare Bronze vs. Silver vs. Gold in `advertiser-01`
Open the [BigQuery Console for `advertiser-01`](https://console.cloud.google.com/bigquery?project=advertiser-01) and run:

```sql
-- 4A. Row count comparison showing deduplication and filtering from Bronze -> Silver -> Gold
SELECT '1_bronze.raw_ad_spend_daily' AS table_name, COUNT(*) AS row_count FROM `advertiser-01.bronze.raw_ad_spend_daily`
UNION ALL SELECT '2_silver.stg_ad_spend_daily', COUNT(*) FROM `advertiser-01.silver.stg_ad_spend_daily`
UNION ALL SELECT '3_bronze.raw_crm_customers', COUNT(*) FROM `advertiser-01.bronze.raw_crm_customers`
UNION ALL SELECT '4_silver.stg_crm_customers', COUNT(*) FROM `advertiser-01.silver.stg_crm_customers`
UNION ALL SELECT '5_bronze.raw_conversions', COUNT(*) FROM `advertiser-01.bronze.raw_conversions`
UNION ALL SELECT '6_silver.stg_conversions', COUNT(*) FROM `advertiser-01.silver.stg_conversions`
UNION ALL SELECT '7_gold.mart_cross_channel_performance', COUNT(*) FROM `advertiser-01.gold.mart_cross_channel_performance`
UNION ALL SELECT '8_gold.mart_customer_attribution', COUNT(*) FROM `advertiser-01.gold.mart_customer_attribution`
UNION ALL SELECT '9_gold.share_cross_channel_performance_iceberg', COUNT(*) FROM `advertiser-01.gold.share_cross_channel_performance_iceberg`
ORDER BY table_name;
```

```sql
-- 4B. Demonstrate PII Hashing: Cleartext email/phone in Bronze vs. SHA-256 hashes in Silver
SELECT
  b.customer_id,
  b.email AS bronze_cleartext_email,
  b.phone AS bronze_cleartext_phone,
  TO_HEX(s.email_hash) AS silver_sha256_email_hash,
  TO_HEX(s.phone_hash) AS silver_sha256_phone_hash,
  s.loyalty_tier,
  s.country_code
FROM `advertiser-01.bronze.raw_crm_customers` b
JOIN `advertiser-01.silver.stg_crm_customers` s
  ON TRIM(b.customer_id) = s.customer_id
LIMIT 10;
```

```sql
-- 4C. Compare Gold Cross-Channel ROAS & CPA across Advertiser 01 (Apex Apparel) vs Advertiser 02 (Nova FinTech)
SELECT
  'advertiser-01 (Apex Apparel)' AS advertiser,
  channel,
  SUM(impressions) AS total_impressions,
  SUM(clicks) AS total_clicks,
  ROUND(SUM(spend_usd), 2) AS total_spend_usd,
  ROUND(SUM(total_conversions), 2) AS total_conversions,
  ROUND(SUM(total_revenue_usd), 2) AS total_revenue_usd,
  ROUND(SAFE_DIVIDE(SUM(total_revenue_usd), SUM(spend_usd)), 2) AS blended_roas
FROM `advertiser-01.gold.mart_cross_channel_performance`
GROUP BY channel
UNION ALL
SELECT
  'advertiser-02 (Nova FinTech)' AS advertiser,
  channel,
  SUM(impressions),
  SUM(clicks),
  ROUND(SUM(spend_usd), 2),
  ROUND(SUM(total_conversions), 2),
  ROUND(SUM(total_revenue_usd), 2),
  ROUND(SAFE_DIVIDE(SUM(total_revenue_usd), SUM(spend_usd)), 2)
FROM `advertiser-02.gold.mart_cross_channel_performance`
GROUP BY channel
ORDER BY advertiser, channel;
```

---

## Act 5: Cross-Cloud & Partner Data Sharing (Iceberg + Analytics Hub)

**Talking Points:**
* Advertisers often want their curated Gold data shared back to their own Snowflake, Databricks, AWS/Azure environments, or partner BI tools without egress lock-in.
* Every tenant project automatically produces:
  1. **A BigLake Managed Apache Iceberg table** (`gold.share_cross_channel_performance_iceberg`) backed by standard Parquet data files and Iceberg metadata snapshots in the tenant's GCS bucket.
  2. **A BigQuery Analytics Hub Data Exchange & Listing** (`advertiser_01_exchange` / `advertiser_01_gold_listing`) for zero-copy BigQuery sharing.

### 1. Inspect the Apache Iceberg Metadata & Parquet Files in GCS
Run the following commands to show the live Iceberg `metadata/` and `data/` objects written by BigQuery/BigLake into `gs://advertiser-01-landing`:

```bash
# Force a fresh metadata snapshot export if demonstrating live file creation
bq query --project_id=advertiser-01 --use_legacy_sql=false \
  "EXPORT TABLE METADATA FROM \`advertiser-01.gold.share_cross_channel_performance_iceberg\`"

gcloud storage ls --recursive gs://advertiser-01-landing/iceberg/cross_channel_performance/
```

### 2. Show Analytics Hub Listings
Open [Analytics Hub in `advertiser-01`](https://console.cloud.google.com/bigquery/analytics-hub/exchanges?project=advertiser-01) to show `Apex Apparel Gold Data Exchange` and its published listing `Apex Apparel Gold Marts Listing` pointing to `advertiser-01.gold`.

---

## Act 6: Proving Tenant Isolation & 1-Block Tenant Onboarding

**Talking Points:**
* **Strict Tenant Isolation:** `sa-dataform@advertiser-01.iam.gserviceaccount.com` only has permissions on `advertiser-01` datasets and `gs://advertiser-01-landing`. It has zero access to `advertiser-02`.
* **Rapid Tenant Onboarding:** Provisioning a new advertiser (`advertiser-03`) requires adding one map entry in [`terraform/terraform.tfvars`](../terraform/terraform.tfvars) — no changes to the Dataform SQLX files or Cloud Workflows definitions.

### 1. Run the Cross-Tenant Isolation Check
Run this command in the terminal to prove that `sa-dataform@advertiser-01` cannot read `advertiser-02`'s Gold data:

```bash
gcloud projects get-iam-policy advertiser-02 \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-dataform@advertiser-01.iam.gserviceaccount.com"
```
*(Returns `Listed 0 items.`, and the automated test in [`scripts/verify_platform.py`](../scripts/verify_platform.py) further tests live service-account impersonation against `advertiser-02.gold.mart_cross_channel_performance` to confirm an HTTP `403 Access Denied`.)*

### 2. Show the Enterprise Reference Modules in Terraform
Open [`terraform/modules/enterprise_reference/`](../terraform/modules/enterprise_reference/variables.tf) to walk the customer through the production toggle modules ready for Day-2 hardening:
* [`vpc_sc.tf`](../terraform/modules/enterprise_reference/vpc_sc.tf) — Per-advertiser VPC Service Controls perimeter and explicit Admin->Tenant ingress bridge.
* [`cmek.tf`](../terraform/modules/enterprise_reference/cmek.tf) — Per-advertiser Cloud KMS keyring and crypto key for GCS & BigQuery encryption.
* [`dts_connectors.tf`](../terraform/modules/enterprise_reference/dts_connectors.tf) — Google Ads / Campaign Manager 360 BigQuery Data Transfer configs + Cloud Run 3P Ad API pullers.
* [`governance.tf`](../terraform/modules/enterprise_reference/governance.tf) — Dataplex Lake, Data Catalog PII Policy Tags (`PII_Confidential`, `PII_Hashed`), and Data Quality scans.
* [`monitoring.tf`](../terraform/modules/enterprise_reference/monitoring.tf) & [`cicd_cloudbuild.tf`](../terraform/modules/enterprise_reference/cicd_cloudbuild.tf) — Cloud Monitoring SLA failure alerts and GitOps Cloud Build onboarding pipeline.
