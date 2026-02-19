# Allow external access to seller server REST API
resource "google_compute_firewall" "allow_seller_server" {
  name    = "allow-seller-server"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["seller-server"]
}

# Allow external access to buyer server REST API
resource "google_compute_firewall" "allow_buyer_server" {
  name    = "allow-buyer-server"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["6000"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["buyer-server"]
}

# Allow internal gRPC traffic to product-db (VPC only)
resource "google_compute_firewall" "allow_product_db_grpc" {
  name    = "allow-product-db-grpc"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["50051"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["product-db"]
}

# Allow internal gRPC traffic to customer-db (VPC only)
resource "google_compute_firewall" "allow_customer_db_grpc" {
  name    = "allow-customer-db-grpc"
  network = "default"
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["50052"]
  }

  source_ranges = ["10.128.0.0/9"]
  target_tags   = ["customer-db"]
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

# Port 8000 (financial-transactions SOAP) is intentionally NOT opened:
# it runs on buyer-server-vm with --network host and is only
# accessed from the co-located buyer-server container via localhost.
