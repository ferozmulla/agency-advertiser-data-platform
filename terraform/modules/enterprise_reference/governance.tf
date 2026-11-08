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
