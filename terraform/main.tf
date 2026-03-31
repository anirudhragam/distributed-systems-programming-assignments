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

# Shared locals


locals {
  docker_install = <<-SCRIPT
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg git netcat-openbsd
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io
  SCRIPT


  abp_peers = "${google_compute_address.vm1_internal.address}:5100,${google_compute_address.vm1_internal.address}:5101,${google_compute_address.vm2_internal.address}:5100,${google_compute_address.vm3_internal.address}:5100,${google_compute_address.vm4_internal.address}:5100"

  raft_partners_db_0 = "${google_compute_address.vm1_internal.address}:12346,${google_compute_address.vm2_internal.address}:12345,${google_compute_address.vm3_internal.address}:12345,${google_compute_address.vm4_internal.address}:12345"
  raft_partners_db_1 = "${google_compute_address.vm1_internal.address}:12345,${google_compute_address.vm2_internal.address}:12345,${google_compute_address.vm3_internal.address}:12345,${google_compute_address.vm4_internal.address}:12345"
  raft_partners_db_2 = "${google_compute_address.vm1_internal.address}:12345,${google_compute_address.vm1_internal.address}:12346,${google_compute_address.vm3_internal.address}:12345,${google_compute_address.vm4_internal.address}:12345"
  raft_partners_db_3 = "${google_compute_address.vm1_internal.address}:12345,${google_compute_address.vm1_internal.address}:12346,${google_compute_address.vm2_internal.address}:12345,${google_compute_address.vm4_internal.address}:12345"
  raft_partners_db_4 = "${google_compute_address.vm1_internal.address}:12345,${google_compute_address.vm1_internal.address}:12346,${google_compute_address.vm2_internal.address}:12345,${google_compute_address.vm3_internal.address}:12345"
  product_db_hosts   = "${google_compute_address.vm1_internal.address}:50051,${google_compute_address.vm1_internal.address}:50054,${google_compute_address.vm2_internal.address}:50051,${google_compute_address.vm3_internal.address}:50051,${google_compute_address.vm4_internal.address}:50051"
}

resource "google_compute_address" "vm1_internal" {
  name         = "vm1-internal"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  project      = var.project_id
}

resource "google_compute_address" "vm2_internal" {
  name         = "vm2-internal"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  project      = var.project_id
}

resource "google_compute_address" "vm3_internal" {
  name         = "vm3-internal"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  project      = var.project_id
}

resource "google_compute_address" "vm4_internal" {
  name         = "vm4-internal"
  region       = var.region
  address_type = "INTERNAL"
  subnetwork   = "default"
  project      = var.project_id
}


# VM1 — product-db, customer-db-0, customer-db-1,
#         financial-transactions, seller-server-0, buyer-server-0

resource "google_compute_instance" "vm1" {
  name         = "vm1"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["customer-db", "product-db", "financial-transactions", "ecommerce-app", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 30
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.vm1_internal.address
    access_config {}
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "[vm1] Installing Docker "
    ${local.docker_install}

    echo " [vm1] Cloning repo "
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    echo " [vm1] Building images "
    docker build -t product-db:latest -f services/product-db/Dockerfile .
    docker build -t customer-db:latest -f services/customer-db/Dockerfile .
    docker build -t seller-server:latest -f services/seller_server/Dockerfile .
    docker build -t buyer-server:latest -f services/buyer_server/Dockerfile .
    docker build -t financial-transactions:latest \
      -f services/financial_transactions/Dockerfile services/financial_transactions/

    echo " [vm1] Creating bridge network "
    docker network create app-net

    echo " [vm1] Starting product-db-0 (node 0, gRPC 50051, Raft 12345) "
    # product-db-0: gRPC 50051, Raft 12345
    docker run -d --name product-db-0 --network app-net --restart unless-stopped \
      -p 50051:50051 \
      -p 12345:12345 \
      -e POSTGRES_DB=product_db -e POSTGRES_USER=product_user -e POSTGRES_PASSWORD=product_password \
      -e SELF_IP="${google_compute_address.vm1_internal.address}" \
      -e SELF_PORT=12345 \
      -e PARTNERS="${local.raft_partners_db_0}" \
      -v product_db_0_data:/var/lib/postgresql/data \
      -v product_db_0_raft:/data/raft \
      product-db:latest

    echo " [vm1] Starting product-db-1 (node 1, gRPC 50054, Raft 12346) "
    # product-db-1: gRPC exposed on 50054, Raft exposed on 12346
    docker run -d --name product-db-1 --network app-net --restart unless-stopped \
      -p 50054:50051 \
      -p 12346:12346 \
      -e POSTGRES_DB=product_db -e POSTGRES_USER=product_user -e POSTGRES_PASSWORD=product_password \
      -e SELF_IP="${google_compute_address.vm1_internal.address}" \
      -e SELF_PORT=12346 \
      -e PARTNERS="${local.raft_partners_db_1}" \
      -v product_db_1_data:/var/lib/postgresql/data \
      -v product_db_1_raft:/data/raft \
      product-db:latest

    echo " [vm1] Starting customer-db-0 (node 0, UDP 5100, gRPC 50052) "
    docker run -d --name customer-db-0 --network host --restart unless-stopped \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -e ABP_NODE_ID=0 \
      -e "ABP_PEERS=${local.abp_peers}" \
      -e ABP_UDP_PORT=5100 \
      -e GRPC_PORT=50052 \
      -v customer_db_0_data:/var/lib/postgresql/data \
      customer-db:latest

    echo " [vm1] Starting customer-db-1 (node 1, UDP 5101, gRPC 50053) "
    docker run -d --name customer-db-1 --network host --restart unless-stopped \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -e ABP_NODE_ID=1 \
      -e "ABP_PEERS=${local.abp_peers}" \
      -e ABP_UDP_PORT=5101 \
      -e GRPC_PORT=50053 \
      -e PGPORT=5433 \
      -v customer_db_1_data:/var/lib/postgresql/data \
      customer-db:latest

    echo " [vm1] Waiting for customer-db-0 and customer-db-1 "
    until docker exec customer-db-0 pg_isready -U customer_user -d customer_db 2>/dev/null; do sleep 2; done
    until nc -z localhost 50052; do sleep 2; done
    until docker exec customer-db-1 pg_isready -U customer_user -d customer_db 2>/dev/null; do sleep 2; done
    until nc -z localhost 50053; do sleep 2; done

    echo " [vm1] Starting financial-transactions "
    docker run -d --name financial-transactions --network app-net --restart unless-stopped \
      -p 8000:8000 \
      financial-transactions:latest

    echo " [vm1] Starting seller-server-0 "
    docker run -d --name seller-server-0 --network app-net --restart unless-stopped \
      -p 5000:5000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=5000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm1_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      seller-server:latest

    echo " [vm1] Starting buyer-server-0 "
    docker run -d --name buyer-server-0 --network app-net --restart unless-stopped \
      -p 6000:6000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=6000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm1_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      -e FINANCIAL_TRANSACTIONS_HOST=financial-transactions \
      -e FINANCIAL_TRANSACTIONS_PORT=8000 \
      buyer-server:latest

    echo " [vm1] Startup complete "
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}

# VM2 — customer-db-2, seller-server-1, buyer-server-1
resource "google_compute_instance" "vm2" {
  name         = "vm2"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["customer-db", "product-db", "ecommerce-app", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.vm2_internal.address
    access_config {}
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo " [vm2] Installing Docker "
    ${local.docker_install}

    echo " [vm2] Cloning repo "
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    echo " [vm2] Building images "
    docker build -t product-db:latest -f services/product-db/Dockerfile .
    docker build -t customer-db:latest -f services/customer-db/Dockerfile .
    docker build -t seller-server:latest -f services/seller_server/Dockerfile .
    docker build -t buyer-server:latest -f services/buyer_server/Dockerfile .

    echo " [vm2] Creating bridge network "
    docker network create app-net

    # VM2: product-db-2
    echo " [vm2] Starting product-db-2 (node 2, gRPC 50051, Raft 12345) "
    docker run -d --name product-db-2 --network app-net --restart unless-stopped \
      -p 50051:50051 \
      -p 12345:12345 \
      -e POSTGRES_DB=product_db -e POSTGRES_USER=product_user -e POSTGRES_PASSWORD=product_password \
      -e SELF_IP="${google_compute_address.vm2_internal.address}" \
      -e SELF_PORT=12345 \
      -e PARTNERS="${local.raft_partners_db_2}" \
      -v product_db_2_data:/var/lib/postgresql/data \
      -v product_db_2_raft:/data/raft \
      product-db:latest

    echo " [vm2] Starting customer-db-2 (node 2, UDP 5100, gRPC 50052) "
    docker run -d --name customer-db-2 --network host --restart unless-stopped \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -e ABP_NODE_ID=2 \
      -e "ABP_PEERS=${local.abp_peers}" \
      -e ABP_UDP_PORT=5100 \
      -e GRPC_PORT=50052 \
      -v customer_db_2_data:/var/lib/postgresql/data \
      customer-db:latest

    echo " [vm2] Waiting for customer-db-2 "
    until docker exec customer-db-2 pg_isready -U customer_user -d customer_db 2>/dev/null; do sleep 2; done
    until nc -z localhost 50052; do sleep 2; done

    echo " [vm2] Starting seller-server-1 "
    docker run -d --name seller-server-1 --network app-net --restart unless-stopped \
      -p 5000:5000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=5000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm2_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      seller-server:latest

    echo " [vm2] Starting buyer-server-1 "
    docker run -d --name buyer-server-1 --network app-net --restart unless-stopped \
      -p 6000:6000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=6000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm2_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      -e FINANCIAL_TRANSACTIONS_HOST=${google_compute_address.vm1_internal.address} \
      -e FINANCIAL_TRANSACTIONS_PORT=8000 \
      buyer-server:latest

    echo " [vm2] Startup complete "
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}


# VM3 — customer-db-3, seller-server-2, buyer-server-2

resource "google_compute_instance" "vm3" {
  name         = "vm3"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["customer-db", "product-db", "ecommerce-app", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.vm3_internal.address
    access_config {}
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo " [vm3] Installing Docker "
    ${local.docker_install}

    echo " [vm3] Cloning repo "
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    echo " [vm3] Building images "
    docker build -t product-db:latest -f services/product-db/Dockerfile .
    docker build -t customer-db:latest   -f services/customer-db/Dockerfile .
    docker build -t seller-server:latest -f services/seller_server/Dockerfile .
    docker build -t buyer-server:latest  -f services/buyer_server/Dockerfile .

    echo " [vm3] Creating bridge network "
    docker network create app-net

    # VM3: product-db-3
    echo " [vm3] Starting product-db-3 (node 2, gRPC 50051, Raft 12345) "
    docker run -d --name product-db-3 --network app-net --restart unless-stopped \
      -p 50051:50051 \
      -p 12345:12345 \
      -e POSTGRES_DB=product_db -e POSTGRES_USER=product_user -e POSTGRES_PASSWORD=product_password \
      -e SELF_IP="${google_compute_address.vm3_internal.address}" \
      -e SELF_PORT=12345 \
      -e PARTNERS="${local.raft_partners_db_3}" \
      -v product_db_3_data:/var/lib/postgresql/data \
      -v product_db_3_raft:/data/raft \
      product-db:latest

    echo " [vm3] Starting customer-db-3 (node 3, UDP 5100, gRPC 50052) "
    docker run -d --name customer-db-3 --network host --restart unless-stopped \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -e ABP_NODE_ID=3 \
      -e "ABP_PEERS=${local.abp_peers}" \
      -e ABP_UDP_PORT=5100 \
      -e GRPC_PORT=50052 \
      -v customer_db_3_data:/var/lib/postgresql/data \
      customer-db:latest

    echo "[vm3] Waiting for customer-db-3"
    until docker exec customer-db-3 pg_isready -U customer_user -d customer_db 2>/dev/null; do sleep 2; done
    until nc -z localhost 50052; do sleep 2; done

    echo "[vm3] Starting seller-server-2"
    docker run -d --name seller-server-2 --network app-net --restart unless-stopped \
      -p 5000:5000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=5000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm3_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      seller-server:latest

    echo "[vm3] Starting buyer-server-2"
    docker run -d --name buyer-server-2 --network app-net --restart unless-stopped \
      -p 6000:6000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=6000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm3_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      -e FINANCIAL_TRANSACTIONS_HOST=${google_compute_address.vm1_internal.address} \
      -e FINANCIAL_TRANSACTIONS_PORT=8000 \
      buyer-server:latest

    echo "[vm3] Startup complete"
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}

# VM4 — customer-db-4, seller-server-3, buyer-server-3
resource "google_compute_instance" "vm4" {
  name         = "vm4"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["customer-db", "product-db", "ecommerce-app", "ecommerce"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
    }
  }

  network_interface {
    network    = "default"
    subnetwork = "default"
    network_ip = google_compute_address.vm4_internal.address
    access_config {}
  }

  metadata = {
    ssh-keys = var.ssh_public_key
  }

  metadata_startup_script = <<-SCRIPT
    #!/bin/bash
    set -e
    exec > /var/log/startup.log 2>&1

    echo "[vm4] Installing Docker"
    ${local.docker_install}

    echo "[vm4] Cloning repo"
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    echo "[vm4] Building images"
    docker build -t product-db:latest -f services/product-db/Dockerfile .
    docker build -t customer-db:latest   -f services/customer-db/Dockerfile .
    docker build -t seller-server:latest -f services/seller_server/Dockerfile .
    docker build -t buyer-server:latest  -f services/buyer_server/Dockerfile .

    echo "[vm4] Creating bridge network"
    docker network create app-net

    # VM4: product-db-4
    echo " [vm4] Starting product-db-4 (node 2, gRPC 50051, Raft 12345) "
    docker run -d --name product-db-4 --network app-net --restart unless-stopped \
      -p 50051:50051 \
      -p 12345:12345 \
      -e POSTGRES_DB=product_db -e POSTGRES_USER=product_user -e POSTGRES_PASSWORD=product_password \
      -e SELF_IP="${google_compute_address.vm4_internal.address}" \
      -e SELF_PORT=12345 \
      -e PARTNERS="${local.raft_partners_db_4}" \
      -v product_db_4_data:/var/lib/postgresql/data \
      -v product_db_4_raft:/data/raft \
      product-db:latest

    echo "[vm4] Starting customer-db-4 (node 4, UDP 5100, gRPC 50052)"
    docker run -d --name customer-db-4 --network host --restart unless-stopped \
      -e POSTGRES_DB=customer_db \
      -e POSTGRES_USER=customer_user \
      -e POSTGRES_PASSWORD=customer_password \
      -e ABP_NODE_ID=4 \
      -e "ABP_PEERS=${local.abp_peers}" \
      -e ABP_UDP_PORT=5100 \
      -e GRPC_PORT=50052 \
      -v customer_db_4_data:/var/lib/postgresql/data \
      customer-db:latest

    echo "[vm4] Waiting for customer-db-4"
    until docker exec customer-db-4 pg_isready -U customer_user -d customer_db 2>/dev/null; do sleep 2; done
    until nc -z localhost 50052; do sleep 2; done

    echo "[vm4] Starting seller-server-3"
    docker run -d --name seller-server-3 --network app-net --restart unless-stopped \
      -p 5000:5000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=5000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm4_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      seller-server:latest

    echo "[vm4] Starting buyer-server-3"
    docker run -d --name buyer-server-3 --network app-net --restart unless-stopped \
      -p 6000:6000 \
      -e SERVER_HOST=0.0.0.0 \
      -e SERVER_PORT=6000 \
      -e PRODUCT_DB_HOSTS="${local.product_db_hosts}" \
      -e CUSTOMER_DB_HOST=${google_compute_address.vm4_internal.address} \
      -e CUSTOMER_DB_PORT=50052 \
      -e FINANCIAL_TRANSACTIONS_HOST=${google_compute_address.vm1_internal.address} \
      -e FINANCIAL_TRANSACTIONS_PORT=8000 \
      buyer-server:latest

    echo "[vm4] Startup complete"
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
    google_compute_instance.vm1,
    google_compute_instance.vm2,
    google_compute_instance.vm3,
    google_compute_instance.vm4
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
    apt-get install -y python3 python3-pip git curl google-cloud-cli

    echo "=== [test-runner-vm] Waiting for app VMs to finish initializing ==="
    sleep 600

    echo "=== [test-runner-vm] Cloning repo ==="
    git clone ${var.repo_url} /opt/app
    cd /opt/app

    pip3 install requests --break-system-packages

    # Write server addresses to env file for easy sourcing
    # change BUYER_SERVER and SELLER_SERVER
    cat > /opt/app/.env << ENVEOF
export BUYER_SERVER="${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}"
export BUYER_PORT=6000
export SELLER_SERVER="${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}"
export SELLER_PORT=5000
export ZONE="${var.zone}"
export BUYER_SERVERS="${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}:6000,${google_compute_instance.vm2.network_interface[0].access_config[0].nat_ip}:6000,${google_compute_instance.vm3.network_interface[0].access_config[0].nat_ip}:6000,${google_compute_instance.vm4.network_interface[0].access_config[0].nat_ip}:6000"
export SELLER_SERVERS="${google_compute_instance.vm1.network_interface[0].access_config[0].nat_ip}:5000,${google_compute_instance.vm2.network_interface[0].access_config[0].nat_ip}:5000,${google_compute_instance.vm3.network_interface[0].access_config[0].nat_ip}:5000,${google_compute_instance.vm4.network_interface[0].access_config[0].nat_ip}:5000"
ENVEOF
  SCRIPT

  service_account {
    scopes = ["cloud-platform"]
  }
}