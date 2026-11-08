# Reference Architecture Box C: Per-Tenant VPC Service Controls Perimeter & Admin Bridge
# Controlled by var.enable_vpc_sc (default = false in demo environment)

resource "google_access_context_manager_service_perimeter" "tenant_perimeter" {
  for_each       = var.enable_vpc_sc && var.access_context_manager_policy_id != "" ? var.tenants : {}
  parent         = "accessPolicies/${var.access_context_manager_policy_id}"
  name           = "accessPolicies/${var.access_context_manager_policy_id}/servicePerimeters/${each.value.tenant_id}_perimeter"
  title          = "${each.value.tenant_name} Isolated VPC-SC Perimeter"
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  status {
    restricted_services = [
      "bigquery.googleapis.com",
      "storage.googleapis.com",
      "dataform.googleapis.com",
      "secretmanager.googleapis.com"
    ]

    ingress_policies {
      ingress_from {
        identities = [
          "serviceAccount:sa-orchestrator@${var.admin_project_id}.iam.gserviceaccount.com"
        ]
        sources {
          resource = "projects/${var.admin_project_id}"
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "bigquery.googleapis.com"
          method_selectors {
            method = "*"
          }
        }
      }
    }
  }
}
