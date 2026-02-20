terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}


# Static internal IP reservations for DB VMs

resource "google_compute_address" "product_db_internal" {
  name         = "product-db-internal-ip"
  project      = var.project_id
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  address      = var.product_db_internal_ip
}

resource "google_compute_address" "customer_db_internal" {
  name         = "customer-db-internal-ip"
  project      = var.project_id
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  address      = var.customer_db_internal_ip
}


# Docker install script

locals {
  docker_install = <<-SCRIPT
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io
  SCRIPT
}

# ─────────────────────────────────────────────────────────
# Product DB VM
# ─────────────────────────────────────────────────────────

resource "google_compute_instance" "product_db_vm" {
  name         = "product-db-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["product-db", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.product_db_internal.address
    access_config {} # Ephemeral external IP needed for outbound internet (apt-get, git clone, docker pull)
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "=== [product-db-vm] Installing Docker ==="
    ${local.docker_install}

    echo "=== [product-db-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app

    echo "=== [product-db-vm] Building image (build context: repo root) ==="
    cd /opt/app
    docker build -t product-db:latest -f services/product-db/Dockerfile .

    echo "=== [product-db-vm] Starting container ==="
    docker run -d \
      --name product-db \
      --restart unless-stopped \
      -p 50051:50051 \
      -e POSTGRES_DB=product_db \
      -e POSTGRES_USER=product_user \
      -e POSTGRES_PASSWORD=product_password \
      -v product_db_data:/var/lib/postgresql/data \
      product-db:latest

    echo "=== [product-db-vm] Startup complete ==="
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}


# Customer DB VM

resource "google_compute_instance" "customer_db_vm" {
  name         = "customer-db-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["customer-db", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.customer_db_internal.address
    access_config {} # Ephemeral external IP needed for outbound internet (apt-get, git clone, docker pull)
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "=== [customer-db-vm] Installing Docker ==="
    ${local.docker_install}

    echo "=== [customer-db-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app

    echo "=== [customer-db-vm] Building image (build context: repo root) ==="
    cd /opt/app
    docker build -t customer-db:latest -f services/customer-db/Dockerfile .

    echo "=== [customer-db-vm] Starting container ==="
    docker run -d \
      --name customer-db \
      --restart unless-stopped \
      -p 50052:50052 \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -v customer_db_data:/var/lib/postgresql/data \
      customer-db:latest

    echo "=== [customer-db-vm] Startup complete ==="
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}


# Seller Server VM


resource "google_compute_instance" "seller_server_vm" {
  name         = "seller-server-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  # Depend on address reservations so their IPs are known before
  # this VM's startup script is rendered with the interpolated values.
  depends_on = [
    google_compute_address.product_db_internal,
    google_compute_address.customer_db_internal,
  ]

  tags = ["seller-server", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 15
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    access_config {} # Ephemeral external IP for client access
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "=== [seller-server-vm] Installing Docker ==="
    ${local.docker_install}

    echo "=== [seller-server-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app

    echo "=== [seller-server-vm] Building image (build context: repo root) ==="
    cd /opt/app
    docker build -t seller-server:latest -f services/seller_server/Dockerfile .

    echo "=== [seller-server-vm] Starting container ==="
    docker run -d \
      --name seller-server \
      --restart unless-stopped \
      -p 5000:5000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=5000 \
      -e PRODUCT_DB_HOST="${google_compute_address.product_db_internal.address}" \
      -e PRODUCT_DB_PORT=50051 \
      -e CUSTOMER_DB_HOST="${google_compute_address.customer_db_internal.address}" \
      -e CUSTOMER_DB_PORT=50052 \
      seller-server:latest

    echo "=== [seller-server-vm] Startup complete ==="
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}


# Buyer Server VM
# financial-transactions (SOAP) runs on the same VM in a separate container.

resource "google_compute_instance" "buyer_server_vm" {
  name         = "buyer-server-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  depends_on = [
    google_compute_address.product_db_internal,
    google_compute_address.customer_db_internal,
  ]

  tags = ["buyer-server", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 15
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    access_config {} # Ephemeral external IP for client access
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "=== [buyer-server-vm] Installing Docker ==="
    ${local.docker_install}

    echo "=== [buyer-server-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app

    # Create a Docker network so both containers can communicate by name
    docker network create buyer-net

    echo "=== [buyer-server-vm] Building financial-transactions image ==="
    cd /opt/app
    docker build -t financial-transactions:latest -f services/financial_transactions/Dockerfile services/financial_transactions/

    echo "=== [buyer-server-vm] Starting financial-transactions ==="
    docker run -d \
      --name financial-transactions \
      --network buyer-net \
      --restart unless-stopped \
      financial-transactions:latest

    echo "=== [buyer-server-vm] Building buyer-server image (build context: repo root) ==="
    docker build -t buyer-server:latest -f services/buyer_server/Dockerfile .

    echo "=== [buyer-server-vm] Starting buyer-server ==="
    docker run -d \
      --name buyer-server \
      --network buyer-net \
      --restart unless-stopped \
      -p 6000:6000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=6000 \
      -e PRODUCT_DB_HOST="${google_compute_address.product_db_internal.address}" \
      -e PRODUCT_DB_PORT=50051 \
      -e CUSTOMER_DB_HOST="${google_compute_address.customer_db_internal.address}" \
      -e CUSTOMER_DB_PORT=50052 \
      -e FINANCIAL_TRANSACTIONS_HOST=financial-transactions \
      -e FINANCIAL_TRANSACTIONS_PORT=8000 \
      buyer-server:latest

    echo "=== [buyer-server-vm] Startup complete ==="
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}


# ─────────────────────────────────────────────────────────
# Test Runner VM
# ─────────────────────────────────────────────────────────

resource "google_compute_instance" "test_runner_vm" {
  name         = "test-runner-vm"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  depends_on = [
    google_compute_instance.seller_server_vm,
    google_compute_instance.buyer_server_vm,
  ]

  tags = ["test-runner", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    access_config {}
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "=== [test-runner-vm] Installing Python and dependencies ==="
    apt-get update -y
    apt-get install -y python3 python3-pip git curl

    echo "=== [test-runner-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    pip3 install requests --break-system-packages

    # Write server addresses to env file for easy sourcing
    cat > /opt/app/.env <<'ENVEOF'
export BUYER_SERVER="${google_compute_instance.buyer_server_vm.network_interface[0].access_config[0].nat_ip}"
export BUYER_PORT=6000
export SELLER_SERVER="${google_compute_instance.seller_server_vm.network_interface[0].access_config[0].nat_ip}"
export SELLER_PORT=5000
export PRODUCT_DB_IP="${google_compute_address.product_db_internal.address}"
export CUSTOMER_DB_IP="${google_compute_address.customer_db_internal.address}"
ENVEOF
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}
