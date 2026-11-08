variable "admin_project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "tenants" {
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
  type    = bool
  default = false
}

variable "enable_cmek" {
  type    = bool
  default = false
}

variable "enable_dts_connectors" {
  type    = bool
  default = false
}

variable "enable_dataplex_governance" {
  type    = bool
  default = false
}

variable "enable_monitoring_alerts" {
  type    = bool
  default = false
}

variable "enable_cloudbuild_cicd" {
  type    = bool
  default = false
}

variable "access_context_manager_policy_id" {
  type    = string
  default = ""
}
