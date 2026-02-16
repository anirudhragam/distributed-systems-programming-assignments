"""
Authentication utilities for seller server (gRPC-based)
"""
from functools import wraps
from flask import request, jsonify
import grpc
import sys

# Add generated protobuf path
sys.path.insert(0, '/app/generated')
import customer_db_pb2
import customer_db_pb2_grpc

# Global gRPC stub (injected by app.py)
customer_db_stub = None


def set_customer_db_stub(stub):
    """
    Set the gRPC stub for customer database service.
    Called by app.py during initialization.

    Args:
        stub: CustomerDBServiceStub instance
    """
    global customer_db_stub
    customer_db_stub = stub


def require_auth(user_type='seller'):
    """
    Decorator factory to validate session for protected endpoints using gRPC.

    Args:
        user_type: 'seller' or 'buyer' (default: 'seller')

    Returns:
        Decorator function that validates session and injects session_id and user_id
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

            try:
                if user_type == 'seller':
                    # Validate seller session via gRPC
                    validate_req = customer_db_pb2.ValidateSellerSessionRequest(
                        session_id=session_id
                    )
                    validate_resp = customer_db_stub.ValidateSellerSession(validate_req)

                    if not validate_resp.valid:
                        return jsonify({
                            "status": "Timeout",
                            "message": "Session expired. Please log in again."
                        }), 401

                    # Update session timestamp via gRPC
                    update_req = customer_db_pb2.UpdateSellerSessionTimestampRequest(
                        session_id=session_id
                    )
                    customer_db_stub.UpdateSellerSessionTimestamp(update_req)

                    # Inject session_id and seller_id into route function
                    return f(session_id=session_id, seller_id=validate_resp.seller_id, *args, **kwargs)

                else:  # buyer
                    # Validate buyer session via gRPC
                    validate_req = customer_db_pb2.ValidateBuyerSessionRequest(
                        session_id=session_id
                    )
                    validate_resp = customer_db_stub.ValidateBuyerSession(validate_req)

                    if not validate_resp.valid:
                        return jsonify({
                            "status": "Timeout",
                            "message": "Session expired. Please log in again."
                        }), 401

                    # Update session timestamp via gRPC
                    update_req = customer_db_pb2.UpdateBuyerSessionTimestampRequest(
                        session_id=session_id
                    )
                    customer_db_stub.UpdateBuyerSessionTimestamp(update_req)

                    # Inject session_id and buyer_id into route function
                    return f(session_id=session_id, buyer_id=validate_resp.buyer_id, *args, **kwargs)

            except grpc.RpcError as e:
                print(f"gRPC error validating session: {e.code()} - {e.details()}")
                return jsonify({
                    "status": "Error",
                    "message": "Authentication service unavailable"
                }), 503

        return decorated_function
    return decorator
