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


class ProductDBServicer(product_db_pb2_grpc.ProductDBServiceServicer):
    """Implementation of ProductDBService"""
    
    def __init__(self):
        print("Initializing Product DB gRPC server...")
        # Create PostgreSQL connection pool
        self.db_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            user=os.getenv("POSTGRES_USER", "product_user"),
            password=os.getenv("POSTGRES_PASSWORD", "product_password"),
            host="localhost",  # PostgreSQL runs in same container
            port="5432",
            database=os.getenv("POSTGRES_DB", "product_db"),
        )
        print("Product DB connection pool initialized")

    def RegisterItem(self, request, context):
        """Register a new item for sale"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "INSERT INTO products (seller_id, item_name, category, keywords, "
                "condition, sale_price, quantity) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "RETURNING item_id",
                (request.seller_id, request.item_name, request.category,
                 list(request.keywords), request.condition, request.sale_price,
                 request.quantity)
            )
            item_id = cursor.fetchone()["item_id"]
            conn.commit()
            return product_db_pb2.RegisterItemResponse(
                success=True,
                item_id=item_id
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in RegisterItem: {e}")
            return product_db_pb2.RegisterItemResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def UpdateItemPrice(self, request, context):
        """Update the price of an item"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE products SET sale_price = %s WHERE item_id = %s AND seller_id = %s",
                (request.new_price, request.item_id, request.seller_id)
            )
            
            if cursor.rowcount == 0:
                return product_db_pb2.UpdateItemPriceResponse(
                    success=False,
                    error_message="Item not found or does not belong to seller"
                )
            
            conn.commit()
            return product_db_pb2.UpdateItemPriceResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateItemPrice: {e}")
            return product_db_pb2.UpdateItemPriceResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def UpdateItemQuantity(self, request, context):
        """Update the quantity of an item"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Get current quantity
            cursor.execute(
                "SELECT quantity FROM products WHERE item_id = %s AND seller_id = %s",
                (request.item_id, request.seller_id)
            )
            result = cursor.fetchone()
            
            if not result:
                return product_db_pb2.UpdateItemQuantityResponse(
                    success=False,
                    error_message="Item not found or does not belong to seller"
                )
            
            current_quantity = result["quantity"]
            new_quantity = current_quantity - request.quantity_change
            
            if new_quantity < 0:
                return product_db_pb2.UpdateItemQuantityResponse(
                    success=False,
                    error_message="Available units cannot be negative"
                )
            
            # Update quantity
            cursor.execute(
                "UPDATE products SET quantity = %s WHERE item_id = %s AND seller_id = %s",
                (new_quantity, request.item_id, request.seller_id)
            )
            conn.commit()
            
            return product_db_pb2.UpdateItemQuantityResponse(
                success=True,
                new_quantity=new_quantity
            )
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateItemQuantity: {e}")
            return product_db_pb2.UpdateItemQuantityResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetItemsBySeller(self, request, context):
        """Get all items for sale by a seller"""
        conn = self.db_pool.getconn()
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
            self.db_pool.putconn(conn)

    def SearchItems(self, request, context):
        """Search items by category and optional keywords"""
        conn = self.db_pool.getconn()
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
            self.db_pool.putconn(conn)

    def GetItem(self, request, context):
        """Get details of a single item"""
        conn = self.db_pool.getconn()
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
            self.db_pool.putconn(conn)

    def UpdateItemFeedback(self, request, context):
        """Update thumbs up/down for an item"""
        conn = self.db_pool.getconn()
        try:
            cursor = conn.cursor()
            
            if request.thumbs_up:
                cursor.execute(
                    "UPDATE products SET thumbs_up = thumbs_up + 1 WHERE item_id = %s",
                    (request.item_id,)
                )
            else:
                cursor.execute(
                    "UPDATE products SET thumbs_down = thumbs_down + 1 WHERE item_id = %s",
                    (request.item_id,)
                )
            
            conn.commit()
            return product_db_pb2.UpdateItemFeedbackResponse(success=True)
        except Exception as e:
            conn.rollback()
            print(f"Error in UpdateItemFeedback: {e}")
            return product_db_pb2.UpdateItemFeedbackResponse(
                success=False,
                error_message=str(e)
            )
        finally:
            self.db_pool.putconn(conn)

    def GetItemQuantity(self, request, context):
        """Get the available quantity of an item"""
        conn = self.db_pool.getconn()
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
            self.db_pool.putconn(conn)

    def GetItemSeller(self, request, context):
        """Get the seller_id for an item"""
        conn = self.db_pool.getconn()
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
            self.db_pool.putconn(conn)


def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    product_db_pb2_grpc.add_ProductDBServiceServicer_to_server(
        ProductDBServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Product DB gRPC server started on port 50051")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()