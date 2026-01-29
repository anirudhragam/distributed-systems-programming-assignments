from hmac import new
import os
import socket

from utils.socket_utils import send_message, recv_message
from psycopg2 import pool, extras, extensions, _psycopg
import threading
import uuid

# Define extension to convert DECIMAL to FLOAT
DEC2FLOAT = extensions.new_type(
    _psycopg.DECIMAL.values,
    'DEC2FLOAT',
    extensions.FLOAT
)

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
            password = "product_password",
            host = "product-db",
            port = "5432",
            database = "product_db"
        )
        self.customer_db_pool = pool.ThreadedConnectionPool(
            minconn = 1,
            maxconn = 25,
            user = "customer_user",
            password = "customer_password",
            host = "customer-db",
            port = "5432",
            database = "customer_db"
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
            self.socket.listen(10) # Change number of backlog connections, if needed
            print(f"Seller server listening on {self.server_host}:{self.server_port}")
            return self.socket
        except Exception as e:
            print(f"Error server unable to listen on {self.server_host}:{self.server_port}: {e}")
            self.socket = None
            return None

    def create_account(self, payload: dict):
        """Function to create a new seller account, if it does not already exist."""
        username = payload.get("username")
        password = payload.get("password")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Check if username already exists
            cursor.execute("SELECT seller_id FROM sellers WHERE username = %s", (username,))
            result = cursor.fetchone()
            if result:
                return {"status": "Error", "message": "Username already exists."}

            # Insert new seller into the database
            cursor.execute(
                "INSERT INTO sellers (username, passwd) VALUES (%s, %s) RETURNING seller_id",
                (username, password)
            )
            seller_id = cursor.fetchone()['seller_id']
            customer_db_conn.commit()
            return {"status": "OK", "seller_id": seller_id}
        except Exception as e:
            print(f"Error creating seller account: {e}")
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
            cursor.execute("SELECT seller_id, username FROM sellers WHERE username = %s AND passwd = %s", (username, password))
            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Username/Password combination does not exist."}

            seller_id = result['seller_id']
            username = result['username']

            # Create a new session and add it to the seller_sessions table
            session_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO seller_sessions (session_id, seller_id) VALUES (%s, %s)", (session_id, seller_id))

            customer_db_conn.commit()
            return {"status": "OK", "session_id": session_id, "seller_id": seller_id, "message": f"I've seen enough. Welcome back {username}"}
        except Exception as e:
            print(f"Error logging into seller account: {e}")
            return {"status": "Error", "message": "Failed to log in to seller account."}
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def logout(self, payload: dict):
        """Function to logout of a seller session"""
        session_id = payload.get("session_id")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Delete the session from the seller_sessions table
            cursor.execute("DELETE FROM seller_sessions WHERE session_id = %s", (session_id,))
            customer_db_conn.commit()
            return {"status": "OK", "message": "Successfully logged out."}
        
        except Exception as e:
            print(f"Error logging out of seller session: {e}")
            return {"status": "Error", "message": "Failed to log out of seller session."}
        
    def check_if_session_valid(self, session_id: str):
        """Function to check if a given session has not expired""" 
        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Check if session ID exists
            # print("SELECT seller_id FROM seller_sessions WHERE session_id = %s AND last_active_at > NOW() - INTERVAL '5 minutes'", (session_id,))
            cursor.execute("SELECT seller_id FROM seller_sessions WHERE session_id = %s AND last_active_at > NOW() - INTERVAL '2 minutes'", (session_id,))

            result = cursor.fetchone()
            print(f"Session check result: {result}")
            if not result:
                # Session expired, delete from seller_sessions table and return False
                print("Deleting expired session")
                cursor.execute("DELETE FROM seller_sessions WHERE session_id = %s", (session_id,))
                customer_db_conn.commit()
                return False
            
            # Session valid, update last_active_at timestamp
            cursor.execute("UPDATE seller_sessions SET last_active_at = NOW() WHERE session_id = %s", (session_id,))
            customer_db_conn.commit()
            return True
        
        except Exception as e:
            print(f"Error checking session validity: {e}")
            return False
        
        finally:
            self.customer_db_pool.putconn(customer_db_conn)    


    def get_seller_rating(self, payload: dict):
        """Function to get the seller rating for seller ID associated with current session"""
        # Check if session is valid
        session_id = payload.get("session_id")
        seller_id = payload.get("seller_id")

        if not self.check_if_session_valid(session_id):
            return {"status": "Timeout", "message": "Session expired. Please log in again."}

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

            # Fetch thumbs up and thumbs down counts
            cursor.execute("SELECT thumbs_up, thumbs_down FROM sellers WHERE seller_id = %s",(seller_id,))
            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Seller ID does not exist."}

            thumbs_up, thumbs_down = result['thumbs_up'], result['thumbs_down']

            return {"status": "OK", "thumbs_up": thumbs_up, "thumbs_down": thumbs_down}
        
        except Exception as e:
            print(f"Error getting seller rating: {e}")
            return {"status": "Error", "message": "Failed to get seller rating."}
        
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def register_item_for_sale(self, payload: dict):
        """Function to register a new item for sale"""
        # Check if session is valid
        session_id = payload.get("session_id")
        seller_id = payload.get("seller_id")

        if not self.check_if_session_valid(session_id):
            return {"status": "Timeout", "message": "Session expired. Please log in again."}
        
        item_name = payload.get("item_name")
        category = payload.get("category")
        keywords = payload.get("keywords")
        condition = payload.get("condition")
        sale_price = payload.get("sale_price")
        quantity = payload.get("quantity")

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()

        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Insert new item into the products table
            cursor.execute(
                "INSERT INTO products (seller_id, item_name, category, keywords, condition, sale_price, quantity) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING item_id",
                (seller_id, item_name, category, keywords, condition, sale_price, quantity)
            )
            item_id = cursor.fetchone()['item_id']
            product_db_conn.commit()
            return {"status": "OK", "message": f"Item {item_name} registered for sale successfully with Item ID {item_id}"}
        except Exception as e:
            print(f"Error registering item for sale: {e}")
            return {"status": "Error", "message": "Failed to register item for sale."}
        finally:
            self.product_db_pool.putconn(product_db_conn)

    def change_item_price(self, payload: dict):
        """Function to change the price of an item for sale"""
        # Check if session is valid
        session_id = payload.get("session_id")
        seller_id = payload.get("seller_id")

        if not self.check_if_session_valid(session_id):
            return {"status": "Timeout", "message": "Session expired. Please log in again."}
        
        item_id = payload.get("item_id")
        new_price = payload.get("new_price")

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()

        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Update the item price
            cursor.execute("UPDATE products SET sale_price = %s WHERE item_id = %s AND seller_id = %s", (new_price, item_id, int(seller_id)))
            if cursor.rowcount == 0:
                return {"status": "Error", "message": "Item ID does not exist or does not belong to the seller."}
            product_db_conn.commit()
            return {"status": "OK", "message": f"Item price for item {item_id} updated successfully to {new_price}"}
        except Exception as e:
            print(f"Error changing item price: {e}")
            return {"status": "Error", "message": "Failed to change item price."}
        finally:
            self.product_db_pool.putconn(product_db_conn)

    def update_units_for_sale(self, payload: dict):
        """Function to update the number of units available for sale for an item"""
        # Check if session is valid
        session_id = payload.get("session_id")
        seller_id = payload.get("seller_id")

        if not self.check_if_session_valid(session_id):
            return {"status": "Timeout", "message": "Session expired. Please log in again."}
        
        item_id = payload.get("item_id")
        quantity_change = payload.get("quantity_change")

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()

        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Fetch current quantity
            cursor.execute("SELECT quantity FROM products WHERE item_id = %s AND seller_id = %s", (item_id, seller_id))
            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Item ID does not exist or does not belong to the seller."}

            current_quantity = result['quantity']
            new_quantity = current_quantity - quantity_change

            if new_quantity < 0:
                return {"status": "Error", "message": "Available units cannot be negative."}
            
            # Update the item quantity
            cursor.execute("UPDATE products SET quantity = %s WHERE item_id = %s AND seller_id = %s", (new_quantity, item_id, int(seller_id)))
            product_db_conn.commit()
            return {"status": "OK", "message": f"Item quantity for item {item_id} updated successfully to {new_quantity}"}
        except Exception as e:
            print(f"Error updating item quantity: {e}")
            return {"status": "Error", "message": "Failed to update item quantity."}
        finally:
            self.product_db_pool.putconn(product_db_conn)

    def display_items_for_sale(self, payload: dict):
        # Check if session is valid
        session_id = payload.get("session_id")
        seller_id = payload.get("seller_id")

        if not self.check_if_session_valid(session_id):
            return {"status": "Timeout", "message": "Session expired. Please log in again."}
        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()    

        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("SELECT item_id, item_name, category, keywords, condition, sale_price::float, quantity, thumbs_up, thumbs_down FROM products WHERE seller_id = %s AND quantity > 0", (seller_id,))
            items = cursor.fetchall()
            if not items:
                return {"status": "OK", "message": "No items for sale."}
            return {"status": "OK", "items": items}
        except Exception as e:
            print(f"Error displaying items for sale: {e}")
            return {"status": "Error", "message": "Failed to display items for sale."}
        finally:
            self.product_db_pool.putconn(product_db_conn)

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
                    elif payload["operation"] == "Logout":
                        response = self.logout(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "GetSellerRating":
                        response = self.get_seller_rating(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "RegisterItemForSale":
                        response = self.register_item_for_sale(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "ChangeItemPrice":
                        response = self.change_item_price(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "UpdateUnitsForSale":
                        response = self.update_units_for_sale(payload)
                        send_message(connection, response)
                    elif payload["operation"] == "DisplayItemsForSale":
                        response = self.display_items_for_sale(payload)
                        send_message(connection, response)
                    else:
                        response = {"status": "Error", "message": "Invalid operation."}
                        send_message(connection, response)
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