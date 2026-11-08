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
