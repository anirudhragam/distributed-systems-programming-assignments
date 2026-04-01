"""
gRPC server for Product Database
Wraps PostgreSQL operations with gRPC service
"""
import os
import sys
from concurrent import futures

import grpc
from psycopg2 import extras, pool

# Add generated code to path
sys.path.insert(0, '/app/generated')

import product_db_pb2
import product_db_pb2_grpc
from pysyncobj import SyncObj, SyncObjConf, replicated

_db_pool = None

class RaftManager(SyncObj):
    def __init__(self, self_addr, partners):
        # Create PostgreSQL connection pool
        global _db_pool
        _db_pool = pool.ThreadedConnectionPool(
            minconn=5,
            maxconn=100,
            user=os.getenv("POSTGRES_USER", "product_user"),
            password=os.getenv("POSTGRES_PASSWORD", "product_password"),
            host="localhost",  # PostgreSQL runs in same container
            port=os.getenv("PGPORT", "5432"),
            database=os.getenv("POSTGRES_DB", "product_db"),
        )
        print("Product DB connection pool initialized")

        # Clear PostgreSQL so journal replay starts from a clean state.
        # Without this, PySyncObj re-applies already-applied entries:
        # INSERTs fail (duplicate key), quantity UPDATEs double-subtract.
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE products RESTART IDENTITY")
            conn.commit()
            print("PostgreSQL cleared for Raft journal replay")
        except Exception as e:
            conn.rollback()
            print(f"Warning: could not clear state: {e}")
        finally:
            _db_pool.putconn(conn)

        # Create a config that cleans the log every 500 entries
        conf = SyncObjConf(
            entriesFinishedSize=500, 
            autoTickPeriod=0.01,
        )
        super(RaftManager, self).__init__(self_addr, partners, conf=conf)
        print("Initializing Product DB gRPC server...") 
    
    def getSnapshot(self):
        """Export products table as JSON for Raft snapshot."""
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT item_id, seller_id, item_name, category, keywords, condition, "
                "sale_price::float, quantity, thumbs_up, thumbs_down FROM products"
            )
            rows = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT last_value FROM products_item_id_seq")
            seq = cursor.fetchone()["last_value"]
            import json
            return json.dumps({"rows": rows, "seq": seq}).encode()
        except Exception as e:
            print(f"getSnapshot error: {e}")
            return b'pg_synced'
        finally:
            _db_pool.putconn(conn)

    def setSnapshot(self, snapshot_data):
        """Restore products table from Raft snapshot."""
        if not snapshot_data or snapshot_data == b'pg_synced':
            return
        try:
            import json
            data = json.loads(snapshot_data)
        except Exception:
            return
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE products RESTART IDENTITY")
            for row in data["rows"]:
                cursor.execute(
                    "INSERT INTO products (item_id, seller_id, item_name, category, keywords, "
                    "condition, sale_price, quantity, thumbs_up, thumbs_down) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (row["item_id"], row["seller_id"], row["item_name"], row["category"],
                    row["keywords"], row["condition"], row["sale_price"],
                    row["quantity"], row["thumbs_up"], row["thumbs_down"])
                )
            cursor.execute("SELECT setval('products_item_id_seq', %s, true)", (data["seq"],))
            conn.commit()
            print(f"setSnapshot: restored {len(data['rows'])} rows")
        except Exception as e:
            conn.rollback()
            print(f"setSnapshot error: {e}")
        finally:
            _db_pool.putconn(conn)

    @replicated
    def sync_update_item_price(self, item_id, seller_id, new_price):
        """
        This method is called by PySyncObj internally. 
        It only executes once the majority has agreed.
        """
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET sale_price = %s WHERE item_id = %s AND seller_id = %s",
                (new_price, item_id, seller_id)
            )
            count = cursor.rowcount
            conn.commit()
            # We return the rowcount so the Leader knows if it actually found the item
            return {"success": count > 0, "rows": count}
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            _db_pool.putconn(conn)

    @replicated
    def sync_register_item(self, item_id, seller_id, item_name, category, keywords, condition, sale_price, quantity):
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO products (item_id, seller_id, item_name, category, keywords, "
                "condition, sale_price, quantity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING item_id",
                (item_id, seller_id, item_name, category, list(keywords), condition, sale_price, quantity)
            )
            result = cursor.fetchone()
            # Sync the sequence so any future leader uses the correct next ID
            cursor.execute("SELECT setval('products_item_id_seq', %s, true)", (item_id,))
            conn.commit()
            return {"success": True, "item_id": result["item_id"]}
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            _db_pool.putconn(conn)

    @replicated
    def sync_update_item_quantity(self, item_id, seller_id, quantity_change):
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT quantity FROM products WHERE item_id = %s AND seller_id = %s",
                (item_id, seller_id)
            )
            result = cursor.fetchone()
            if not result:
                return {"success": False, "error": "Item not found or does not belong to seller"}
            new_quantity = result["quantity"] - quantity_change
            if new_quantity < 0:
                return {"success": False, "error": "Available units cannot be negative"}
            cursor.execute(
                "UPDATE products SET quantity = %s WHERE item_id = %s AND seller_id = %s",
                (new_quantity, item_id, seller_id)
            )
            conn.commit()
            return {"success": True, "new_quantity": new_quantity}
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            _db_pool.putconn(conn)

    @replicated
    def sync_update_item_feedback(self, item_id, thumbs_up):
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor()
            if thumbs_up:
                cursor.execute(
                    "UPDATE products SET thumbs_up = thumbs_up + 1 WHERE item_id = %s",
                    (item_id,)
                )
            else:
                cursor.execute(
                    "UPDATE products SET thumbs_down = thumbs_down + 1 WHERE item_id = %s",
                    (item_id,)
                )
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            _db_pool.putconn(conn)
class ProductDBServicer(product_db_pb2_grpc.ProductDBServiceServicer):
    """Implementation of ProductDBService"""
    
    def __init__(self, raft_manager):
        self.raft = raft_manager

    def RegisterItem(self, request, context):
        """Register a new item for sale"""
        if not self.raft.isReady():
            context.abort(grpc.StatusCode.UNAVAILABLE, "Cluster not ready")

        # Pre-generate item_id from the local sequence (leader only)
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT nextval('products_item_id_seq')")
            item_id = cursor.fetchone()[0]
        except Exception as e:
            return product_db_pb2.RegisterItemResponse(success=False, error_message=str(e))
        finally:
            _db_pool.putconn(conn)

        res = self.raft.sync_register_item(
            item_id, request.seller_id, request.item_name, request.category,
            list(request.keywords), request.condition, request.sale_price,
            request.quantity, sync=True, timeout=10
        )
        if not res or not res.get("success"):
            return product_db_pb2.RegisterItemResponse(
                success=False,
                error_message=res.get("error", "Registration failed") if res else "Timeout"
            )
        return product_db_pb2.RegisterItemResponse(success=True, item_id=res["item_id"])

    def UpdateItemPrice(self, request, context):
        """Update the price of an item"""
        # Wait for Raft to be ready (election finished)
        if not self.raft.isReady():
            context.abort(grpc.StatusCode.UNAVAILABLE, "Cluster not ready")
        
        # This call handles the replication and blocks until consensus
        res = self.raft.sync_update_item_price(request.item_id, request.seller_id, request.new_price, sync=True, timeout=10)
        return product_db_pb2.UpdateItemPriceResponse(success=res.get("success", False))

    def UpdateItemQuantity(self, request, context):
        """Update the quantity of an item"""
        if not self.raft.isReady():
            context.abort(grpc.StatusCode.UNAVAILABLE, "Cluster not ready")

        res = self.raft.sync_update_item_quantity(
            request.item_id, request.seller_id, request.quantity_change,
            sync=True, timeout=10
        )
        if not res:
            return product_db_pb2.UpdateItemQuantityResponse(
                success=False, error_message="Timeout waiting for consensus"
            )
        if not res.get("success"):
            return product_db_pb2.UpdateItemQuantityResponse(
                success=False, error_message=res.get("error", "Update failed")
            )
        return product_db_pb2.UpdateItemQuantityResponse(
            success=True, new_quantity=res["new_quantity"]
        )

    def GetItemsBySeller(self, request, context):
        """Get all items for sale by a seller"""
        # Wait for Raft to be ready (election finished)
        if not self.raft.isReady():
            context.abort(grpc.StatusCode.UNAVAILABLE, "Cluster not ready")
        
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT item_id, seller_id, item_name, category, keywords, condition, "
                "sale_price::float, quantity, thumbs_up, thumbs_down "
                "FROM products WHERE seller_id = %s AND quantity > 0",
                (request.seller_id,)
            )
            items = cursor.fetchall()
            
            product_list = []
            for item in items:
                product_list.append(product_db_pb2.Item(
                    item_id=item["item_id"],
                    seller_id=item["seller_id"],
                    item_name=item["item_name"],
                    category=item["category"],
                    keywords=item["keywords"] or [],
                    condition=item["condition"],
                    sale_price=item["sale_price"],
                    quantity=item["quantity"],
                    thumbs_up=item["thumbs_up"],
                    thumbs_down=item["thumbs_down"]
                ))
            
            return product_db_pb2.GetItemsBySellerResponse(
                success=True,
                items=product_list
            )
        except Exception as e:
            print(f"Error in GetItemsBySeller: {e}")
            return product_db_pb2.GetItemsBySellerResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            _db_pool.putconn(conn)

    def SearchItems(self, request, context):
        """Search items by category and optional keywords"""
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            if request.keywords:
                # Search with keywords using array overlap operator
                cursor.execute(
                    "SELECT item_id, seller_id, item_name, category, keywords, condition, "
                    "sale_price::float, quantity, thumbs_up, thumbs_down "
                    "FROM products WHERE category = %s AND keywords && %s::varchar[]",
                    (request.category, list(request.keywords))
                )
            else:
                # Search by category only
                cursor.execute(
                    "SELECT item_id, seller_id, item_name, category, keywords, condition, "
                    "sale_price::float, quantity, thumbs_up, thumbs_down "
                    "FROM products WHERE category = %s",
                    (request.category,)
                )
            
            items = cursor.fetchall()
            
            product_list = []
            for item in items:
                product_list.append(product_db_pb2.Item(
                    item_id=item["item_id"],
                    seller_id=item["seller_id"],
                    item_name=item["item_name"],
                    category=item["category"],
                    keywords=item["keywords"] or [],
                    condition=item["condition"],
                    sale_price=item["sale_price"],
                    quantity=item["quantity"],
                    thumbs_up=item["thumbs_up"],
                    thumbs_down=item["thumbs_down"]
                ))
            
            return product_db_pb2.SearchItemsResponse(
                success=True,
                items=product_list
            )
        except Exception as e:
            print(f"Error in SearchItems: {e}")
            return product_db_pb2.SearchItemsResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            _db_pool.putconn(conn)

    def GetItem(self, request, context):
        """Get details of a single item"""
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT item_id, seller_id, item_name, category, keywords, condition, "
                "sale_price::float, quantity, thumbs_up, thumbs_down "
                "FROM products WHERE item_id = %s",
                (request.item_id,)
            )
            item = cursor.fetchone()
            
            if not item:
                return product_db_pb2.GetItemResponse(
                    success=False,
                    error_message="Item not found"
                )
            
            product = product_db_pb2.Item(
                item_id=item["item_id"],
                seller_id=item["seller_id"],
                item_name=item["item_name"],
                category=item["category"],
                keywords=item["keywords"] or [],
                condition=item["condition"],
                sale_price=item["sale_price"],
                quantity=item["quantity"],
                thumbs_up=item["thumbs_up"],
                thumbs_down=item["thumbs_down"]
            )
            
            return product_db_pb2.GetItemResponse(
                success=True,
                item=product
            )
        except Exception as e:
            print(f"Error in GetItem: {e}")
            return product_db_pb2.GetItemResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            _db_pool.putconn(conn)

    def UpdateItemFeedback(self, request, context):
        """Update thumbs up/down for an item"""
        if not self.raft.isReady():
            context.abort(grpc.StatusCode.UNAVAILABLE, "Cluster not ready")

        res = self.raft.sync_update_item_feedback(
            request.item_id, request.thumbs_up,
            sync=True, timeout=10
        )
        if not res or not res.get("success"):
            return product_db_pb2.UpdateItemFeedbackResponse(
                success=False,
                error_message=res.get("error", "Feedback update failed") if res else "Timeout"
            )
        return product_db_pb2.UpdateItemFeedbackResponse(success=True)

    def GetItemQuantity(self, request, context):
        """Get the available quantity of an item"""
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT quantity FROM products WHERE item_id = %s",
                (request.item_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return product_db_pb2.GetItemQuantityResponse(
                    success=False,
                    error_message="Item not found"
                )
            
            return product_db_pb2.GetItemQuantityResponse(
                success=True,
                quantity=result["quantity"]
            )
        except Exception as e:
            print(f"Error in GetItemQuantity: {e}")
            return product_db_pb2.GetItemQuantityResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            _db_pool.putconn(conn)

    def GetItemSeller(self, request, context):
        """Get the seller_id for an item"""
        conn = _db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT seller_id FROM products WHERE item_id = %s",
                (request.item_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                return product_db_pb2.GetItemSellerResponse(
                    success=False,
                    error_message="Item not found"
                )
            
            return product_db_pb2.GetItemSellerResponse(
                success=True,
                seller_id=result["seller_id"]
            )
        except Exception as e:
            print(f"Error in GetItemSeller: {e}")
            return product_db_pb2.GetItemSellerResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            _db_pool.putconn(conn)


def serve():
    """Start the gRPC server"""
    self_ip = os.getenv("SELF_IP", "")
    self_port = os.getenv("SELF_PORT", "12345")
    raw_partners = os.getenv("PARTNERS", "")
    # Split the string and ensure each IP has the :12345 port attached
    partners = [f"{ip.strip()}:12345" if ":" not in ip else ip.strip() for ip in raw_partners.split(",") if ip.strip()]
    # Initialize Raft Manager
    raft_manager = RaftManager(f"{self_ip}:{self_port}", partners)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    product_db_pb2_grpc.add_ProductDBServiceServicer_to_server(
        ProductDBServicer(raft_manager), server
    )
    server.add_insecure_port(f'[::]:{os.getenv("GRPC_PORT", "50051")}')
    server.start()
    print(f"Product DB gRPC server started on port 50051 with raft node on {self_ip}")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()