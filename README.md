# distributed-systems-programming-assignments
Repository containing all the programming assignments for CSCI-5673: Distributed Systems Spring 2026.

Terminal 1:
sh build_containers.sh
docker-compose ps

Terminal 2:
docker exec -it seller_client_container python seller_cli.py

Terminal 3:
docker exec -it customer_db_container psql -U customer_user -d customer_db

Terminal 4:
docker exec -it product_db_container psql -U product_user -d product_db

Terminal 5:
docker exec -it buyer_client_container python buyer_cli.py