output "seller_server_addrs" {
  description = "Comma-separated seller server addresses for SERVER_ADDRS env var"
  value = join(",", [
    "${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}:5000",
    "${google_compute_instance.vm2.network_interface[0].access_config[0].nat_ip}:5000",
    "${google_compute_instance.vm3.network_interface[0].access_config[0].nat_ip}:5000",
    "${google_compute_instance.vm4.network_interface[0].access_config[0].nat_ip}:5000",
  ])
}

output "buyer_server_addrs" {
  description = "Comma-separated buyer server addresses for SERVER_ADDRS env var"
  value = join(",", [
    "${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}:6000",
    "${google_compute_instance.vm2.network_interface[0].access_config[0].nat_ip}:6000",
    "${google_compute_instance.vm3.network_interface[0].access_config[0].nat_ip}:6000",
    "${google_compute_instance.vm4.network_interface[0].access_config[0].nat_ip}:6000",
  ])
}

output "vm1_external_ip" {
  value = google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip
}

output "vm2_external_ip" {
  value = google_compute_instance.vm2.network_interface[0].access_config[0].nat_ip
}

output "vm3_external_ip" {
  value = google_compute_instance.vm3.network_interface[0].access_config[0].nat_ip
}

output "vm4_external_ip" {
  value = google_compute_instance.vm4.network_interface[0].access_config[0].nat_ip
}

