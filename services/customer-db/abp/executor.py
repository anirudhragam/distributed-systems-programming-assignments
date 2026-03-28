
import json
import logging

from psycopg2 import extras

logger = logging.getLogger(__name__)


class SQLExecutor:
    def __init__(self, db_pool):
        # psycopg2 connection pool for executing SQL queries. Passed in from grpc_server.py
        self.db_pool = db_pool
        self.handlerMap = {
            # Seller
            "CreateSeller": self.create_seller,
            "SellerLogin": self.seller_login,
            "SellerLogout": self.seller_logout,
            "UpdateSellerFeedback": self.update_seller_feedback,
            "UpdateSellerSessionTimestamp": self.update_seller_session_timestamp,
            # Buyer
            "CreateBuyer": self.create_buyer,
            "BuyerLogin": self.buyer_login,
            "BuyerLogout": self.buyer_logout,
            "UpdateBuyerSessionTimestamp": self.update_buyer_session_timestamp,
            # Cart
            "AddItemToCart": self.add_item_to_cart,
            "RemoveItemFromCart": self.remove_item_from_cart,
            "SaveCart": self.save_cart,
            "ClearCart": self.clear_cart,
            # Transactions
            "InsertTransaction": self.insert_transaction,
            "InsertPurchase": self.insert_purchase,
        }

    def execute(self, method_name: str, args: dict) -> dict:
        """Dispatch method_name to its handler, passing its required args"""
        handler = self.handlerMap.get(method_name)
        if handler is None:
            logger.error("Unknown ABP method: %s", method_name)
            return {"success": False, "error_message": f"Unknown method: {method_name}"}
        return handler(args)

    # Seller Operations
    def create_seller(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT seller_id FROM sellers WHERE username = %s",
                (args["username"],)
            )
            if cursor.fetchone():
                return {"success": False, "error_message": "Username already exists"}

            cursor.execute(
                "INSERT INTO sellers (username, passwd) VALUES (%s, %s) RETURNING seller_id",
                (args["username"], args["password"])
            )
            seller_id = cursor.fetchone()["seller_id"]
            conn.commit()
            return {"success": True, "seller_id": seller_id}
        except Exception as e:
            conn.rollback()
            logger.error("CreateSeller error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def seller_login(self, args: dict) -> dict:
        """
        session_id is pre-generated in grpc_server.py and passed in args
        so that all replicas insert the identical UUID.
        """
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT seller_id, username FROM sellers WHERE username = %s AND passwd = %s",
                (args["username"], args["password"])
            )
            result = cursor.fetchone()
            if not result:
                return {"success": False, "error_message": "Invalid username or password"}

            seller_id = result["seller_id"]
            username = result["username"]
            session_id = args["session_id"]

            cursor.execute(
                "INSERT INTO seller_sessions (session_id, seller_id) VALUES (%s, %s)",
                (session_id, seller_id)
            )
            conn.commit()
            return {"success": True, "session_id": session_id,
                    "seller_id": seller_id, "username": username}
        except Exception as e:
            conn.rollback()
            logger.error("SellerLogin error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def seller_logout(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM seller_sessions WHERE session_id = %s",
                (args["session_id"],)
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("SellerLogout error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def update_seller_feedback(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            if args["thumbs_up"]:
                cursor.execute(
                    "UPDATE sellers SET thumbs_up = thumbs_up + 1 WHERE seller_id = %s",
                    (args["seller_id"],)
                )
            else:
                cursor.execute(
                    "UPDATE sellers SET thumbs_down = thumbs_down + 1 WHERE seller_id = %s",
                    (args["seller_id"],)
                )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("UpdateSellerFeedback error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def update_seller_session_timestamp(self, args: dict) -> dict:
        """Update session timestamp to keep it alive"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE seller_sessions SET last_active_at = NOW() WHERE session_id = %s",
                (args["session_id"],)
            )
            conn.commit()
            
            return {"success": True}
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateSellerSessionTimestamp: {e}")
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    # Buyer Operations

    def create_buyer(self, args: dict) -> dict:
        """
        saved_cart_id is pre-generated in grpc_server.py and passed in args.
        """
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT buyer_id FROM buyers WHERE username = %s",
                (args["username"],)
            )
            if cursor.fetchone():
                return {"success": False, "error_message": "Username already exists"}

            saved_cart_id = args["saved_cart_id"]  # pre-generated

            cursor.execute(
                "INSERT INTO buyers (username, passwd, saved_cart_id) "
                "VALUES (%s, %s, %s) RETURNING buyer_id",
                (args["username"], args["password"], saved_cart_id)
            )
            buyer_id = cursor.fetchone()["buyer_id"]

            cursor.execute(
                "INSERT INTO saved_carts (saved_cart_id, buyer_id) VALUES (%s, %s)",
                (saved_cart_id, buyer_id)
            )
            conn.commit()
            return {"success": True, "buyer_id": buyer_id, "saved_cart_id": saved_cart_id}
        except Exception as e:
            conn.rollback()
            logger.error("CreateBuyer error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def buyer_login(self, args: dict) -> dict:
        """
        session_id and active_cart_id are pre-generated in grpc_server.py.
        """
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT buyer_id, username FROM buyers WHERE username = %s AND passwd = %s",
                (args["username"], args["password"])
            )
            result = cursor.fetchone()
            if not result:
                return {"success": False, "error_message": "Invalid username or password"}

            buyer_id = result["buyer_id"]
            username = result["username"]

            # Load saved cart items to seed the new active cart
            cursor.execute(
                "SELECT saved_cart_items FROM saved_carts WHERE saved_cart_id = "
                "(SELECT saved_cart_id FROM buyers WHERE buyer_id = %s)",
                (buyer_id,)
            )
            saved_cart_result = cursor.fetchone()
            saved_cart_items = saved_cart_result["saved_cart_items"] if saved_cart_result else {}

            session_id = args["session_id"]       # pre-generated
            active_cart_id = args["active_cart_id"]  # pre-generated

            cursor.execute(
                "INSERT INTO buyer_sessions (session_id, buyer_id, active_cart_id) "
                "VALUES (%s, %s, %s)",
                (session_id, buyer_id, active_cart_id)
            )
            cursor.execute(
                "INSERT INTO active_carts (active_cart_id, session_id, active_cart_items) "
                "VALUES (%s, %s, %s)",
                (active_cart_id, session_id, json.dumps(saved_cart_items))
            )
            conn.commit()
            return {"success": True, "session_id": session_id, "buyer_id": buyer_id,
                    "username": username, "saved_cart_items": saved_cart_items}
        except Exception as e:
            conn.rollback()
            logger.error("BuyerLogin error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def buyer_logout(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            # Cascades to active_carts via FK
            cursor.execute(
                "DELETE FROM buyer_sessions WHERE session_id = %s",
                (args["session_id"],)
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("BuyerLogout error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def update_buyer_session_timestamp(self, args: dict) -> dict:
        """Update session timestamp to keep it alive"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE buyer_sessions SET last_active_at = NOW() WHERE session_id = %s",
                (args["session_id"],)
            )
            conn.commit()
            
            return {"success": True}
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateBuyerSessionTimestamp: {e}")
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    # Cart Operations

    def add_item_to_cart(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
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
                (str(args["item_id"]), str(args["item_id"]),
                 args["quantity"], args["session_id"])
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("AddItemToCart error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def remove_item_from_cart(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT (active_cart_items->>%s)::int AS cart_quantity "
                "FROM active_carts WHERE session_id = %s",
                (str(args["item_id"]), args["session_id"])
            )
            result = cursor.fetchone()
            cart_quantity = result["cart_quantity"] if result and result["cart_quantity"] else 0

            if cart_quantity <= args["quantity"]:
                cursor.execute(
                    "UPDATE active_carts SET active_cart_items = active_cart_items - %s "
                    "WHERE session_id = %s",
                    (str(args["item_id"]), args["session_id"])
                )
            else:
                cursor.execute(
                    """
                    UPDATE active_carts
                    SET active_cart_items = jsonb_set(
                        active_cart_items,
                        ARRAY[%s],
                        ((active_cart_items->>%s)::int - %s)::text::jsonb
                    )
                    WHERE session_id = %s
                    """,
                    (str(args["item_id"]), str(args["item_id"]),
                     args["quantity"], args["session_id"])
                )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("RemoveItemFromCart error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def save_cart(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
                (args["session_id"],)
            )
            result = cursor.fetchone()
            active_cart_items = result["active_cart_items"] if result else {}

            cursor.execute(
                "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s",
                (args["buyer_id"],)
            )
            saved_cart_id = cursor.fetchone()["saved_cart_id"]

            cursor.execute(
                "UPDATE saved_carts SET saved_cart_items = %s WHERE saved_cart_id = %s",
                (json.dumps(active_cart_items), saved_cart_id)
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("SaveCart error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def clear_cart(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(
                "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s",
                (args["buyer_id"],)
            )
            saved_cart_id = cursor.fetchone()["saved_cart_id"]

            cursor.execute(
                "SELECT active_cart_id FROM buyer_sessions WHERE session_id = %s",
                (args["session_id"],)
            )
            active_cart_id = cursor.fetchone()["active_cart_id"]

            cursor.execute(
                "UPDATE saved_carts SET saved_cart_items = '{}'::jsonb WHERE saved_cart_id = %s",
                (saved_cart_id,)
            )
            cursor.execute(
                "UPDATE active_carts SET active_cart_items = '{}'::jsonb WHERE active_cart_id = %s",
                (active_cart_id,)
            )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            logger.error("ClearCart error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    # Transaction Operations 

    def insert_transaction(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO transactions "
                "(buyer_id, cardholder_name, card_number, expiry_month, "
                " expiry_year, security_code, amount) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING transaction_id",
                (args["buyer_id"], args["cardholder_name"], args["card_number"],
                 args["expiry_month"], args["expiry_year"],
                 args["security_code"], args["amount"])
            )
            transaction_id = cursor.fetchone()["transaction_id"]
            conn.commit()
            return {"success": True, "transaction_id": transaction_id}
        except Exception as e:
            conn.rollback()
            logger.error("InsertTransaction error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)

    def insert_purchase(self, args: dict) -> dict:
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO purchases (buyer_id, transaction_id, item_ids) "
                "VALUES (%s, %s, %s) RETURNING purchase_id",
                (args["buyer_id"], args["transaction_id"], list(args["item_ids"]))
            )
            purchase_id = cursor.fetchone()["purchase_id"]
            conn.commit()
            return {"success": True, "purchase_id": purchase_id}
        except Exception as e:
            conn.rollback()
            logger.error("InsertPurchase error: %s", e)
            return {"success": False, "error_message": str(e)}
        finally:
            self.db_pool.putconn(conn)
