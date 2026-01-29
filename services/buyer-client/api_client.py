# API client for communicating with buyer server

import socket
from utils.socket_utils import send_message, recv_message
from session import BuyerSession

class BuyerAPIClient:
    """Client for making API calls to the buyer backend server"""

    def __init__(self, server_host: str = "buyer-server", server_port: int = 6000):
        self.server_host = server_host
        self.server_port = server_port
        self.connection = None
        self.connect()
    
    def send_message_with_reconnect(self, message: dict):
        """Function to send message with reconnect logic"""
        if self.connection is not None:
            try:
                send_message(self.connection, message)
                response = recv_message(self.connection)
                return response
            except (ConnectionError, socket.error):
                print("Connection lost. Reconnecting...")
                self.connect()
                send_message(self.connection, message)
                response = recv_message(self.connection)
                return response
        else:
            # handle this case
            pass
        
    def connect(self):
        """Function to establish TCP connection to the seller server"""
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.settimeout(60*15)  
            self.connection.connect((self.server_host, self.server_port))
        except Exception as e:
            print(f"Error connecting to seller server: {e}")
            self.connection = None

    def create_account(self, username: str, password: str):
        """Function to send TCP requests to the buyer server, to create a new buyer account."""
        payload = {
            "operation": "CreateAccount",
            "username": username,
            "password": password
        }
        response = self.send_message_with_reconnect(payload)
        return response
    
    def login(self, username: str, password: str):
        """Function to send TCP requests to the buyer server, to login an existing buyer and start a session."""
        payload = {
            "operation": "Login",
            "username": username,
            "password": password
        }
        response = self.send_message_with_reconnect(payload)
        return response
    
    def logout(self, session: BuyerSession):
        """Function to send TCP requests to the buyer server, to logout an existing buyer."""
        payload = {
            "operation": "Logout",
            "session_id": session.session_id,
        }
        response = self.send_message_with_reconnect(payload)
        return response
    
    def search_items(self, session: BuyerSession, category: int, keywords: list[str]):
        """Function to send TCP request to search items"""
        payload = {
            "operation": "SearchItemsForSale",
            "session_id": session.session_id,
            "category": category,
            "keywords": keywords
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def get_item(self, session: BuyerSession, item_id: int):
        """Function to send TCP request to get attributes of an item"""
        payload = {
            "operation": "GetItem",
            "session_id": session.session_id,
            "item_id": item_id
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def add_item_to_cart(self, session: BuyerSession, item_id: int, quantity: int):
        """Function to send TCP request to add items to active cart"""
        payload = {
            "operation": "AddItemToCart",
            "session_id": session.session_id,
            "item_id": item_id,
            "quantity": quantity
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def remove_item_from_cart(self, session: BuyerSession, item_id: int, quantity: int):
        """Function to send TCP request to remove items from cart"""
        payload = {
            "operation": "RemoveItemFromCart",
            "session_id": session.session_id,
            "item_id": item_id,
            "quantity": quantity
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def save_cart(self, session: BuyerSession):
        """Function to send TCP request to save buyer's shopping cart"""
        payload = {
            "operation": "SaveCart",
            "session_id": session.session_id,
            "buyer_id": session.buyer_id
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def clear_cart(self, session: BuyerSession):
        """Function to send TCP request to clear buyer's active shopping cart"""
        payload = {
            "operation": "SaveCart",
            "session_id": session.session_id,
            "buyer_id": session.buyer_id
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def display_cart(self, session: BuyerSession):
        """Function to send TCP request to display buyer's active shopping cart"""
        payload = {
            "operation": "DisplayCart",
            "session_id": session.session_id,
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def make_purchase(self):
        # To be implemented in future
        pass

    def provide_feedback(self, session: BuyerSession, item_id: int, feedback: int):
        """Function to send TCP request to provide feedback (a thumbs up or thumbs down) for an item"""
        payload = {
            "operation": "ProvideFeedback",
            "session_id": session.session_id,
            "item_id": item_id,
            "feedback": feedback    
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def get_seller_rating(self, session: BuyerSession, seller_id: int):
        """Function to send TCP request to get the feedback for a seller"""
        payload = {
            "operation": "GetSellerRating",
            "session_id": session.session_id,
            "seller_id": seller_id
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def get_buyer_purchases(self):
        pass
