"""
Flask-based RESTful API server for buyer operations
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

print("Buyer server initialized with Flask")

@app.route('/api/buyers/accounts', methods=['POST'])
def create_account():
    """Create a new buyer account"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Check if username already exists
        cursor.execute(
            "SELECT buyer_id FROM buyers WHERE username = %s", (username,)
        )
        result = cursor.fetchone()
        if result:
            return jsonify({
                "status": "Error",
                "message": "Username already exists."
            }), 409

        # Insert new buyer and create saved cart
        saved_cart_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO buyers (username, passwd, saved_cart_id) VALUES (%s, %s, %s) RETURNING buyer_id",
            (username, password, saved_cart_id),
        )
        buyer_id = cursor.fetchone()["buyer_id"]

        # Create saved cart
        cursor.execute(
            "INSERT INTO saved_carts (saved_cart_id, buyer_id) VALUES (%s, %s)",
            (saved_cart_id, buyer_id),
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "buyer_id": buyer_id
        }), 201

    except Exception as e:
        print(f"Error creating buyer account: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to create account."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/sessions', methods=['POST'])
def login():
    """Login and create a new session with active cart"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Verify username and password
        cursor.execute(
            "SELECT buyer_id, username FROM buyers WHERE username = %s AND passwd = %s",
            (username, password),
        )
        result = cursor.fetchone()
        if not result:
            return jsonify({
                "status": "Error",
                "message": "Username/Password combination does not exist."
            }), 401

        buyer_id = result["buyer_id"]
        username = result["username"]

        # Create a new session and active cart
        session_id = str(uuid.uuid4())
        active_cart_id = str(uuid.uuid4())

        cursor.execute(
            "INSERT INTO buyer_sessions (session_id, buyer_id, active_cart_id) VALUES (%s, %s, %s)",
            (session_id, buyer_id, active_cart_id),
        )

        # Load saved cart into active cart
        cursor.execute(
            "SELECT saved_cart_items FROM saved_carts WHERE saved_cart_id = (SELECT saved_cart_id FROM buyers WHERE buyer_id = %s)",
            (buyer_id,),
        )
        result = cursor.fetchone()
        saved_cart_items = result["saved_cart_items"] if result else {}

        cursor.execute(
            "INSERT INTO active_carts (active_cart_id, session_id, active_cart_items) VALUES (%s, %s, %s)",
            (active_cart_id, session_id, extras.Json(saved_cart_items)),
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "session_id": session_id,
            "buyer_id": buyer_id,
            "message": f"I've seen enough. Welcome back {username}"
        }), 201

    except Exception as e:
        print(f"Error logging into buyer account: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log in to buyer account."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/sessions', methods=['DELETE'])
@require_auth(customer_db_pool)
def logout(session_id, buyer_id):
    """Logout and delete the session"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Delete the session (foreign key constraint deletes active cart)
        cursor.execute(
            "DELETE FROM buyer_sessions WHERE session_id = %s", (session_id,)
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": "Successfully logged out."
        }), 200

    except Exception as e:
        print(f"Error logging out of buyer session: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to log out of buyer session."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/items/search', methods=['GET'])
@require_auth(customer_db_pool)
def search_items(session_id, buyer_id):
    """Search for items by category and keywords"""
    category = request.args.get("category", type=int)
    keywords = request.args.getlist("keywords")

    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        if not keywords:
            # Query by category only
            cursor.execute(
                "SELECT * FROM products WHERE category = %s",
                (category,),
            )
        else:
            # Query by category and keywords
            cursor.execute(
                "SELECT * FROM products WHERE category = %s AND keywords && %s::varchar[]",
                (category, keywords),
            )

        results = cursor.fetchall()
        return jsonify({
            "status": "OK",
            "items": results
        }), 200

    except Exception as e:
        print(f"Error searching items: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to search items."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


@app.route('/api/buyers/items/<int:item_id>', methods=['GET'])
@require_auth(customer_db_pool)
def get_item(session_id, buyer_id, item_id):
    """Get details of a specific item"""
    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        cursor.execute("SELECT * FROM products WHERE item_id = %s", (item_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({
                "status": "Error",
                "message": "Item not found."
            }), 404

        return jsonify({
            "status": "OK",
            "item": result
        }), 200

    except Exception as e:
        print(f"Error getting item details: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to get item details."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)


@app.route('/api/buyers/cart/items/<int:item_id>', methods=['POST'])
@require_auth(customer_db_pool)
def add_item_to_cart(session_id, buyer_id, item_id):
    """Add item to cart"""
    data = request.json
    quantity = data.get("quantity")

    # Validate item and quantity
    product_db_conn = product_db_pool.getconn()
    try:
        cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute(
            "SELECT quantity FROM products WHERE item_id = %s", (item_id,)
        )
        result = cursor.fetchone()
        if not result:
            return jsonify({
                "status": "Error",
                "message": "Item ID does not exist."
            }), 404

        if result["quantity"] < quantity:
            return jsonify({
                "status": "Error",
                "message": "Quantity requested is less than available quantity."
            }), 400
    finally:
        product_db_pool.putconn(product_db_conn)

    # Add to cart
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

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

        return jsonify({
            "status": "OK",
            "message": f"Item ID {item_id} with quantity {quantity} added to cart."
        }), 200

    except Exception as e:
        print(f"Error adding item to cart: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to add item to cart."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/cart/items/<int:item_id>', methods=['DELETE'])
@require_auth(customer_db_pool)
def remove_item_from_cart(session_id, buyer_id, item_id):
    """Remove item from cart"""
    data = request.json
    quantity = data.get("quantity")

    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Get current quantity in cart
        cursor.execute(
            "SELECT (active_cart_items->>%s)::int AS cart_quantity FROM active_carts WHERE session_id = %s",
            (str(item_id), session_id),
        )
        result = cursor.fetchone()
        cart_quantity = result["cart_quantity"]

        if cart_quantity is None:
            return jsonify({
                "status": "Error",
                "message": "Item ID does not exist in cart"
            }), 404

        # If removing all, delete the key; otherwise decrement
        if cart_quantity == quantity:
            cursor.execute(
                "UPDATE active_carts SET active_cart_items = active_cart_items - %s WHERE session_id = %s",
                (str(item_id), session_id),
            )
            message = f"Removed item ID {item_id} from cart."
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
                AND (active_cart_items->>%s)::int > %s
                """,
                (str(item_id), str(item_id), quantity, session_id, str(item_id), quantity),
            )
            message = f"Item ID {item_id} with quantity {quantity} removed from cart."

        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": message
        }), 200

    except Exception as e:
        print(f"Error removing item from cart: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to remove item from cart."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/cart/save', methods=['POST'])
@require_auth(customer_db_pool)
def save_cart(session_id, buyer_id):
    """Save active cart to saved cart"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Get active cart items
        cursor.execute(
            "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
            (session_id,),
        )
        result = cursor.fetchone()
        active_cart_items = result["active_cart_items"]

        # Get saved cart ID
        cursor.execute(
            "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s", (buyer_id,)
        )
        saved_cart_id = cursor.fetchone()["saved_cart_id"]

        # Update saved cart
        cursor.execute(
            "UPDATE saved_carts SET saved_cart_items = %s WHERE saved_cart_id = %s",
            (extras.Json(active_cart_items), saved_cart_id),
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": "Cart saved successfully."
        }), 200

    except Exception as e:
        print(f"Error saving cart: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to save cart."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/cart', methods=['DELETE'])
@require_auth(customer_db_pool)
def clear_cart(session_id, buyer_id):
    """Clear both saved and active cart"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Get saved cart ID
        cursor.execute(
            "SELECT saved_cart_id FROM buyers WHERE buyer_id = %s", (buyer_id,)
        )
        saved_cart_id = cursor.fetchone()["saved_cart_id"]

        # Clear saved cart
        cursor.execute(
            "UPDATE saved_carts SET saved_cart_items = '{}'::jsonb WHERE saved_cart_id = %s",
            (saved_cart_id,),
        )

        # Get active cart ID
        cursor.execute(
            "SELECT active_cart_id FROM buyer_sessions WHERE session_id = %s",
            (session_id,),
        )
        active_cart_id = cursor.fetchone()["active_cart_id"]

        # Clear active cart
        cursor.execute(
            "UPDATE active_carts SET active_cart_items = '{}'::jsonb WHERE active_cart_id = %s",
            (active_cart_id,),
        )
        customer_db_conn.commit()

        return jsonify({
            "status": "OK",
            "message": "Cart cleared successfully."
        }), 200

    except Exception as e:
        print(f"Error clearing cart: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to clear cart."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/cart', methods=['GET'])
@require_auth(customer_db_pool)
def display_cart(session_id, buyer_id):
    """Display active cart"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        cursor.execute(
            "SELECT active_cart_items FROM active_carts WHERE session_id = %s",
            (session_id,),
        )
        result = cursor.fetchone()

        if not result:
            return jsonify({
                "status": "Error",
                "message": "Cart does not exist for this session."
            }), 404

        return jsonify({
            "status": "OK",
            "cart_items": result["active_cart_items"]
        }), 200

    except Exception as e:
        print(f"Error displaying cart: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to display cart."
        }), 500
    finally:
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/purchases', methods=['POST'])
@require_auth(customer_db_pool)
def make_purchase(session_id, buyer_id):
    """Make a purchase (stubbed)"""
    return jsonify({
        "status": "OK",
        "message": "Purchase functionality not implemented yet."
    }), 501


@app.route('/api/buyers/feedback', methods=['POST'])
@require_auth(customer_db_pool)
def provide_feedback(session_id, buyer_id):
    """Provide feedback for an item"""
    data = request.json
    item_id = data.get("item_id")
    feedback = data.get("feedback")  # 0 or 1

    if feedback not in [0, 1]:
        return jsonify({
            "status": "Error",
            "message": "Invalid feedback value. Must be 0 or 1."
        }), 400

    product_db_conn = product_db_pool.getconn()
    customer_db_conn = customer_db_pool.getconn()

    try:
        product_cursor = product_db_conn.cursor(cursor_factory=extras.RealDictCursor)
        customer_cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        # Get seller_id for the item
        product_cursor.execute(
            "SELECT seller_id FROM products WHERE item_id = %s", (item_id,)
        )
        item_result = product_cursor.fetchone()

        if not item_result:
            return jsonify({
                "status": "Error",
                "message": f"Item with ID {item_id} not found."
            }), 404

        seller_id = item_result["seller_id"]

        # Update feedback
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

        return jsonify({
            "status": "OK",
            "message": "Feedback recorded successfully."
        }), 200

    except Exception as e:
        print(f"Error providing feedback: {e}")
        return jsonify({
            "status": "Error",
            "message": "Failed to provide feedback."
        }), 500
    finally:
        product_db_pool.putconn(product_db_conn)
        customer_db_pool.putconn(customer_db_conn)


@app.route('/api/buyers/sellers/<int:seller_id>/rating', methods=['GET'])
@require_auth(customer_db_pool)
def get_seller_rating(session_id, buyer_id, seller_id):
    """Get seller rating"""
    customer_db_conn = customer_db_pool.getconn()
    try:
        cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

        cursor.execute(
            "SELECT thumbs_up, thumbs_down FROM sellers WHERE seller_id = %s",
            (seller_id,),
        )
        result = cursor.fetchone()

        if not result:
            return jsonify({
                "status": "Error",
                "message": "Seller not found."
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


@app.route('/api/buyers/purchases', methods=['GET'])
@require_auth(customer_db_pool)
def get_buyer_purchases(session_id, buyer_id):
    """Get buyer purchase history (stubbed)"""
    return jsonify({
        "status": "OK",
        "purchases": {}
    }), 200


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    server_host = os.getenv("SERVER_HOST", "0.0.0.0")
    server_port = int(os.getenv("SERVER_PORT", "6000"))

    print(f"Starting Buyer Flask server on {server_host}:{server_port}")
    app.run(host=server_host, port=server_port, debug=False, threaded=True)
