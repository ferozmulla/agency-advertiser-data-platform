# Reference Architecture Box B: Cloud Build Tenant Factory GitOps Trigger ("Onboard Advertiser N+1")
# Controlled by var.enable_cloudbuild_cicd (default = false in demo environment)

resource "google_cloudbuild_trigger" "tenant_factory_gitops" {
  count       = var.enable_cloudbuild_cicd ? 1 : 0
  project     = var.admin_project_id
  location    = var.region
  name        = "tenant-factory-onboard-advertiser"
  description = "Provisions new advertiser project resources and registers tenant config on PR merge to main"

  included_files = [
    "terraform/**",
    "dataform/**",
    "workflows/**"
  ]

  build {
    step {
      name = "hashicorp/terraform:1.6"
      args = ["init"]
      dir  = "terraform"
    }
    step {
      name = "hashicorp/terraform:1.6"
      args = ["apply", "-auto-approve"]
      dir  = "terraform"
    }
  }
}
