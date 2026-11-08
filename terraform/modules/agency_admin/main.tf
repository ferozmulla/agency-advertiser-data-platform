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
