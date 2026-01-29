import os
import socket
import threading
import uuid
from hmac import new

from psycopg2 import _psycopg, extensions, extras, pool

from utils.socket_utils import recv_message, send_message

# Define extension to convert DECIMAL to FLOAT
DEC2FLOAT = extensions.new_type(_psycopg.DECIMAL.values, "DEC2FLOAT", extensions.FLOAT)


class BuyerServer:
    """Server for serving API requests for the buyer API client"""

    def __init__(self, server_host: str = "localhost", server_port: int = 6000):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = self.listen()

        # TODO: use constants or env variables for DB connection params
        self.product_db_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=25,
            user="product_user",
            password="product_password",
            host="product-db",
            port="5432",
            database="product_db",
        )
        self.customer_db_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=25,
            user="customer_user",
            password="customer_password",
            host="customer-db",
            port="5432",
            database="customer_db",
        )
        # register uuid extension
        extras.register_uuid()
        # register decimal to float extension
        extensions.register_type(DEC2FLOAT)

    def listen(self):
        """Function to listen for incoming TCP connection requests on the specified host and port"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.server_host, self.server_port))
            self.socket.listen(10)  # Change number of backlog connections, if needed
            print(f"Buyer server listening on {self.server_host}:{self.server_port}")
            return self.socket
        except Exception as e:
            print(
                f"Error server unable to listen on {self.server_host}:{self.server_port}: {e}"
            )
            self.socket = None
            return None

    def create_account(self, payload: dict):
        """Function to create a new buyer account, if it does not already exist."""
        username = payload.get("username")
        password = payload.get("password")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Check if username already exists
            cursor.execute(
                "SELECT buyer_id FROM buyers WHERE username = %s", (username,)
            )
            result = cursor.fetchone()
            if result:
                return {"status": "Error", "message": "Username already exists."}

            # Insert new buyer into the database
            cursor.execute(
                "INSERT INTO buyers (username, passwd) VALUES (%s, %s) RETURNING buyer_id",
                (username, password),
            )
            buyer_id = cursor.fetchone()["buyer_id"]
            customer_db_conn.commit()
            return {"status": "OK", "buyer_id": buyer_id}
        except Exception as e:
            print(f"Error creating buyer account: {e}")
            return {"status": "Error", "message": "Failed to create account."}
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def login(self, payload: dict):
        username = payload.get("username")
        password = payload.get("password")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Check if username already exists
            cursor.execute(
                "SELECT buyer_id, username FROM buyers WHERE username = %s AND passwd = %s",
                (username, password),
            )
            result = cursor.fetchone()
            if not result:
                return {
                    "status": "Error",
                    "message": "Username/Password combination does not exist.",
                }

            buyer_id = result["buyer_id"]
            username = result["username"]

            # Create a new session and add it to the buyer_sessions table
            session_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO buyer_sessions (session_id, buyer_id) VALUES (%s, %s)",
                (session_id, buyer_id),
            )

            customer_db_conn.commit()
            return {
                "status": "OK",
                "session_id": session_id,
                "buyer_id": buyer_id,
                "message": f"I've seen enough. Welcome back {username}",
            }
        except Exception as e:
            print(f"Error logging into buyer account: {e}")
            return {"status": "Error", "message": "Failed to log in to buyer account."}
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def logout(self, payload: dict):
        """Function to logout of a buyer session"""
        session_id = payload.get("session_id")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Delete the session from the buyer_sessions table
            cursor.execute(
                "DELETE FROM buyer_sessions WHERE session_id = %s", (session_id,)
            )
            customer_db_conn.commit()
            return {"status": "OK", "message": "Successfully logged out."}

        except Exception as e:
            print(f"Error logging out of buyer session: {e}")
            return {"status": "Error", "message": "Failed to log out of buyer session."}

    def check_if_session_valid(self, session_id: str):
        """Function to check if a given session has not expired"""
        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Check if session ID exists
            cursor.execute(
                "SELECT buyer_id FROM buyer_sessions WHERE session_id = %s AND last_active_at > NOW() - INTERVAL '5 minutes'",
                (session_id,),
            )

            result = cursor.fetchone()
            print(f"Session check result: {result}")
            if not result:
                # Session expired, delete from buyer_sessions table and return False
                print("Deleting expired session")
                cursor.execute(
                    "DELETE FROM buyer_sessions WHERE session_id = %s", (session_id,)
                )
                customer_db_conn.commit()
                return False

            # Session valid, update last_active_at timestamp
            cursor.execute(
                "UPDATE buyer_sessions SET last_active_at = NOW() WHERE session_id = %s",
                (session_id,),
            )
            customer_db_conn.commit()
            return True

        except Exception as e:
            print(f"Error checking session validity: {e}")
            return False

        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def search_items(self, payload: dict):
        pass

    def get_item(self, payload: dict):
        pass

    def add_item_to_cart(self, payload: dict):
        pass

    def remove_item_from_cart(self, payload: dict):
        pass

    def save_cart(self, payload: dict):
        pass

    def clear_cart(self, payload: dict):
        pass

    def display_cart(self, payload: dict):
        pass

    def make_purchase(self, payload: dict):
        pass

    def provide_feedback(self, payload: dict):
        pass

    def get_seller_rating(self, payload: dict):
        pass

    def get_buyer_purchases(self, payload: dict):
        pass

    def handle_request(self, connection, addr):
        """Function to handle incoming client requests. Executed in a separate thread for each connection."""
        print(f"Connection accepted from buyer client {addr}")
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
                    elif payload["operation"] == "Logout":
                        response = self.logout(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "SearchItemsForSale":
                        response = self.search_items(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "GetItem":
                        response = self.get_item(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "AddItemToCart":
                        response = self.add_item_to_cart(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "RemoveItemFromCart":
                        response = self.remove_item_from_cart(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "SaveCart":
                        response = self.save_cart(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "ClearCart":
                        response = self.clear_cart(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "DisplayCart":
                        response = self.display_cart(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "MakePurchase":
                        response = self.make_purchase(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "ProvideFeedback":
                        response = self.provide_feedback(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "GetSellerRating":
                        response = self.get_seller_rating(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "GetBuyerPurchases":
                        response = self.get_buyer_purchases(payload)
                        send_message(connection, response)
                    else:
                        response = {"status": "Error", "message": "Invalid operation."}
                        send_message(connection, response)
                except Exception as e:
                    print(f"Error receiving message from {addr}: {e}")
                    break

    def run(self):
        """Main function for buyer server to accept incoming connections and spawn threads to handle them"""
        if not self.socket:
            print("Listening failed.")
            return

        while True:
            connection, addr = self.socket.accept()
            thread = threading.Thread(
                target=self.handle_request, args=(connection, addr)
            )
            thread.daemon = True  # Cleanly exit threads on main program exit
            thread.start()


def main():
    """Entry point for the buyer server"""
    server_host = os.getenv("SERVER_HOST", "localhost")
    server_port = int(os.getenv("SERVER_PORT", "6000"))

    server = BuyerServer(server_host, server_port)
    server.run()


if __name__ == "__main__":
    main()
