"""
Authentication utilities for buyer server
"""
from functools import wraps
from flask import request, jsonify
from psycopg2 import extras


def require_auth(customer_db_pool):
    """
    Decorator factory to validate buyer session for protected endpoints.

    Args:
        customer_db_pool: PostgreSQL connection pool for customer database

    Returns:
        Decorator function that validates session and injects session_id and buyer_id
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    "status": "Error",
                    "message": "Missing or invalid authorization header"
                }), 401

            # Extract session ID from Bearer token
            session_id = auth_header.replace('Bearer ', '').strip()

            # Validate session
            customer_db_conn = customer_db_pool.getconn()
            try:
                cursor = customer_db_conn.cursor(cursor_factory=extras.RealDictCursor)

                # Check if session exists and is not expired (5 minute timeout)
                cursor.execute(
                    "SELECT buyer_id FROM buyer_sessions WHERE session_id = %s "
                    "AND last_active_at > NOW() - INTERVAL '5 minutes'",
                    (session_id,)
                )
                result = cursor.fetchone()

                if not result:
                    # Session expired or invalid, delete it
                    cursor.execute(
                        "DELETE FROM buyer_sessions WHERE session_id = %s",
                        (session_id,)
                    )
                    customer_db_conn.commit()
                    return jsonify({
                        "status": "Timeout",
                        "message": "Session expired. Please log in again."
                    }), 401

                buyer_id = result["buyer_id"]

                # Update last_active_at timestamp
                cursor.execute(
                    "UPDATE buyer_sessions SET last_active_at = NOW() WHERE session_id = %s",
                    (session_id,)
                )
                customer_db_conn.commit()

                # Inject session_id and buyer_id into the route function
                return f(session_id=session_id, buyer_id=buyer_id, *args, **kwargs)

            except Exception as e:
                print(f"Error validating session: {e}")
                return jsonify({
                    "status": "Error",
                    "message": "Failed to validate session"
                }), 500
            finally:
                customer_db_pool.putconn(customer_db_conn)

        return decorated_function
    return decorator
