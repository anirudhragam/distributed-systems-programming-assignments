output "seller_server_external_ip" {
  description = "External IP of the seller server VM"
  value       = google_compute_instance.seller_server_vm.network_interface[0].access_config[0].nat_ip
}

output "buyer_server_external_ip" {
  description = "External IP of the buyer server VM"
  value       = google_compute_instance.buyer_server_vm.network_interface[0].access_config[0].nat_ip
}

output "product_db_internal_ip" {
  description = "Auto-assigned internal IP of the product-db VM"
  value       = google_compute_instance.product_db_vm.network_interface[0].network_ip
}

output "customer_db_internal_ip" {
  description = "Auto-assigned internal IP of the customer-db VM"
  value       = google_compute_instance.customer_db_vm.network_interface[0].network_ip
}

output "seller_server_url" {
  description = "Base URL for the seller REST API"
  value       = "http://${google_compute_instance.seller_server_vm.network_interface[0].access_config[0].nat_ip}:5000"
}

output "buyer_server_url" {
  description = "Base URL for the buyer REST API"
  value       = "http://${google_compute_instance.buyer_server_vm.network_interface[0].access_config[0].nat_ip}:6000"
}
