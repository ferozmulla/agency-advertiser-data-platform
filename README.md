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
