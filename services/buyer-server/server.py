import os
import socket
import threading
import uuid

from psycopg2 import _psycopg, extensions, extras, pool

from utils.socket_utils import recv_message, send_message

# Define extension to convert DECIMAL to FLOAT
DEC2FLOAT = extensions.new_type(_psycopg.DECIMAL.values, "DEC2FLOAT", extensions.FLOAT)


class BuyerServer:
    """Server for serving API requests for the buyer API client"""

    def __init__(self, server_host: str = "buyer-server", server_port: int = 6000):
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
            saved_cart_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO buyers (username, passwd, saved_cart_id) VALUES (%s, %s, %s) RETURNING buyer_id",
                (username, password, saved_cart_id),
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
            active_cart_id = str(uuid.uuid4())
            # Create a new session for buyer
            cursor.execute(
                "INSERT INTO buyer_sessions (session_id, buyer_id, active_cart_id) VALUES (%s, %s, %s)",
                (session_id, buyer_id, active_cart_id),
            )
            # Create a new active cart for session
            cursor.execute(
                "INSERT INTO active_carts (active_cart_id, session_id) VALUES (%s, %s)",
                (active_cart_id, session_id),
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
            # Foreign key contraint will delete the active cart too
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
                # Foreign key contraint will delete the active cart too
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
        """Function to get attributes of a specific item by item ID"""
        # Check if session is valid
        session_id = payload.get("session_id")
        if not self.check_if_session_valid(session_id):
            return {
                "status": "Timeout",
                "message": "Session expired. Please log in again.",
            }

        item_id = payload.get("item_id")

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()

        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Query item by item_id
            cursor.execute("SELECT * FROM products WHERE item_id = %s", (item_id,))

            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Item not found."}

            return {"status": "OK", "item": result}
        except Exception as e:
            print(f"Error getting item details: {e}")
            return {"status": "Error", "message": "Failed to get item details."}
        finally:
            self.product_db_pool.putconn(product_db_conn)

    def add_item_to_cart(self, payload: dict):
        """Function to add item to the active cart"""
        # Check if session is valid
        session_id = payload.get("session_id")

        if not self.check_if_session_valid(session_id):
            return {
                "status": "Timeout",
                "message": "Session expired. Please log in again.",
            }

        item_id = payload.get("item_id")
        quantity = payload.get("quantity")

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()
        try:
            cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

            # Validate item_id and quantity
            cursor.execute(
                "SELECT quantity FROM products WHERE item_id = %s", (item_id,)
            )
            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Item ID does not exist."}

            available_quantity = result["quantity"]

            if available_quantity < quantity:
                return {
                    "status": "Error",
                    "message": "Quantity requested is less than available quantity.",
                }
        except Exception as e:
            print(f"Error validating item for adding item to cart: {e}")
        finally:
            self.product_db_pool.putconn(product_db_conn)

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

            # Add item to buyer's active cart if item is missing, else update the quantity for the item
            cursor.execute(
                """
                           UPDATE active_carts
                           SET active_cart_items = jsonb_set(
                                active_cart_items,
                                ARRAY[%s],
                                (COALESCE(active_cart_items->>%s, '0')::int + %s)::text::jsonb,
                                true
                           )
                           WHERE session_id = %s
                        """,
                (str(item_id), str(item_id), quantity, session_id),
            )

            customer_db_conn.commit()
            return {
                "status": "OK",
                "message": f"Item ID {item_id} with quantity {quantity} added to cart.",
            }
        except Exception as e:
            print(f"Error adding item to cart: {e}")
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def remove_item_from_cart(self, payload: dict):
        """Function to add item to the active cart"""
        # Check if session is valid
        session_id = payload.get("session_id")

        if not self.check_if_session_valid(session_id):
            return {
                "status": "Timeout",
                "message": "Session expired. Please log in again.",
            }

        item_id = payload.get("item_id")
        quantity = payload.get("quantity")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()
        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT (active_cart_items->>%s)::int AS cart_quantity FROM active_carts WHERE session_id = %s",
                (str(item_id), session_id),
            )
            result = cursor.fetchone()

            cart_quantity = result["cart_quantity"]

            if cart_quantity is None:
                return {"status": "Error", "message": "Item ID does not exist in cart"}

            # Delete the item_id key from active cart items
            if cart_quantity == quantity:
                cursor.execute(
                    "UPDATE active_carts SET active_cart_items = active_cart_items - %s WHERE session_id = %s",
                    (str(item_id), session_id),
                )
                customer_db_conn.commit()
                return {
                    "status": "OK",
                    "message": f"Quantity to remove is equal to quantity in cart. Removed item ID {item_id} from cart.",
                }

            # Remove item from buyer's active cart if its quantity in the cart is more than the quantity to be removed
            # the AND check is just to be extra cautious - the above conditions should ensure that available quantity > quantity to be removed
            cursor.execute(
                """
                           UPDATE active_carts
                           SET active_cart_items = jsonb_set(
                                active_cart_items,
                                ARRAY[%s],
                                ((active_cart_items->>%s)::int - %s)::text::jsonb
                           )
                           WHERE session_id = %s
                           AND (active_cart_items->>%s)::int > %s
                        """,
                (
                    str(item_id),
                    str(item_id),
                    quantity,
                    session_id,
                    str(item_id),
                    quantity,
                ),
            )
            customer_db_conn.commit()
            return {
                "status": "OK",
                "message": f"Item ID {item_id} with quantity {quantity} added to cart.",
            }
        except Exception as e:
            print(f"Error adding item to cart: {e}")
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def save_cart(self, payload: dict):
        pass

    def clear_cart(self, payload: dict):
        pass

    def display_cart(self, payload: dict):
        pass

    def make_purchase(self, payload: dict):
        pass

    def provide_feedback(self, payload: dict):
        """Function to provide feedback (thumbs up or thumbs down) for an item and accordingly update seller feedback"""
        # Check if session is valid
        session_id = payload.get("session_id")
        if not self.check_if_session_valid(session_id):
            return {
                "status": "Timeout",
                "message": "Session expired. Please log in again.",
            }

        item_id = payload.get("item_id")
        feedback = payload.get("feedback")  # Expecting 0 or 1
        if feedback not in [0, 1]:
            return {
                "status": "Error",
                "message": "Invalid feedback value. Must be 0 or 1.",
            }

        # Get a connection from the product DB pool
        product_db_conn = self.product_db_pool.getconn()
        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            product_cursor = product_db_conn.cursor(
                cursor_factory=extras.RealDictCursor
            )
            customer_cursor = customer_db_conn.cursor(
                cursor_factory=extras.RealDictCursor
            )
            # Query item to get seller_id
            product_cursor.execute(
                "SELECT seller_id FROM products WHERE item_id = %s", (item_id,)
            )
            item_result = product_cursor.fetchone()
            if not item_result:
                return {
                    "status": "Error",
                    "message": f"Item with ID {item_id} not found.",
                }

            seller_id = item_result["seller_id"]
            # Update seller feedback
            if feedback == 1:
                product_cursor.execute(
                    "UPDATE products SET thumbs_up = thumbs_up + 1 WHERE item_id = %s",
                    (item_id,),
                )
                customer_cursor.execute(
                    "UPDATE sellers SET thumbs_up = thumbs_up + 1 WHERE seller_id = %s",
                    (seller_id,),
                )
            else:
                product_cursor.execute(
                    "UPDATE products SET thumbs_down = thumbs_down + 1 WHERE item_id = %s",
                    (item_id,),
                )
                customer_cursor.execute(
                    "UPDATE sellers SET thumbs_down = thumbs_down + 1 WHERE seller_id = %s",
                    (seller_id,),
                )

            product_db_conn.commit()
            customer_db_conn.commit()

            return {"status": "OK", "message": "Feedback recorded successfully."}

        except Exception as e:
            print(f"Error providing feedback: {e}")
            return {"status": "Error", "message": "Failed to provide feedback."}

        finally:
            self.product_db_pool.putconn(product_db_conn)
            self.customer_db_pool.putconn(customer_db_conn)

    def get_seller_rating(self, payload: dict):
        """Function to get the seller rating for the given seller ID"""
        # Check if session is valid
        session_id = payload.get("session_id")
        if not self.check_if_session_valid(session_id):
            return {
                "status": "Timeout",
                "message": "Session expired. Please log in again.",
            }

        seller_id = payload.get("seller_id")

        # Get a connection from the customer DB pool
        customer_db_conn = self.customer_db_pool.getconn()

        try:
            cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)
            # Query seller by seller_id
            cursor.execute(
                "SELECT thumbs_up, thumbs_down FROM sellers WHERE seller_id = %s",
                (seller_id,),
            )

            result = cursor.fetchone()
            if not result:
                return {"status": "Error", "message": "Seller not found."}

            return {
                "status": "OK",
                "thumbs_up": result["thumbs_up"],
                "thumbs_down": result["thumbs_down"],
            }
        except Exception as e:
            print(f"Error getting seller rating: {e}")
            return {"status": "Error", "message": "Failed to get seller rating."}
        finally:
            self.customer_db_pool.putconn(customer_db_conn)

    def get_buyer_purchases(self, payload: dict):
        """Stubbed function to get the buyer's purchase history"""
        return {"status": "OK", "purchases": {}}

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
    server_host = os.getenv("SERVER_HOST", "buyer-server")
    server_port = int(os.getenv("SERVER_PORT", "6000"))

    server = BuyerServer(server_host, server_port)
    server.run()


if __name__ == "__main__":
    main()
