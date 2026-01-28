# API client for communicating with backend server
from typing import Dict, Any, Optional
import socket
from utils.socket_utils import send_message, recv_message
from session import SellerSession

class SellerAPIClient:
    """Client for making API calls to the seller backend server"""
    
    def __init__(self, server_host: str = "seller-server", server_port: int = 5000):
        self.server_host = server_host
        self.server_port = server_port
        self.connection = None
        # TODO: Implement TCP socket connection
        # implement some mechanism to close idle tcp connections (easy way: timeout)
        # Creating a TCP socket connection with the Seller server. Setting connection timeout to 15 minutes
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
        """Function to send TCP requests to the seller server, to create a new seller account."""
        # If server connection is not established or if server terminated the connection, reconnect
        payload = {
            "operation": "CreateAccount",
            "username": username,
            "password": password
        }
        response = self.send_message_with_reconnect(payload)
        return response
    
    def login(self, username: str, password: str):
        """Function to send TCP requests to the seller server, to login an existing seller and start a session."""
        payload = {
            "operation": "Login",
            "username": username,
            "password": password
        }
        response = self.send_message_with_reconnect(payload)
        return response

    def logout(self, session: SellerSession):
        """Function to send TCP requests to the seller server, to logout an existing seller."""
        payload = {
            "operation": "Logout",
            "session_id": session.session_id,
        }
        response = self.send_message_with_reconnect(payload)
        return response
    
    def get_seller_rating(self, session: SellerSession):
        """Function to get the seller rating for seller ID associated with current session"""
        payload = {
            "operation": "GetSellerRating",
            "session_id": session.session_id,
            "seller_id": session.seller_id
        }
        response = self.send_message_with_reconnect(payload)
        return response
        
    
    def register_item_for_sale(self, session: SellerSession, item_data: dict):
        """
        Function to accept item details and send TCP request to register item for sale.
        Args:
            session: Current seller session
            item_data: Dictionary containing:
                - item_name (str): Name of the item
                - category (int): Item category
                - keywords (list): Up to 5 keywords
                - condition (str): "New" or "Used"
                - sale_price (float): Price of the item
                - quantity (int): Number of units available
                
        """
        # Validate item_data?

        payload = {
            "operation": "RegisterItemForSale",
            "session_id": session.session_id,
            "seller_id": session.seller_id,
            "item_name": item_data["item_name"],
            "category": item_data["category"],
            "keywords": item_data["keywords"],  # Check this
            "condition": item_data["condition"],
            "sale_price": item_data["sale_price"],
            "quantity": item_data["quantity"]
        } 
        response = self.send_message_with_reconnect(payload)
        return response

    def change_item_price(self, session: SellerSession, item_id: int, new_price: float):
        """
        Function to send TCP request to update price of an item.
        """
        payload = {
            "operation": "ChangeItemPrice",
            "session_id": session.session_id,
            "seller_id": session.seller_id,
            "item_id": item_id,
            "new_price": new_price
        }
        response = self.send_message_with_reconnect(payload)
        return response     
        
    def update_units_for_sale(self, session: SellerSession, item_id: int, quantity_change: int):
        """
       Function to send TCP request to update quantity of an item.
        """
        payload = {
            "operation": "UpdateUnitsForSale",
            "session_id": session.session_id,
            "seller_id": session.seller_id,
            "item_id": item_id,
            "quantity_change": quantity_change
        }
        response = self.send_message_with_reconnect(payload)
        return response     
    
    def display_items_for_sale(self, session: SellerSession):
        """
       Function to send TCP request to retrieve all items for sale by the seller.
        """
        payload = {
            "operation": "DisplayItemsForSale",
            "session_id": session.session_id,
            "seller_id": session.seller_id
        }
        response = self.send_message_with_reconnect(payload)
        return response