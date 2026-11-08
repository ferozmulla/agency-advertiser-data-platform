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
