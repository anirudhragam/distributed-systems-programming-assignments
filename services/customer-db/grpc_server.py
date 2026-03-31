"""
gRPC server for Customer Database
Handles sellers, buyers, sessions, and cart operations
"""
import json
import os
import sys
import threading
import uuid
from concurrent import futures

import grpc
import psycopg2
from psycopg2 import extras, pool


# Add generated code to path
sys.path.insert(0, '/app/generated')

import customer_db_pb2
import customer_db_pb2_grpc
from abp.node import ABPNode



class CustomerDBServicer(customer_db_pb2_grpc.CustomerDBServiceServicer):
    """Implementation of CustomerDBService"""
    
    def __init__(self):
        print("Initializing Customer DB gRPC server...")
        # Create PostgreSQL connection pool
        self.db_pool = pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=100,
            user=os.getenv("POSTGRES_USER", "customer_user"),
            password=os.getenv("POSTGRES_PASSWORD", "customer_password"),
            host="localhost",  # PostgreSQL runs in same container
            port=os.getenv("PGPORT", "5432"),
            database=os.getenv("POSTGRES_DB", "customer_db"),
        )

        # Atomic Broadcast protocol setup
        node_id   = int(os.getenv("ABP_NODE_ID", "0"))
        peers_raw = os.getenv("ABP_PEERS", "localhost:5100")
        peers = [(h, int(p)) for h, p in (pair.split(":") for pair in peers_raw.split(","))]
        udp_port  = int(os.getenv("ABP_UDP_PORT", "5100"))

        self.abp = ABPNode(node_id, peers, self.db_pool, udp_port)
        self.abp.start()
        print(f"ABPNode {node_id} started, peers={peers}")
        
        # Register UUID type
        extras.register_uuid()
        print("Customer DB connection pool initialized")

    # Seller Operation

    def CreateSeller(self, request, context):
        """Create a new seller account"""
        result = self.abp.submit_write("CreateSeller", {
            "username": request.username,
            "password": request.password
        })

        return customer_db_pb2.CreateSellerResponse(
            success=result["success"],
            seller_id=result.get("seller_id", 0),
            error_message=result.get("error_message", ""),
        )

    def SellerLogin(self, request, context):
        """Login seller and create session"""
        session_id = str(uuid.uuid4())
        result = self.abp.submit_write("SellerLogin", {
            "username": request.username,
            "password": request.password,
            "session_id": session_id,
        })
        return customer_db_pb2.SellerLoginResponse(
            success=result["success"],
            session_id=result.get("session_id", ""),
            seller_id=result.get("seller_id", 0),
            username=result.get("username", ""),
            error_message=result.get("error_message", ""),
    )
        

    def SellerLogout(self, request, context):
        result = self.abp.submit_write("SellerLogout", {
            "session_id": request.session_id,
        })
        return customer_db_pb2.LogoutResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

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
        result = self.abp.submit_write("UpdateSellerSessionTimestamp", {
            "session_id": request.session_id,
        })

        return customer_db_pb2.UpdateSellerSessionTimestampResponse(
            success=result["success"],
        )
        
    def UpdateSellerFeedback(self, request, context):
        result = self.abp.submit_write("UpdateSellerFeedback", {
            "seller_id": request.seller_id,
            "thumbs_up": request.thumbs_up,
        })
        return customer_db_pb2.UpdateSellerFeedbackResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

    # Buyer Operations

    def CreateBuyer(self, request, context):
        saved_cart_id = str(uuid.uuid4())
        result = self.abp.submit_write("CreateBuyer", {
            "username":      request.username,
            "password":      request.password,
            "saved_cart_id": saved_cart_id,
        })
        return customer_db_pb2.CreateBuyerResponse(
            success=result["success"],
            buyer_id=result.get("buyer_id", 0),
            saved_cart_id=result.get("saved_cart_id", ""),
            error_message=result.get("error_message", ""),
        )

    def BuyerLogin(self, request, context):
        session_id     = str(uuid.uuid4())
        active_cart_id = str(uuid.uuid4())
        result = self.abp.submit_write("BuyerLogin", {
            "username":       request.username,
            "password":       request.password,
            "session_id":     session_id,
            "active_cart_id": active_cart_id,
        })
        if not result["success"]:
            return customer_db_pb2.BuyerLoginResponse(
                success=False,
                error_message=result.get("error_message", ""),
            )
        cart_items = customer_db_pb2.CartItems()
        saved = result.get("saved_cart_items") or {}
        for item_id, quantity in saved.items():
            cart_items.items[str(item_id)] = int(quantity)

        return customer_db_pb2.BuyerLoginResponse(
            success=True,
            session_id=result["session_id"],
            buyer_id=result["buyer_id"],
            username=result["username"],
            saved_cart_items=cart_items,
        )

    def BuyerLogout(self, request, context):
        result = self.abp.submit_write("BuyerLogout", {
            "session_id": request.session_id,
        })
        return customer_db_pb2.LogoutResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

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
        result = self.abp.submit_write("UpdateBuyerSessionTimestamp", {
            "session_id": request.session_id,
        })

        return customer_db_pb2.UpdateBuyerSessionTimestampResponse(
            success=result["success"],
        )

    def InsertTransaction(self, request, context):
        result = self.abp.submit_write("InsertTransaction", {
            "buyer_id":        request.buyer_id,
            "cardholder_name": request.cardholder_name,
            "card_number":     request.card_number,
            "expiry_month":    request.expiry_month,
            "expiry_year":     request.expiry_year,
            "security_code":   request.security_code,
            "amount":          request.amount,
        })
        return customer_db_pb2.InsertTransactionResponse(
            success=result["success"],
            transaction_id=result.get("transaction_id", 0),
            error_message=result.get("error_message", ""),
        )

    def InsertPurchase(self, request, context):
        result = self.abp.submit_write("InsertPurchase", {
            "buyer_id":       request.buyer_id,
            "transaction_id": request.transaction_id,
            "item_ids":       list(request.item_ids),
        })
        return customer_db_pb2.InsertPurchaseResponse(
            success=result["success"],
            purchase_id=result.get("purchase_id", 0),
            error_message=result.get("error_message", ""),
        )

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


    # Cart Operations

    def AddItemToCart(self, request, context):
        result = self.abp.submit_write("AddItemToCart", {
            "session_id": request.session_id,
            "item_id":    request.item_id,
            "quantity":   request.quantity,
        })
        return customer_db_pb2.AddItemToCartResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

    def RemoveItemFromCart(self, request, context):
        result = self.abp.submit_write("RemoveItemFromCart", {
            "session_id": request.session_id,
            "item_id":    request.item_id,
            "quantity":   request.quantity,
        })
        return customer_db_pb2.RemoveItemFromCartResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

    def GetActiveCart(self, request, context):
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
            
            return customer_db_pb2.GetActiveCartResponse(
                success=True,
                cart_items=cart_items
            )
        except Exception as e:
            print(f"Error in GetActiveCart: {e}")
            return customer_db_pb2.GetActiveCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetSavedCart(self, request, context):
        """Get saved cart items"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT saved_cart_items FROM saved_carts WHERE buyer_id = %s",
                (request.buyer_id,)
            )
            result = cursor.fetchone()
            
            cart_items = customer_db_pb2.CartItems()
            if result and result["saved_cart_items"]:
                for item_id, quantity in result["saved_cart_items"].items():
                    cart_items.items[str(item_id)] = int(quantity)
            
            return customer_db_pb2.GetSavedCartResponse(
                success=True,
                cart_items=cart_items
            )
        except Exception as e:
            print(f"Error in GetSavedCart: {e}")
            return customer_db_pb2.GetSavedCartResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def SaveCart(self, request, context):
        result = self.abp.submit_write("SaveCart", {
            "session_id": request.session_id,
            "buyer_id":   request.buyer_id,
        })

        return customer_db_pb2.SaveCartResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

    def ClearCart(self, request, context):
        result = self.abp.submit_write("ClearCart", {
            "session_id": request.session_id,
            "buyer_id":   request.buyer_id,
        })

        return customer_db_pb2.ClearCartResponse(
            success=result["success"],
            error_message=result.get("error_message", ""),
        )

def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    port = int(os.getenv("GRPC_PORT", "50052"))

    customer_db_pb2_grpc.add_CustomerDBServiceServicer_to_server(
        CustomerDBServicer(), server
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print("Customer DB gRPC server started on port 50052")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
