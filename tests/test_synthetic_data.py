from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
