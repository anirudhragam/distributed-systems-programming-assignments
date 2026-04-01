# Allow SSH to all VMs
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-ecommerce"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ecommerce"]
}

# Allow external access to seller/buyer REST APIs
resource "google_compute_firewall" "allow_app_servers" {
  name    = "allow-app-servers"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5000", "6000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ecommerce-app"]
}

# Allow all internal traffic between app VMs (TCP + UDP, all service ports)
# Covers: product-db gRPC (50051,50054), Raft (12345,12346),
#         customer-db gRPC (50052,50053), ABP UDP (5100,5101),
#         financial-transactions (8000)
resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal-ecommerce"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  source_tags = ["ecommerce-internal"]
  target_tags = ["ecommerce-internal"]
}
