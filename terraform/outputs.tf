output "agency_admin_summary" {
  description = "Summary of Agency Admin control plane resources"
  value = {
    admin_project_id             = var.admin_project_id
    platform_admin_dataset       = module.agency_admin.platform_admin_dataset_id
    dataform_repository_name     = module.agency_admin.dataform_repository_name
    orchestrator_sa_email        = module.agency_admin.orchestrator_sa_email
    dataform_service_agent_email = module.agency_admin.dataform_service_agent_email
    parent_workflow_name         = module.agency_admin.parent_workflow_name
    child_workflow_name          = module.agency_admin.child_workflow_name
  }
}

output "tenants_summary" {
  description = "Per-tenant isolated resources provisioned by Tenant Factory"
  value = {
    for k, m in module.tenant_factory : k => {
      project_id              = m.project_id
      landing_bucket          = m.landing_bucket_name
      tenant_dataform_sa      = m.tenant_dataform_sa_email
      biglake_connection_id   = m.biglake_connection_id
      biglake_service_account = m.biglake_connection_sa
      datasets                = m.dataset_ids
      analytics_hub_listing   = m.analytics_hub_listing_id
    }
  }
}
