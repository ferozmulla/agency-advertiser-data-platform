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
