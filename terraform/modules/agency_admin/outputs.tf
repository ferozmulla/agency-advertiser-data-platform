output "platform_admin_dataset_id" {
  value = google_bigquery_dataset.platform_admin.dataset_id
}

output "dataform_repository_name" {
  value = google_dataform_repository.medallion.name
}

output "orchestrator_sa_email" {
  value = google_service_account.orchestrator.email
}

output "dataform_service_agent_email" {
  value = "service-${data.google_project.admin.number}@gcp-sa-dataform.iam.gserviceaccount.com"
}

output "parent_workflow_name" {
  value = google_workflows_workflow.parent_orchestrator.name
}

output "child_workflow_name" {
  value = google_workflows_workflow.tenant_child.name
}
