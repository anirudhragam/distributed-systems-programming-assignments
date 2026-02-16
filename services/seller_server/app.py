"""
Flask-based RESTful API server for seller operations
"""
import os
import uuid
from flask import Flask, request, jsonify
from psycopg2 import _psycopg, extensions, extras, pool

from auth import require_auth

# Define extension to convert DECIMAL to FLOAT
DEC2FLOAT = extensions.new_type(_psycopg.DECIMAL.values, "DEC2FLOAT", extensions.FLOAT)

# Initialize Flask app
app = Flask(__name__)

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

print("Seller server initialized with Flask")


@app.route('/api/sellers/accounts', methods=['POST'])
def create_account():
    """Create a new seller account"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Check if username already exists
        cursor.execute(
            "SELECT seller_id FROM sellers WHERE username = %s", (username,)
        )
        result = cursor.fetchone()
        if result:
            return jsonify({
                "status": "Error",
                "message": "Username already exists."
            }), 409

        # Insert new seller into the database
        cursor.execute(
            "INSERT INTO sellers (username, passwd) VALUES (%s, %s) RETURNING seller_id",
            (username, password),
        )
        seller_id = cursor.fetchone()["seller_id"]
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "seller_id": seller_id
        }), 201

    except Exception as e:
        print(f"Error creating seller account: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to create account."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/sellers/sessions', methods=['POST'])
def login():
    """Login and create a new session"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Verify username and password
        cursor.execute(
            "SELECT seller_id, username FROM sellers WHERE username = %s AND passwd = %s",
            (username, password),
        )
        result = cursor.fetchone()
        if not result:
            return jsonify({
                "status": "Error",
                "message": "Username/Password combination does not exist."
            }), 401

        seller_id = result["seller_id"]
        username = result["username"]

        # Create a new session
        session_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO seller_sessions (session_id, seller_id) VALUES (%s, %s)",
            (session_id, seller_id),
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "session_id": session_id,
            "seller_id": seller_id,
            "message": f"I've seen enough. Welcome back {username}"
        }), 201

    except Exception as e:
        print(f"Error logging into seller account: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log in to seller account."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/sellers/sessions', methods=['DELETE'])
@require_auth(customer_db_pool)
def logout(session_id, seller_id):
    """Logout and delete the session"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Delete the session from the seller_sessions table
        cursor.execute(
            "DELETE FROM seller_sessions WHERE session_id = %s", (session_id,)
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": "Successfully logged out."
        }), 200

    except Exception as e:
        print(f"Error logging out of seller session: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log out of seller session."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/sellers/rating', methods=['GET'])
@require_auth(customer_db_pool)
def get_seller_rating(session_id, seller_id):
    """Get seller rating (thumbs up/down counts)"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Fetch thumbs up and thumbs down counts
        cursor.execute(
            "SELECT thumbs_up, thumbs_down FROM sellers WHERE seller_id = %s",
            (seller_id,),
        )
        result = cursor.fetchone()
        if not result:
            return jsonify({
                "status": "Error",
                "message": "Seller ID does not exist."
            }), 404

        return jsonify({
            "status": "OK",
            "thumbs_up": result["thumbs_up"],
            "thumbs_down": result["thumbs_down"]
        }), 200

    except Exception as e:
        print(f"Error getting seller rating: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to get seller rating."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/sellers/items', methods=['POST'])
@require_auth(customer_db_pool)
def register_item_for_sale(session_id, seller_id):
    """Register a new item for sale"""
    data = request.json
    item_name = data.get("item_name")
    category = data.get("category")
    keywords = data.get("keywords")
    condition = data.get("condition")
    sale_price = data.get("sale_price")
    quantity = data.get("quantity")

    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Insert new item into the products table
        cursor.execute(
            "INSERT INTO products (seller_id, item_name, category, keywords, condition, sale_price, quantity) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING item_id",
            (seller_id, item_name, category, keywords, condition, sale_price, quantity),
        )
        item_id = cursor.fetchone()["item_id"]
        product_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": f"Item {item_name} registered for sale successfully with Item ID {item_id}"
        }), 201

    except Exception as e:
        print(f"Error registering item for sale: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to register item for sale."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


@app.route('/api/sellers/items/<int:item_id>/price', methods=['PATCH'])
@require_auth(customer_db_pool)
def change_item_price(session_id, seller_id, item_id):
    """Change the price of an item"""
    data = request.json
    new_price = data.get("new_price")

    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Update the item price
        cursor.execute(
            "UPDATE products SET sale_price = %s WHERE item_id = %s AND seller_id = %s",
            (new_price, item_id, int(seller_id)),
        )

        if cursor.rowcount == 0:
            return jsonify({
                "status": "Error",
                "message": "Item ID does not exist or does not belong to the seller."
            }), 404

        product_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": f"Item price for item {item_id} updated successfully to {new_price}"
        }), 200

    except Exception as e:
        print(f"Error changing item price: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to change item price."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


@app.route('/api/sellers/items/<int:item_id>/quantity', methods=['PATCH'])
@require_auth(customer_db_pool)
def update_units_for_sale(session_id, seller_id, item_id):
    """Update the quantity of units available for sale"""
    data = request.json
    quantity_change = data.get("quantity_change")

    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Fetch current quantity
        cursor.execute(
            "SELECT quantity FROM products WHERE item_id = %s AND seller_id = %s",
            (item_id, seller_id),
        )
        result = cursor.fetchone()
        if not result:
            return jsonify({
                "status": "Error",
                "message": "Item ID does not exist or does not belong to the seller."
            }), 404

        current_quantity = result["quantity"]
        new_quantity = current_quantity - quantity_change

        if new_quantity < 0:
            return jsonify({
                "status": "Error",
                "message": "Available units cannot be negative."
            }), 400

        # Update the item quantity
        cursor.execute(
            "UPDATE products SET quantity = %s WHERE item_id = %s AND seller_id = %s",
            (new_quantity, item_id, int(seller_id)),
        )
        product_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": f"Item quantity for item {item_id} updated successfully to {new_quantity}"
        }), 200

    except Exception as e:
        print(f"Error updating item quantity: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to update item quantity."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


@app.route('/api/sellers/items', methods=['GET'])
@require_auth(customer_db_pool)
def display_items_for_sale(session_id, seller_id):
    """Display all items for sale by the seller"""
    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        cursor.execute(
            "SELECT item_id, item_name, category, keywords, condition, sale_price::float, quantity, "
            "thumbs_up, thumbs_down FROM products WHERE seller_id = %s AND quantity > 0",
            (seller_id,),
        )
        items = cursor.fetchall()

        if not items:
            return jsonify({
                "status": "OK",
                "message": "No items for sale."
            }), 200

        return jsonify({
            "status": "OK",
            "items": items
        }), 200

    except Exception as e:
        print(f"Error displaying items for sale: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to display items for sale."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "5000"))

    print(f"Starting Seller Flask server on {server_host}:{server_port}")
    app.run(host=server_host, port=server_port, debug=False, threaded=True)
