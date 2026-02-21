# distributed-systems-programming-assignments
Repository containing all the programming assignments for CSCI-5673: Distributed Systems Spring 2026.

# Programming Assignment 1

## System Design

The overall system is structured logically as follows:

Container 1: Seller CLI + API Client (Seller Frontend)

Container 2: Seller Server (Seller Backend)

Container 3: Buyer CLI + API Client (Buyer Frontend)

Container 4: Buyer Server (Buyer Backend)

Container 5: customer-db

Container 6: product-db

Each process runs as a Docker container. The `docker-compose.yml` file has the setup to manage all containers.

The database nodes run PostgreSQL databases.

All communication between the frontend and backend are happening through TCP sockets. All the messages are length-prefixed, which means that the first 4 bytes of each message contains the length of the message in bytes. The receiver of the message reads the first 4 bytes, determines the message length, say x, and then proceeds to read the next x bytes.

### Search Items Semantics

The `SearchItems` operation on the buyer interface filters items using a two-stage approach, where the `category` column takes precedence over the `keywords` column:

1. **Category filtering**: Items are first filtered by the category parameter
2. **Keyword filtering**: From the category-filtered results, items containing any of the provided keywords are returned

**Example**:
- Input: Category = 0, Keywords = ["Black", "Keyboard"]
- Output: All items in category 0 that contain either "Black" OR "Keyboard" (or both) in the keywords column
### Session Management
Buyer and Seller sessions are being maintained on the backend by the server, by maintaining two tables in the customer database - `buyer_sessions` and `seller_sessions`. The schemas for the two tables are as follows:

![Buyer Sessions Schema](images/buyer_sessions.png "Buyer Sessions Schema")

![Seller Sessions Schema](images/seller_sessions.png "Seller Sessions Schema")

When a user (buyer or seller) logs into their account, the server generates a new `session_id` and stores it in the respective sessions table along with the current timestamp (`NOW()`). The `session_id` is then returned to the frontend to display the "logged in" menu.
                  
Everytime the user performs an operation (like `GetItems`), the server first checks the sessions table to see if the session is still valid, by checking that the time-interval between the `last_active_at` timestamp and the current timestamp is less than 5 minutes. If the session is valid, the server updates the `last_active_at` timestamp and continues with the operation. Else it deletes the row from the sessions table and sends a "session timeout" message to the frontend. The frontend then flushes the session and displays the "logged out" menu.

### Cart Management

Carts are managed for buyers.
Two tables maintain carts for a buyer - `active_carts` and `saved_carts`. The table schema contains cart id, buyer id or session id, and a json of `{item_id : quantity}` key-value pairs.

An active cart is associated to a specific session and a saved cart is associated to a specific buyer.

When a buyer creates a new account, the buyer server creates a new entry in the buyers table with a new saved cart ID.

When a new session is created, the buyer server creates a new session entry in the sessions table with a new active cart ID.

When a session terminates, the session row is deleted and the delete is cascaded to delete the corresponding active cart. 

On buyer login, if the buyer's saved cart contains items, then these items are loaded into the new active cart. Otherwise, an empty active cart is created.

Add to cart, remove from cart, and display cart operations are performed on the active cart. Save cart saves the overwrites the active cart items over the saved cart items of that buyer. Clear cart clears both the active cart and the saved cart.

## Assumptions:

1. API client requests a TCP connection to the server when the client is initialised.
It then ensures that there is an active connection by sending requests to the server via
`send_message_with_reconnect`. This method first checks if there is an active connection still. If not, it makes one retry attempts to send a new TCP connection request to the server. So, we make an assumption here that the single retry will create a new successful connection to the server 

    Optimization: Adding multiple retries with exponential backoff

2. Implementation detail: Clear Cart clears the active cart as well as the saved cart

3. Save Cart: save cart is implemented to overwrite the current save cart with the current active cart. Ordering of save cart across sessions is not considered.

    Optimization: Implement some locking mechanism


# Programming Assignment 2

## System Design

For this assignment, the overall system is structured logically the same as in Programming Assignment 1 and is as follows:

Container 1: Seller CLI + API Client (Seller Frontend)

Container 2: Seller Server (Seller Backend)

Container 3: Buyer CLI + API Client (Buyer Frontend)

Container 4: Buyer Server (Buyer Backend)

Container 5: Financial Transactions SOAP/WSDL payment processor 

Container 6: customer-db

Container 7: product-db

As directed, the communication layers have been updated for this assignment:
1. Frontend -> Server: Changed from TCP sockets to REST APIs (HTTP)
2. Server -> Database: Changed from TCP sockets to gRPC

The buyer and seller servers are now Flask applications that handle HTTP requests from their respective clients. All inter-service communication between the servers and the databases is handled via gRPC stubs generated from .proto definitions.

Each component is deployed as a separate Google Compute Engine (GCE) VM, provisioned automatically via Terraform. Each VM's startup script installs Docker, clones the repository, builds the relevant Docker image, and starts the container on boot.

The financial transactions service is a SOAP-based service which has a process_payment rpc which takes credit card details of the buyer as returns "Yes" with 90% probability and "No" with 10% probability.

The buyer server container and the financial-transactions service container share a Docker network (buyer-net) on buyer-server-vm, allowing them to communicate by container name.

The database VMs communicate with the application servers over GCP's internal VPC network using private IPs. The seller and buyer servers are reachable externally via their external public IPs.

## Make and Get Buyer Purchases

PA2 includes the implmentation of the MakePurchase and GetBuyerPurchases options for the buyer.

Two tables are created to manage purchases:
- Transaction table: stores the buyer id, transaction id, and credit card details used for the transaction
- Purchases table: To make it easier to get the items IDs for a buyer's history of purchases, purchases table is creates which stores the buyer id, purchase id, transaction id, and the list of item IDs associated with the transaction.

### MakePurchase

- Buyer CLI prompts the input of card holder name, credit card number, expiry month, expiry year, and security code and sends the request to the Buyer API Client. 
  - We decided to treat the name on card as separate from the buyer username because they may not always be the same. 
  - The CLI performs input validation
    - Card number must be 16 characters
    - Expiry month must be an integer between 1 and 12
    - Expiry year must be an integer between 1000 and 9999
    - Security code must be 3 characters
- Buyer API Client sends a HTTP POST request to the Buyer Server's `/api/buyers/purchases` REST endpoint
- Buyer Server:
   - Gets the saved card items for the buyer
   - Verifies that the quantity of items in the saved card are available in the product catalog
   - Calls the process payment rpc of the Financial Transactions service with the credit card details of the request.
- The Financial Transaction server returns a Yes indicating a successful payment or No indication a failed payment
- If the response in No, the Buyer Server returns a Payment Declined response
- If the response is Yes, the Buyer Server:
  - Inserts a new transaction entry into the transactions table in the customer db which has the buyer id, credit card details, and the total amount calculated as `amount += quantity[i] * item_sale_price[i]` for each item i in the saved cart
  - Inserts a new purchase into the purchases table with the list of items ids bought, buyer id, and transaction id.
  - Decrements the quantity of the available items in the product catalog
  - Returns a Payment Successful response with the transaction ID and the puchase ID.

### Get Buyer Purchases

- Buyer CLI sends the session details to the buyer API client
- Buyer API Client sends a HTTP GET request to the Buyer Server's `/api/buyers/purchases` REST endpoint
- Buyer server makes a call to the gRPC endpoint of the customer db server.
- gRPC server returns the purchases from the purchases table for the buyer id
- Buyer server returns the HTTP response with the purchases
- Buyer CLI displays the buyer's purchase history as purchase ID and the list of items IDS for each purchase ID

## Current state

All the APIs have been tested and are working.

## Reproduction Commands

### Local setup
Terminal 1:
```
sh build_containers.sh
docker-compose ps
```
### Deploy to GCE instances
Terminal 1:
```
cd terraform
terraform init
``` 
Create a terraform.tfvars file containing the project ID of the GCP project as follows:
```
project_id = "<gcp_project_id>"
```

Run the following command to deploy to GCE VMs
```
terraform apply -var-file="terraform.tfvars"
```


### Debug Commands

Terminal 4:
```
docker exec -it product_db_container psql -U product_user -d product_db
```

Terminal 5:
```
docker exec -it buyer_client_container python buyer_cli.py
```

### GCE creation commands:

Setup project and authenticate to gcloud with

`gcloud auth login`

Create a new VM instance

```
gcloud compute instances create pa1-vm \
  --zone=us-west1-b \
  --machine-type=e2-medium \
  --boot-disk-size=20GB \
  --image-family=ubuntu-2204-lts \
  --tags=pa1 \
  --image-project=ubuntu-os-cloud \
  --metadata=startup-script='#!/bin/bash
    apt-get update
    apt-get install -y docker.io docker-compose
    apt-get install -y git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker $USER
    apt-get install -y curl wget vim'
```

Setup firewall rules to allow traffic to server ports on the VM

```
gcloud compute firewall-rules create allow-seller-server \
  --allow=tcp:5001 \
  --target-tags=pa1 \
  --description="Allow traffic on seller server port 5001" \
  --direction=INGRESS
```

```
gcloud compute firewall-rules create allow-buyer-server \
  --allow=tcp:6001 \
  --target-tags=pa1 \
  --description="Allow traffic on buyer server port 6001" \
  --direction=INGRESS
```

SSH to GCE:
```
gcloud compute ssh pa1-vm --zone=us-west1-b
```

Inside the SSH session, clone repository:
```
git clone https://github.com/anirudhragam/distributed-systems-programming-assignments.git
```

Setup docker user
```
sudo usermod -aG docker $USER
```

Bring up services:
```
cd services
sudo chmod +x build_containers.sh
git pull
bash build_containers.sh
```

Run performance tests:
```
python performance_tests.py --num-sellers 1 --num-buyers 1 > results_1x1.txt 2>&1 | tee results_1x1.txt

python performance_tests.py --num-sellers 10 --num-buyers 10 > results_10x10.txt 2>&1 | tee results_10x10.txt

python performance_tests.py --num-sellers 100 --num-buyers 100 > results_100x100.txt 2>&1 | tee results_100x100.txt
```

### Generate gRPC code

python -m grpc_tools.protoc -I./protos --python_out=./generated --grpc_python_out=./generated ./protos/customer_db.proto

python -m grpc_tools.protoc -I./protos --python_out=./generated --grpc_python_out=./generated ./protos/product_db.proto


### Commands to run and debug tests in test VM
gcloud compute ssh test-runner-vm --zone=us-west1-a
cd /opt/app && source .env
curl -v http://$SELLER_SERVER:5000/api/health
python3 performance_tests.py --num-sellers 1 --num-buyers 1 > ~/results_1x1.txt 2>&1 | tee ~/results_1x1.txt
bash reset_dbs.sh

python3 performance_tests.py --num-sellers 10 --num-buyers 10 2>&1 | tee ~/results_10x10.txt
bash reset_dbs.sh

python3 performance_tests.py --num-sellers 100 --num-buyers 100 2>&1 | tee ~/results_100x100.txt
bash reset_dbs.sh


gcloud compute ssh seller-server-vm --zone=us-west1-a --command="sudo docker logs seller-server"

gcloud compute ssh buyer-server-vm --zone=us-west1-a --command="sudo docker logs buyer-server"

gcloud compute ssh buyer-server-vm --zone=us-west1-a --command="sudo docker logs buyer-grpc-server"








