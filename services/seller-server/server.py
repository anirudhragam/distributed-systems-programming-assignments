import os
import socket
from utils.socket_utils import send_message, recv_message
import psycopg2
from psycopg2 import pool
import threading

class SellerServer:
    """Server for serving API requests for the server API client"""

    def __init__(self, server_host: str = "localhost", server_port: int = 5000):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = self.listen()

        # TODO: use constants or env variables for DB connection params
        self.product_db_pool = pool.ThreadedConnectionPool(
            minconn = 1,
            maxconn = 25,
            user = "product_user",
            password = "product_pass",
            host = "product-db",
            port = "5432",
            database = "product_db"
        )
        self.customer_db_pool = pool.ThreadedConnectionPool(
            minconn = 1,
            maxconn = 25,
            user = "customer_user",
            password = "customer_pass",
            host = "customer-db",
            port = "5433",
            database = "customer_db"
        )

    def listen(self):
        """Function to listen for incoming TCP connection requests on the specified host and port"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.server_host, self.server_port))
            self.socket.listen(10) # Change number of backlog connections, if needed
            print(f"Seller server listening on {self.server_host}:{self.server_port}")
        except Exception as e:
            print(f"Error server unable to listen on {self.server_host}:{self.server_port}: {e}")
            self.socket = None

    def create_account(self, payload: dict):
        """Function to create a new seller account, if it does not already exist."""
        username = payload.get("username")
        password = payload.get("password")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor()
            # Check if username already exists
            cursor.execute("SELECT seller_id FROM sellers WHERE username = %s", (username,))
            result = cursor.fetchone()
            if result:
                return {"status": "Error", "message": "Username already exists."}

            # Insert new seller into the database
            cursor.execute(
                "INSERT INTO sellers (username, password) VALUES (%s, %s) RETURNING seller_id",
                (username, password)
            )
            seller_id = cursor.fetchone()[0]
            customer_db_conn.commit()
            return {"status": "OK", "seller_id": seller_id}
        except Exception as e:
            print(f"Error creating seller account: {e}")
            return {"status": "Error", "message": "Failed to create account."}
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def login(self, payload: dict):
        pass
    
    def handle_request(self, connection, addr):
        """Function to handle incoming client requests. Executed in a separate thread for each connection."""
        print(f"Connection accepted from seller client {addr}")
        with connection:
            while True:
                try:
                    payload = recv_message(connection)
                    if payload["operation"] == "CreateAccount":
                        response = self.create_account(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "Login":
                        response = self.login(payload)
                        send_message(connection, response)
                    else:
                        pass

                    
                except Exception as e:
                    print(f"Error receiving message from {addr}: {e}")
                    break

        

    def run(self):
        """Main function for seller server to accept incoming connections and spawn threads to handle them"""
        if not self.socket:
            print("Listening failed.")
            return

        while True:
            connection, addr = self.socket.accept()
            thread = threading.Thread(target=self.handle_request, args=(connection, addr))
            thread.daemon = True # Cleanly exit threads on main program exit
            thread.start()



def main():
    """Entry point for the seller server"""
    server_host = os.getenv("SERVER_HOST", "localhost")
    server_port = int(os.getenv("SERVER_PORT", "5000"))

    server = SellerServer(server_host, server_port)
    server.run()

if __name__ == "__main__":
    main()