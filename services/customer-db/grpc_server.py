"""
gRPC server for Customer Database
Handles sellers, buyers, sessions, and cart operations
"""
import json
import os
import sys
import uuid
from concurrent import futures

import grpc
import psycopg2
from psycopg2 import extras, pool

# Add generated code to path
sys.path.insert(0, '/app/generated')

import customer_db_pb2
import customer_db_pb2_grpc


class CustomerDBServicer(customer_db_pb2_grpc.CustomerDBServiceServicer):
    """Implementation of CustomerDBService"""
    
    def __init__(self):
        print("Initializing Customer DB gRPC server...")
        # Create PostgreSQL connection pool
        self.db_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            user=os.getenv("POSTGRES_USER", "customer_user"),
            password=os.getenv("POSTGRES_PASSWORD", "customer_password"),
            host="localhost",  # PostgreSQL runs in same container
            port="5432",
            database=os.getenv("POSTGRES_DB", "customer_db"),
        )
        # Register UUID type
        extras.register_uuid()
        print("Customer DB connection pool initialized")

    # ========== Seller Operations ==========

    def CreateSeller(self, request, context):
        """Create a new seller account"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Check if username exists
            cursor.execute(
                "SELECT seller_id FROM sellers WHERE username = %s",
                (request.username,)
            )
            if cursor.fetchone():
                return customer_db_pb2.CreateSellerResponse(
                    success=False,
                    error_message="Username already exists"
                )
            
            # Create seller
            cursor.execute(
                "INSERT INTO sellers (username, passwd) VALUES (%s, %s) RETURNING seller_id",
                (request.username, request.password)
            )
            seller_id = cursor.fetchone()["seller_id"]
            conn.commit()
            
            return customer_db_pb2.CreateSellerResponse(
                success=True,
                seller_id=seller_id
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in CreateSeller: {e}")
            return customer_db_pb2.CreateSellerResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def SellerLogin(self, request, context):
        """Login seller and create session"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Verify credentials
            cursor.execute(
                "SELECT seller_id, username FROM sellers WHERE username = %s AND passwd = %s",
                (request.username, request.password)
            )
            result = cursor.fetchone()
            
            if not result:
                return customer_db_pb2.SellerLoginResponse(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            seller_id = result["seller_id"]
            username = result["username"]
            
            # Create session
            session_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO seller_sessions (session_id, seller_id) VALUES (%s, %s)",
                (session_id, seller_id)
            )
            conn.commit()
            
            return customer_db_pb2.SellerLoginResponse(
                success=True,
                session_id=session_id,
                seller_id=seller_id,
                username=username
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in SellerLogin: {e}")
            return customer_db_pb2.SellerLoginResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def SellerLogout(self, request, context):
        """Logout seller and delete session"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM seller_sessions WHERE session_id = %s",
                (request.session_id,)
            )
            conn.commit()
            
            return customer_db_pb2.LogoutResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in SellerLogout: {e}")
            return customer_db_pb2.LogoutResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetSellerRating(self, request, context):
        """Get seller rating (thumbs up/down)"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT thumbs_up, thumbs_down FROM sellers WHERE seller_id = %s",
                (request.seller_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return customer_db_pb2.GetSellerRatingResponse(
                    success=False,
                    error_message="Seller not found"
                )
            
            rating = customer_db_pb2.Rating(
                thumbs_up=result["thumbs_up"],
                thumbs_down=result["thumbs_down"]
            )
            
            return customer_db_pb2.GetSellerRatingResponse(
                success=True,
                rating=rating
            )
        except Exception as e:
            print(f"Error in GetSellerRating: {e}")
            return customer_db_pb2.GetSellerRatingResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def ValidateSellerSession(self, request, context):
        """Validate seller session and check timeout"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT seller_id FROM seller_sessions "
                "WHERE session_id = %s AND last_active_at > NOW() - INTERVAL '5 minutes'",
                (request.session_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                # Session expired or doesn't exist, clean up
                cursor.execute(
                    "DELETE FROM seller_sessions WHERE session_id = %s",
                    (request.session_id,)
                )
                conn.commit()
                return customer_db_pb2.ValidateSellerSessionResponse(
                    valid=False,
                    error_message="Session expired or invalid"
                )
            
            return customer_db_pb2.ValidateSellerSessionResponse(
                valid=True,
                seller_id=result["seller_id"]
            )
        except Exception as e:
            print(f"Error in ValidateSellerSession: {e}")
            return customer_db_pb2.ValidateSellerSessionResponse(
                valid=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def UpdateSellerSessionTimestamp(self, request, context):
        """Update session timestamp to keep it alive"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE seller_sessions SET last_active_at = NOW() WHERE session_id = %s",
                (request.session_id,)
            )
            conn.commit()
            
            return customer_db_pb2.UpdateSellerSessionTimestampResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateSellerSessionTimestamp: {e}")
            return customer_db_pb2.UpdateSellerSessionTimestampResponse(success=False)
        finally:
            self.db_pool.putconn(conn)

    def UpdateSellerFeedback(self, request, context):
        """Update seller thumbs up/down"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            if request.thumbs_up:
                cursor.execute(
                    "UPDATE sellers SET thumbs_up = thumbs_up + 1 WHERE seller_id = %s",
                    (request.seller_id,)
                )
            else:
                cursor.execute(
                    "UPDATE sellers SET thumbs_down = thumbs_down + 1 WHERE seller_id = %s",
                    (request.seller_id,)
                )
            
            conn.commit()
            return customer_db_pb2.UpdateSellerFeedbackResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateSellerFeedback: {e}")
            return customer_db_pb2.UpdateSellerFeedbackResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    # ========== Buyer Operations ==========

    def CreateBuyer(self, request, context):
        """Create a new buyer account with saved cart"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Check if username exists
            cursor.execute(
                "SELECT buyer_id FROM buyers WHERE username = %s",
                (request.username,)
            )
            if cursor.fetchone():
                return customer_db_pb2.CreateBuyerResponse(
                    success=False,
                    error_message="Username already exists"
                )
            
            # Create saved cart first
            saved_cart_id = str(uuid.uuid4())
            
            # Create buyer with saved_cart_id
            cursor.execute(
                "INSERT INTO buyers (username, passwd, saved_cart_id) "
                "VALUES (%s, %s, %s) RETURNING buyer_id",
                (request.username, request.password, saved_cart_id)
            )
            buyer_id = cursor.fetchone()["buyer_id"]
            
            # Create the saved cart
            cursor.execute(
                "INSERT INTO saved_carts (saved_cart_id, buyer_id) VALUES (%s, %s)",
                (saved_cart_id, buyer_id)
            )
            
            conn.commit()
            
            return customer_db_pb2.CreateBuyerResponse(
                success=True,
                buyer_id=buyer_id,
                saved_cart_id=saved_cart_id
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in CreateBuyer: {e}")
            return customer_db_pb2.CreateBuyerResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def BuyerLogin(self, request, context):
        """Login buyer, create session and active cart"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Verify credentials
            cursor.execute(
                "SELECT buyer_id, username FROM buyers WHERE username = %s AND passwd = %s",
                (request.username, request.password)
            )
            result = cursor.fetchone()
            
            if not result:
                return customer_db_pb2.BuyerLoginResponse(
                    success=False,
                    error_message="Invalid username or password"
                )
            
            buyer_id = result["buyer_id"]
            username = result["username"]
            
            # Get saved cart items
            cursor.execute(
                "SELECT saved_cart_items FROM saved_carts WHERE saved_cart_id = "
                "(SELECT saved_cart_id FROM buyers WHERE buyer_id = %s)",
                (buyer_id,)
            )
            saved_cart_result = cursor.fetchone()
            saved_cart_items = saved_cart_result["saved_cart_items"] if saved_cart_result else {}
            
            # Create session and active cart
            session_id = str(uuid.uuid4())
            active_cart_id = str(uuid.uuid4())
            
            # Create session first (active_carts FK references buyer_sessions)
            cursor.execute(
                "INSERT INTO buyer_sessions (session_id, buyer_id, active_cart_id) "
                "VALUES (%s, %s, %s)",
                (session_id, buyer_id, active_cart_id)
            )

            # Create active cart with saved cart items
            cursor.execute(
                "INSERT INTO active_carts (active_cart_id, session_id, active_cart_items) "
                "VALUES (%s, %s, %s)",
                (active_cart_id, session_id, json.dumps(saved_cart_items))
            )
            
            conn.commit()
            
            # Convert saved_cart_items to protobuf CartItems
            cart_items = customer_db_pb2.CartItems()
            if saved_cart_items:
                for item_id, quantity in saved_cart_items.items():
                    cart_items.items[str(item_id)] = int(quantity)
            
            return customer_db_pb2.BuyerLoginResponse(
                success=True,
                session_id=session_id,
                buyer_id=buyer_id,
                username=username,
                saved_cart_items=cart_items
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in BuyerLogin: {e}")
            return customer_db_pb2.BuyerLoginResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def BuyerLogout(self, request, context):
        """Logout buyer and delete session (cascades to active cart)"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM buyer_sessions WHERE session_id = %s",
                (request.session_id,)
            )
            conn.commit()
            
            return customer_db_pb2.LogoutResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in BuyerLogout: {e}")
            return customer_db_pb2.LogoutResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def ValidateBuyerSession(self, request, context):
        """Validate buyer session and check timeout"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT buyer_id FROM buyer_sessions "
                "WHERE session_id = %s AND last_active_at > NOW() - INTERVAL '5 minutes'",
                (request.session_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                # Session expired, clean up
                cursor.execute(
                    "DELETE FROM buyer_sessions WHERE session_id = %s",
                    (request.session_id,)
                )
                conn.commit()
                return customer_db_pb2.ValidateBuyerSessionResponse(
                    valid=False,
                    error_message="Session expired or invalid"
                )
            
            return customer_db_pb2.ValidateBuyerSessionResponse(
                valid=True,
                buyer_id=result["buyer_id"]
            )
        except Exception as e:
            print(f"Error in ValidateBuyerSession: {e}")
            return customer_db_pb2.ValidateBuyerSessionResponse(
                valid=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def UpdateBuyerSessionTimestamp(self, request, context):
        """Update buyer session timestamp"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE buyer_sessions SET last_active_at = NOW() WHERE session_id = %s",
                (request.session_id,)
            )
            conn.commit()
            
            return customer_db_pb2.UpdateBuyerSessionTimestampResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateBuyerSessionTimestamp: {e}")
            return customer_db_pb2.UpdateBuyerSessionTimestampResponse(success=False)
        finally:
            self.db_pool.putconn(conn)

    def InsertTransaction(self, request, context):
        """Insert transaction"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO transactions (buyer_id, cardholder_name, card_number, expiry_month, expiry_year, security_code, amount) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING transaction_id",
                (request.buyer_id, request.cardholder_name, request.card_number, request.expiry_month, request.expiry_year, request.security_code, request.amount)
            )
            result = cursor.fetchone()
            conn.commit()

            return customer_db_pb2.InsertTransactionResponse(
                success=True,
                transaction_id = result["transaction_id"],
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in InsertTransaction: {e}")
            return customer_db_pb2.InsertTransactionResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def InsertPurchase(self, request, context):
        """Insert purchase"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO purchases (buyer_id, transaction_id, item_ids) VALUES (%s, %s, %s) RETURNING purchase_id",
                (request.buyer_id, request.transaction_id, list(request.item_ids))
            )
            result = cursor.fetchone()
            conn.commit()

            return customer_db_pb2.InsertPurchaseResponse(
                success=True,
                purchase_id=result["purchase_id"]
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in InsertPurchase: {e}")
            return customer_db_pb2.InsertPurchaseResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetBuyerPurchases(self, request, context):
        """Insert purchase"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT purchase_id, item_ids FROM purchases WHERE buyer_id = %s",
                (request.buyer_id,)
            )
            conn.commit()
            result = cursor.fetchall()

            purchases = []
            for row in result:
                purchases.append(customer_db_pb2.PurchaseRecord(
                    purchase_id = row["purchase_id"],
                    item_ids = row["item_ids"]
                ))

            return customer_db_pb2.GetBuyerPurchasesResponse(
                success=True,
                purchases=purchases
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in GetBuyerPurchases: {e}")
            return customer_db_pb2.GetBuyerPurchasesResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)


    # ========== Cart Operations ==========

    def AddItemToCart(self, request, context):
        """Add item to active cart (JSONB operation)"""
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
                (str(request.item_id), str(request.item_id), request.quantity, request.session_id)
            )
            conn.commit()
            
            return customer_db_pb2.AddItemToCartResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in AddItemToCart: {e}")
            return customer_db_pb2.AddItemToCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def RemoveItemFromCart(self, request, context):
        """Remove item from active cart (JSONB operation)"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Get current quantity
            cursor.execute(
                "SELECT (active_cart_items->>%s)::int AS cart_quantity "
                "FROM active_carts WHERE session_id = %s",
                (str(request.item_id), request.session_id)
            )
            result = cursor.fetchone()
            cart_quantity = result["cart_quantity"] if result and result["cart_quantity"] else 0
            
            if cart_quantity <= request.quantity:
                # Remove item completely
                cursor.execute(
                    "UPDATE active_carts SET active_cart_items = active_cart_items - %s "
                    "WHERE session_id = %s",
                    (str(request.item_id), request.session_id)
                )
            else:
                # Decrement quantity
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
                    (str(request.item_id), str(request.item_id), request.quantity, request.session_id)
                )
            
            conn.commit()
            return customer_db_pb2.RemoveItemFromCartResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in RemoveItemFromCart: {e}")
            return customer_db_pb2.RemoveItemFromCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetCart(self, request, context):
        """Get active cart items"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
                (request.session_id,)
            )
            result = cursor.fetchone()
            
            cart_items = customer_db_pb2.CartItems()
            if result and result["active_cart_items"]:
                for item_id, quantity in result["active_cart_items"].items():
                    cart_items.items[str(item_id)] = int(quantity)
            
            return customer_db_pb2.GetCartResponse(
                success=True,
                cart_items=cart_items
            )
        except Exception as e:
            print(f"Error in GetCart: {e}")
            return customer_db_pb2.GetCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def SaveCart(self, request, context):
        """Save active cart to saved cart"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Get active cart items
            cursor.execute(
                "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
                (request.session_id,)
            )
            result = cursor.fetchone()
            active_cart_items = result["active_cart_items"] if result else {}
            
            # Get saved cart ID
            cursor.execute(
                "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s",
                (request.buyer_id,)
            )
            saved_cart_id = cursor.fetchone()["saved_cart_id"]
            
            # Update saved cart
            cursor.execute(
                "UPDATE saved_carts SET saved_cart_items = %s WHERE saved_cart_id = %s",
                (json.dumps(active_cart_items), saved_cart_id)
            )
            
            conn.commit()
            return customer_db_pb2.SaveCartResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in SaveCart: {e}")
            return customer_db_pb2.SaveCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def ClearCart(self, request, context):
        """Clear both active and saved carts"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Get saved cart ID and active cart ID
            cursor.execute(
                "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s",
                (request.buyer_id,)
            )
            saved_cart_id = cursor.fetchone()["saved_cart_id"]
            
            cursor.execute(
                "SELECT active_cart_id FROM buyer_sessions WHERE session_id = %s",
                (request.session_id,)
            )
            active_cart_id = cursor.fetchone()["active_cart_id"]
            
            # Clear both carts
            cursor.execute(
                "UPDATE saved_carts SET saved_cart_items = '{}'::jsonb WHERE saved_cart_id = %s",
                (saved_cart_id,)
            )
            cursor.execute(
                "UPDATE active_carts SET active_cart_items = '{}'::jsonb WHERE active_cart_id = %s",
                (active_cart_id,)
            )
            
            conn.commit()
            return customer_db_pb2.ClearCartResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in ClearCart: {e}")
            return customer_db_pb2.ClearCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    customer_db_pb2_grpc.add_CustomerDBServiceServicer_to_server(
        CustomerDBServicer(), server
    )
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Customer DB gRPC server started on port 50052")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
