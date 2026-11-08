output "project_id" {
  value = var.project_id
}

output "landing_bucket_name" {
  value = google_storage_bucket.landing.name
}

output "tenant_dataform_sa_email" {
  value = google_service_account.tenant_dataform.email
}

output "biglake_connection_id" {
  value = "${var.project_id}.${var.region}.${google_bigquery_connection.lakehouse.connection_id}"
}

output "biglake_connection_sa" {
  value = google_bigquery_connection.lakehouse.cloud_resource[0].service_account_id
}

output "dataset_ids" {
  value = [for k, d in google_bigquery_dataset.medallion : d.dataset_id]
}

output "analytics_hub_listing_id" {
  value = google_bigquery_analytics_hub_listing.gold_listing.id
}
