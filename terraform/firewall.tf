# Allow external access to seller/buyer server REST APIs (all 4 app VMs)
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

# Allow internal gRPC traffic to product-db (VPC only)
resource "google_compute_firewall" "allow_product_db_grpc" {
  name    = "allow-product-db-grpc"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["50051", "50054", "12345", "12346"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["product-db"]
}

# Allow internal gRPC traffic to customer-db nodes (VPC only)
# Port 50052: nodes on vm2-4 and node-0 on vm1
# Port 50053: node-1 on vm1 (published to a different host port)
resource "google_compute_firewall" "allow_customer_db_grpc" {
  name    = "allow-customer-db-grpc"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["50052", "50053"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["customer-db"]
}

# Allow ABP UDP between customer-db nodes (VPC only)
# Port 5100: node on each VM;  Port 5101: node-1 on vm1
resource "google_compute_firewall" "allow_abp_udp" {
  name    = "allow-abp-udp"
  network = "default"
  project = var.project_id

  allow {
    protocol = "udp"
    ports    = ["5100", "5101"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["customer-db"]
}

# Allow internal access to financial-transactions SOAP service (VPC only)
# buyer-server containers on vm2-4 connect to vm1:8000
resource "google_compute_firewall" "allow_financial_transactions" {
  name    = "allow-financial-transactions"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["financial-transactions"]
}

# Allow SSH to all VMs for debugging
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
