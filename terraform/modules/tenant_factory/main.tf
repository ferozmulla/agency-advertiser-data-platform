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

# Allow tenant SA to submit BigQuery jobs initiated from the central Dataform repository host project (grants bigquery.jobs.create only, zero dataset access)
resource "google_project_iam_member" "tenant_sa_admin_job_user" {
  project = var.admin_project_id
  role    = "roles/bigquery.jobUser"
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

resource "google_service_account_iam_member" "orchestrator_token_creator" {
  service_account_id = google_service_account.tenant_dataform.name
  role               = "roles/iam.serviceAccountTokenCreator"
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
