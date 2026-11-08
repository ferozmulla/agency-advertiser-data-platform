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
