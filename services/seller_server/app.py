"""
Flask-based RESTful API server for seller operations (gRPC-based)
"""
import os
import time
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

    product_db_host = os.getenv("PRODUCT_DB_HOST", "product-db")
    product_db_port = os.getenv("PRODUCT_DB_PORT", "50051")
    customer_db_host = os.getenv("CUSTOMER_DB_HOST", "customer-db")
    customer_db_port = os.getenv("CUSTOMER_DB_PORT", "50052")

    for attempt in range(30):
        try:
            product_db_channel = grpc.insecure_channel(f'{product_db_host}:{product_db_port}')
            product_db_stub = product_db_pb2_grpc.ProductDBServiceStub(product_db_channel)
            grpc.channel_ready_future(product_db_channel).result(timeout=5)
            print(f"Connected to product-db at {product_db_host}:{product_db_port}")
            break
        except grpc.FutureTimeoutError:
            print(f"Waiting for product-db at {product_db_host}:{product_db_port} (attempt {attempt+1}/30)...")
            time.sleep(10)

    for attempt in range(30):
        try:
            customer_db_channel = grpc.insecure_channel(f'{customer_db_host}:{customer_db_port}')
            customer_db_stub = customer_db_pb2_grpc.CustomerDBServiceStub(customer_db_channel)
            grpc.channel_ready_future(customer_db_channel).result(timeout=5)
            print(f"Connected to customer-db at {customer_db_host}:{customer_db_port}")
            break
        except grpc.FutureTimeoutError:
            print(f"Waiting for customer-db at {customer_db_host}:{customer_db_port} (attempt {attempt+1}/30)...")
            time.sleep(10)

    # Inject customer_db_stub into auth module
    auth.set_customer_db_stub(customer_db_stub)

    print("Seller server initialized with gRPC clients")


@app.route('/api/sellers/accounts', methods=['POST'])
def create_account():
    """Create a new seller account"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        request_msg = customer_db_pb2.CreateSellerRequest(
            username=username,
            password=password
        )
        response = customer_db_stub.CreateSeller(request_msg)

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
            "seller_id": response.seller_id
        }), 201

    except grpc.RpcError as e:
        print(f"gRPC error creating seller account: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to create account."
        }), 500


@app.route('/api/sellers/sessions', methods=['POST'])
def login():
    """Login and create a new session"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    try:
        request_msg = customer_db_pb2.SellerLoginRequest(
            username=username,
            password=password
        )
        response = customer_db_stub.SellerLogin(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Username/Password combination does not exist."
            }), 401

        return jsonify({
            "status": "OK",
            "session_id": response.session_id,
            "seller_id": response.seller_id,
            "message": f"I've seen enough. Welcome back {response.username}"
        }), 201

    except grpc.RpcError as e:
        print(f"gRPC error logging into seller account: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log in to seller account."
        }), 500


@app.route('/api/sellers/sessions', methods=['DELETE'])
@auth.require_auth(user_type='seller')
def logout(session_id, seller_id):
    """Logout and delete the session"""
    try:
        request_msg = customer_db_pb2.LogoutRequest(session_id=session_id)
        response = customer_db_stub.SellerLogout(request_msg)

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
        print(f"gRPC error logging out of seller session: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log out of seller session."
        }), 500


@app.route('/api/sellers/rating', methods=['GET'])
@auth.require_auth(user_type='seller')
def get_seller_rating(session_id, seller_id):
    """Get seller rating (thumbs up/down counts)"""
    try:
        request_msg = customer_db_pb2.GetSellerRatingRequest(seller_id=seller_id)
        response = customer_db_stub.GetSellerRating(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": "Seller ID does not exist."
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


@app.route('/api/sellers/items', methods=['POST'])
@auth.require_auth(user_type='seller')
def register_item_for_sale(session_id, seller_id):
    """Register a new item for sale"""
    data = request.json
    item_name = data.get("item_name")
    category = data.get("category")
    keywords = data.get("keywords")
    condition = data.get("condition")
    sale_price = data.get("sale_price")
    quantity = data.get("quantity")

    try:
        request_msg = product_db_pb2.RegisterItemRequest(
            seller_id=seller_id,
            item_name=item_name,
            category=category,
            keywords=keywords,  # list automatically converts to repeated
            condition=condition,
            sale_price=sale_price,
            quantity=quantity
        )
        response = product_db_stub.RegisterItem(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": f"Item {item_name} registered for sale successfully with Item ID {response.item_id}"
        }), 201

    except grpc.RpcError as e:
        print(f"gRPC error registering item for sale: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to register item for sale."
        }), 500


@app.route('/api/sellers/items/<int:item_id>/price', methods=['PATCH'])
@auth.require_auth(user_type='seller')
def change_item_price(session_id, seller_id, item_id):
    """Change the price of an item"""
    data = request.json
    new_price = data.get("new_price")

    try:
        request_msg = product_db_pb2.UpdateItemPriceRequest(
            item_id=item_id,
            seller_id=seller_id,
            new_price=new_price
        )
        response = product_db_stub.UpdateItemPrice(request_msg)

        if not response.success:
            if "does not exist" in response.error_message.lower() or "does not belong" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Item ID does not exist or does not belong to the seller."
                }), 404
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": f"Item price for item {item_id} updated successfully to {new_price}"
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error changing item price: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to change item price."
        }), 500


@app.route('/api/sellers/items/<int:item_id>/quantity', methods=['PATCH'])
@auth.require_auth(user_type='seller')
def update_units_for_sale(session_id, seller_id, item_id):
    """Update the quantity of units available for sale"""
    data = request.json
    quantity_change = data.get("quantity_change")

    try:
        request_msg = product_db_pb2.UpdateItemQuantityRequest(
            item_id=item_id,
            seller_id=seller_id,
            quantity_change=quantity_change
        )
        response = product_db_stub.UpdateItemQuantity(request_msg)

        if not response.success:
            if "does not exist" in response.error_message.lower() or "does not belong" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Item ID does not exist or does not belong to the seller."
                }), 404
            if "negative" in response.error_message.lower():
                return jsonify({
                    "status": "Error",
                    "message": "Available units cannot be negative."
                }), 400
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        return jsonify({
            "status": "OK",
            "message": f"Item quantity for item {item_id} updated successfully to {response.new_quantity}"
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error updating item quantity: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to update item quantity."
        }), 500


@app.route('/api/sellers/items', methods=['GET'])
@auth.require_auth(user_type='seller')
def display_items_for_sale(session_id, seller_id):
    """Display all items for sale by the seller"""
    try:
        request_msg = product_db_pb2.GetItemsBySellerRequest(seller_id=seller_id)
        response = product_db_stub.GetItemsBySeller(request_msg)

        if not response.success:
            return jsonify({
                "status": "Error",
                "message": response.error_message
            }), 500

        # Convert protobuf Product messages to dict
        items = []
        for item in response.items:
            items.append({
                "item_id": item.item_id,
                "item_name": item.item_name,
                "category": item.category,
                "keywords": list(item.keywords),
                "condition": item.condition,
                "sale_price": item.sale_price,
                "quantity": item.quantity,
                "thumbs_up": item.thumbs_up,
                "thumbs_down": item.thumbs_down
            })

        if not items:
            return jsonify({
                "status": "OK",
                "message": "No items for sale."
            }), 200

        return jsonify({
            "status": "OK",
            "items": items
        }), 200

    except grpc.RpcError as e:
        print(f"gRPC error displaying items for sale: {e.code()} - {e.details()}")
        return jsonify({
            "status": "Error",
            "message": "Failed to display items for sale."
        }), 500


if __name__ == "__main__":
    # Initialize gRPC clients before starting server
    init_grpc_clients()

    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "5000"))

    print(f"Starting Seller Flask server on {server_host}:{server_port}")
    app.run(host=server_host, port=server_port, debug=False, threaded=True)
