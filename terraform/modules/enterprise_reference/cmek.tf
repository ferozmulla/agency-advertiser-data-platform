# Reference Architecture Box C: Per-Tenant Cloud KMS CMEK Encryption
# Controlled by var.enable_cmek (default = false in demo environment)

resource "google_kms_key_ring" "tenant_keyring" {
  for_each = var.enable_cmek ? var.tenants : {}
  project  = each.value.project_id
  name     = "${each.value.tenant_id}-cmek-keyring"
  location = var.region
}

resource "google_kms_crypto_key" "tenant_bq_gcs_key" {
  for_each        = var.enable_cmek ? var.tenants : {}
  name            = "${each.value.tenant_id}-data-key"
  key_ring        = google_kms_key_ring.tenant_keyring[each.key].id
  rotation_period = "7776000s" # 90 days
}
