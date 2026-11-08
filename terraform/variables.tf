variable "admin_project_id" {
  description = "Centralized Agency Admin GCP project ID"
  type        = string
  default     = "agency-platform-123"
}

variable "region" {
  description = "Default GCP region for BigQuery, Dataform, Workflows, and GCS"
  type        = string
  default     = "us-central1"
}

variable "tenants" {
  description = "Map of advertiser tenants to provision via the Tenant Factory"
  type = map(object({
    tenant_id        = string
    project_id       = string
    tenant_name      = string
    industry         = string
    sla_tier         = string
    default_currency = string
    default_timezone = string
  }))
}

variable "enable_vpc_sc" {
  description = "Enable VPC Service Controls per-tenant perimeters (disabled in demo to prevent lockout)"
  type        = bool
  default     = false
}

variable "enable_cmek" {
  description = "Enable Cloud KMS Customer-Managed Encryption Keys per tenant"
  type        = bool
  default     = false
}

variable "enable_dts_connectors" {
  description = "Enable BigQuery Data Transfer Service (GMP) and 3P Ad API Cloud Run connector jobs"
  type        = bool
  default     = false
}

variable "enable_dataplex_governance" {
  description = "Enable Dataplex / Knowledge Catalog governance and DQ scans"
  type        = bool
  default     = false
}

variable "enable_monitoring_alerts" {
  description = "Enable Cloud Monitoring SLA alert policies and FinOps chargeback views"
  type        = bool
  default     = false
}

variable "enable_cloudbuild_cicd" {
  description = "Enable Cloud Build GitOps trigger for PR-driven tenant onboarding"
  type        = bool
  default     = false
}

variable "access_context_manager_policy_id" {
  description = "Optional Organization Access Context Manager Policy ID when enable_vpc_sc is true"
  type        = string
  default     = ""
}
