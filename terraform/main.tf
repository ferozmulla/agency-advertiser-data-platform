module "agency_admin" {
  source = "./modules/agency_admin"

  admin_project_id         = var.admin_project_id
  region                   = var.region
  parent_workflow_yaml     = file("${path.module}/../workflows/parent_orchestrator.yaml")
  child_workflow_yaml      = file("${path.module}/../workflows/tenant_child_workflow.yaml")
}

module "tenant_factory" {
  source   = "./modules/tenant_factory"
  for_each = var.tenants

  admin_project_id              = var.admin_project_id
  region                        = var.region
  tenant_id                     = each.value.tenant_id
  project_id                    = each.value.project_id
  tenant_name                   = each.value.tenant_name
  industry                      = each.value.industry
  sla_tier                      = each.value.sla_tier
  orchestrator_sa_email         = module.agency_admin.orchestrator_sa_email
  admin_dataform_service_agent  = module.agency_admin.dataform_service_agent_email
}

module "enterprise_reference" {
  source = "./modules/enterprise_reference"

  admin_project_id                 = var.admin_project_id
  region                           = var.region
  tenants                          = var.tenants
  enable_vpc_sc                    = var.enable_vpc_sc
  enable_cmek                      = var.enable_cmek
  enable_dts_connectors            = var.enable_dts_connectors
  enable_dataplex_governance       = var.enable_dataplex_governance
  enable_monitoring_alerts         = var.enable_monitoring_alerts
  enable_cloudbuild_cicd           = var.enable_cloudbuild_cicd
  access_context_manager_policy_id = var.access_context_manager_policy_id
}
