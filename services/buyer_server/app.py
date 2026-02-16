"""
Flask-based RESTful API server for buyer operations (gRPC-based)
"""
import os
import grpc
import sys
from flask import Flask, request, jsonify

# Add generated protobuf path
sys.path.insert(0, '/app/generated')
import product_db_pb2
import product_db_pb2_grpc
import customer_db_pb2
import customer_db_pb2_grpc

import auth
import uuid

import requests
from zeep import Client

# Define extension to convert DECIMAL to FLOAT
DEC2FLOAT = extensions.new_type(_psycopg.DECIMAL.values, "DEC2FLOAT", extensions.FLOAT)

# Initialize Flask app
app = Flask(__name__)

# Global gRPC clients
product_db_channel = None
product_db_stub = None
customer_db_channel = None
customer_db_stub = None


def init_grpc_clients():
    """Initialize gRPC client stubs for database services"""
    global product_db_channel, product_db_stub, customer_db_channel, customer_db_stub

    # Create persistent gRPC channels
    product_db_channel = grpc.insecure_channel('product-db:50051')
    product_db_stub = product_db_pb2_grpc.ProductDBServiceStub(product_db_channel)

    customer_db_channel = grpc.insecure_channel('customer-db:50052')
    customer_db_stub = customer_db_pb2_grpc.CustomerDBServiceStub(customer_db_channel)

    # Inject customer_db_stub into auth module
    auth.set_customer_db_stub(customer_db_stub)

    print("Buyer server initialized with gRPC clients")


SOAP_WSDL = "http://financial-transactions:8000/?wsdl"
soap_client = Client(SOAP_WSDL)

# Initialize database connection pools
product_db_pool = pool.ThreadedConnectionPool(
    minconn=50,
    maxconn=100,
    user="product_user",
    password="product_password",
    host="product-db",
    port="5432",
    database="product_db",
)

customer_db_pool = pool.ThreadedConnectionPool(
    minconn=50,
    maxconn=100,
    user="customer_user",
    password="customer_password",
    host="customer-db",
    port="5432",
    database="customer_db",
)

# Register PostgreSQL extensions
extras.register_uuid()
extensions.register_type(DEC2FLOAT)

@app.route('/api/buyers/accounts', methods=['POST'])
def create_account():
    """Create a new buyer account"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        request_msg = customer_db_pb2.CreateBuyerRequest(
            username=username,
            password=password
        )
        response = customer_db_stub.CreateBuyer(request_msg)

        if not response.success:
            if "already exists" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Username already exists."
                }), 409
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "buyer_id": response.buyer_id
        }), 201

    except grpc.RpcError as e:
        print(f"gRPC error creating buyer account: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to create account."
        }), 500


@app.route('/api/buyers/sessions', methods=['POST'])
def login():
    """Login and create a new session with active cart"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        request_msg = customer_db_pb2.BuyerLoginRequest(
            username=username,
            password=password
        )
        response = customer_db_stub.BuyerLogin(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Username/Password combination does not exist."
            }), 401

        return jsonify({
            "status": "OK",
            "session_id": response.session_id,
            "buyer_id": response.buyer_id,
            "message": f"I've seen enough. Welcome back {response.username}"
        }), 201

    except grpc.RpcError as e:
        print(f"gRPC error logging into buyer account: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log in to buyer account."
        }), 500


@app.route('/api/buyers/sessions', methods=['DELETE'])
@auth.require_auth(user_type='buyer')
def logout(session_id, buyer_id):
    """Logout and delete the session"""
    try:
        request_msg = customer_db_pb2.LogoutRequest(session_id=session_id)
        response = customer_db_stub.BuyerLogout(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Failed to log out."
            }), 500

        return jsonify({
            "status": "OK",
            "message": "Successfully logged out."
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error logging out of buyer session: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log out of buyer session."
        }), 500


@app.route('/api/buyers/items/search', methods=['GET'])
@auth.require_auth(user_type='buyer')
def search_items(session_id, buyer_id):
    """Search for items by category and keywords"""
    category = request.args.get("category", type=int)
    keywords = request.args.getlist("keywords")

    try:
        request_msg = product_db_pb2.SearchItemsRequest(
            category=category,
            keywords=keywords  # list automatically converts to repeated
        )
        response = product_db_stub.SearchItems(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        # Convert protobuf Product messages to dict
        results = []
        for product in response.products:
            results.append({
                "item_id": product.item_id,
                "seller_id": product.seller_id,
                "item_name": product.item_name,
                "category": product.category,
                "keywords": list(product.keywords),
                "condition": product.condition,
                "sale_price": product.sale_price,
                "quantity": product.quantity,
                "thumbs_up": product.thumbs_up,
                "thumbs_down": product.thumbs_down
            })

        return jsonify({
            "status": "OK",
            "items": results
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error searching items: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to search items."
        }), 500


@app.route('/api/buyers/items/<int:item_id>', methods=['GET'])
@auth.require_auth(user_type='buyer')
def get_item(session_id, buyer_id, item_id):
    """Get details of a specific item"""
    try:
        request_msg = product_db_pb2.GetItemRequest(item_id=item_id)
        response = product_db_stub.GetItem(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Item not found."
            }), 404

        # Convert protobuf Product to dict
        result = {
            "item_id": response.product.item_id,
            "seller_id": response.product.seller_id,
            "item_name": response.product.item_name,
            "category": response.product.category,
            "keywords": list(response.product.keywords),
            "condition": response.product.condition,
            "sale_price": response.product.sale_price,
            "quantity": response.product.quantity,
            "thumbs_up": response.product.thumbs_up,
            "thumbs_down": response.product.thumbs_down
        }

        return jsonify({
            "status": "OK",
            "item": result
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error getting item details: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to get item details."
        }), 500


@app.route('/api/buyers/cart/items/<int:item_id>', methods=['POST'])
@auth.require_auth(user_type='buyer')
def add_item_to_cart(session_id, buyer_id, item_id):
    """Add item to cart (with quantity validation)"""
    data = request.json
    quantity = data.get("quantity")

    try:
        # Step 1: Validate item exists and has sufficient quantity
        quantity_req = product_db_pb2.GetItemQuantityRequest(item_id=item_id)
        quantity_resp = product_db_stub.GetItemQuantity(quantity_req)

        if not quantity_resp.success:
            return jsonify({
                "status": "Error",
                "message": "Item ID does not exist."
            }), 404

        if quantity_resp.quantity < quantity:
            return jsonify({
                "status": "Error",
                "message": "Quantity requested is less than available quantity."
            }), 400

        # Step 2: Add to cart
        add_req = customer_db_pb2.AddItemToCartRequest(
            session_id=session_id,
            item_id=item_id,
            quantity=quantity
        )
        add_resp = customer_db_stub.AddItemToCart(add_req)

        if not add_resp.success:
            return jsonify({
                "status": "Error",
                "message": add_resp.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": f"Item ID {item_id} with quantity {quantity} added to cart."
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error adding item to cart: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to add item to cart."
        }), 500


@app.route('/api/buyers/cart/items/<int:item_id>', methods=['DELETE'])
@auth.require_auth(user_type='buyer')
def remove_item_from_cart(session_id, buyer_id, item_id):
    """Remove item from cart"""
    data = request.json
    quantity = data.get("quantity")

    try:
        request_msg = customer_db_pb2.RemoveItemFromCartRequest(
            session_id=session_id,
            item_id=item_id,
            quantity=quantity
        )
        response = customer_db_stub.RemoveItemFromCart(request_msg)

        if not response.success:
            if "does not exist in cart" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Item ID does not exist in cart"
                }), 404
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        # Determine message based on whether item was fully or partially removed
        message = f"Item ID {item_id} with quantity {quantity} removed from cart."

        return jsonify({
            "status": "OK",
            "message": message
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error removing item from cart: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to remove item from cart."
        }), 500


@app.route('/api/buyers/cart/save', methods=['POST'])
@auth.require_auth(user_type='buyer')
def save_cart(session_id, buyer_id):
    """Save active cart to saved cart"""
    try:
        request_msg = customer_db_pb2.SaveCartRequest(
            session_id=session_id,
            buyer_id=buyer_id
        )
        response = customer_db_stub.SaveCart(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": "Cart saved successfully."
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error saving cart: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to save cart."
        }), 500


@app.route('/api/buyers/cart', methods=['DELETE'])
@auth.require_auth(user_type='buyer')
def clear_cart(session_id, buyer_id):
    """Clear both saved and active cart"""
    try:
        request_msg = customer_db_pb2.ClearCartRequest(
            session_id=session_id,
            buyer_id=buyer_id
        )
        response = customer_db_stub.ClearCart(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": "Cart cleared successfully."
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error clearing cart: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to clear cart."
        }), 500


@app.route('/api/buyers/cart', methods=['GET'])
@auth.require_auth(user_type='buyer')
def display_cart(session_id, buyer_id):
    """Display active cart"""
    try:
        request_msg = customer_db_pb2.GetCartRequest(session_id=session_id)
        response = customer_db_stub.GetCart(request_msg)

        if not response.success:
            if "does not exist" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Cart does not exist for this session."
                }), 404
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        # Convert protobuf map to dict
        cart_dict = dict(response.cart_items.items)

        return jsonify({
            "status": "OK",
            "cart_items": cart_dict
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error displaying cart: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to display cart."
        }), 500


@app.route('/api/buyers/purchases', methods=['POST'])
@auth.require_auth(user_type='buyer')
def make_purchase(session_id, buyer_id):
    """Make a purchase (stubbed)"""
    data = request.json
    cardholder_name = data.get("cardholder_name")
    card_number = data.get("card_number")
    expiry_month = data.get("expiry_month")
    expiry_year = data.get("expiry_year")
    security_code = data.get("security_code")

    customer_db_conn = customer_db_pool.getconn()
    product_db_conn = product_db_pool.getconn()
    try:
        product_cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
        customer_cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        customer_cursor.execute(
            "SELECT username FROM buyers WHERE buyer_id  = %s",
            (buyer_id,),
        )
        result = customer_cursor.fetchone()

        if not result:
            return jsonify({
                "status": "Error",
                "message": "Cannot find buyer with buyer id."
            }), 404

        customer_cursor.execute(
            "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
            (session_id,)
        )
        active_cart_result = customer_cursor.fetchone()

        if not active_cart_result:
            return jsonify({
                "status": "Error",
                "message": "Active cart does not exist."
            }), 404

        total_amount = 0
        item_ids = []
        for row in active_cart_result:
            item_id, quantity = row["item_id"], row["quantity"]
            product_cursor.execute(
                "SELECT sale_price FROM products WHERE item_id = %s AND quantity > %s",
                (item_id, quantity)
            )
            sale_price_result = product_cursor.fetchone()

            if not sale_price_result:
                return jsonify({
                    "status": "Error",
                    "message": "Item does not exist or quantity is too low."
                }), 404

            sale_price = sale_price_result["sale_price"]
            total_amount += sale_price * quantity
            item_ids.append(item_id)
        
        result = soap_client.service.process_payment(cardholder_name, card_number, expiry_month, expiry_year, security_code)

        if result == "No":
            return jsonify({
                "status": "Error",
                "message": "Payment declined."
            }), 401
        elif result == "Yes":
            customer_cursor.execute(
                "INSERT INTO transactions (buyer_id, cardholder_name, card_number, expiry_month, expiry_year, security_code, amount) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING transaction_id",
                (buyer_id, cardholder_name, card_number, expiry_month, expiry_year, security_code, amount)
            )
            transaction_id = cursor.fetchone()["transaction_id"]

            customer_cursor.execute(
                "INSERT INTO purchases (buyer_id, transaction_id, item_ids) VALUES (%s, %s, %s) RETURNING purchase_id",
                (buyer_id, transaction_id, item_ids)
            )
            purchase_id = cursor.fetchone()["purchase_id"]

            # update products quantities
            # clear active cart

            return jsonify({
                "status": "OK",
                "message": "Payment successful.",
                "transaction_id": transaction_id,
                "purchase_id": purchase_id
            }), 200

        return jsonify({
            "status": "OK",
            "message": "Unknown error while processing payment. Failed to make purchase."
        }), 401

    except Exception as e:
        return jsonify({
            "status": "Error",
            "message": "Failed to make purchase."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/feedback', methods=['POST'])
@auth.require_auth(user_type='buyer')
def provide_feedback(session_id, buyer_id):
    """Provide feedback for an item (multi-step gRPC operation)"""
    data = request.json
    item_id = data.get("item_id")
    feedback = data.get("feedback")  # 0 or 1

    if feedback not in [0, 1]:
        return jsonify({
            "status": "Error",
            "message": "Invalid feedback value. Must be 0 or 1."
        }), 400

    try:
        # Step 1: Get seller_id for the item
        seller_req = product_db_pb2.GetItemSellerRequest(item_id=item_id)
        seller_resp = product_db_stub.GetItemSeller(seller_req)

        if not seller_resp.success:
            return jsonify({
                "status": "Error",
                "message": f"Item with ID {item_id} not found."
            }), 404

        seller_id = seller_resp.seller_id

        # Step 2: Update item feedback
        item_feedback_req = product_db_pb2.UpdateItemFeedbackRequest(
            item_id=item_id,
            thumbs_up=(feedback == 1)
        )
        item_feedback_resp = product_db_stub.UpdateItemFeedback(item_feedback_req)

        if not item_feedback_resp.success:
            return jsonify({
                "status": "Error",
                "message": "Failed to update item feedback."
            }), 500

        # Step 3: Update seller feedback (don't fail entire operation if this fails)
        try:
            seller_feedback_req = customer_db_pb2.UpdateSellerFeedbackRequest(
                seller_id=seller_id,
                thumbs_up=(feedback == 1)
            )
            seller_feedback_resp = customer_db_stub.UpdateSellerFeedback(seller_feedback_req)

            if not seller_feedback_resp.success:
                print(f"Warning: Failed to update seller feedback: {seller_feedback_resp.error_message}")
        except grpc.RpcError as e:
            print(f"Warning: gRPC error updating seller feedback: {e.code()} - {e.details()}")

        return jsonify({
            "status": "OK",
            "message": "Feedback recorded successfully."
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error providing feedback: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to provide feedback."
        }), 500


@app.route('/api/buyers/sellers/<int:seller_id>/rating', methods=['GET'])
@auth.require_auth(user_type='buyer')
def get_seller_rating(session_id, buyer_id, seller_id):
    """Get seller rating"""
    try:
        request_msg = customer_db_pb2.GetSellerRatingRequest(seller_id=seller_id)
        response = customer_db_stub.GetSellerRating(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Seller not found."
            }), 404

        return jsonify({
            "status": "OK",
            "thumbs_up": response.rating.thumbs_up,
            "thumbs_down": response.rating.thumbs_down
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error getting seller rating: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to get seller rating."
        }), 500


@app.route('/api/buyers/purchases', methods=['GET'])
@auth.require_auth(user_type='buyer')
def get_buyer_purchases(session_id, buyer_id):
    """Get buyer purchase history (stubbed)"""
    return jsonify({
        "status": "OK",
        "purchases": {}
    }), 200


if __name__ == "__main__":
    # Initialize gRPC clients before starting server
    init_grpc_clients()

    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "6000"))

    print(f"Starting Buyer Flask server on {server_host}:{server_port}")
    app.run(host=server_host, port=server_port, debug=False, threaded=True)
