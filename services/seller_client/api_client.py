# API client for communicating with backend server using REST
from typing import Dict, Any, Optional
import requests
import os

try:
    from .session import SellerSession  # For package imports (performance_tests.py)
except ImportError:
    from session import SellerSession  # For direct execution (Docker)


class SellerAPIClient:
    """Client for making REST API calls to the seller backend server"""

    def __init__(self, server_host: str = "seller_server", server_port: int = 5000):
        addrs = os.getenv("SERVER_ADDRS", f"{server_host}:{server_port}")
        self.servers = [(h, int(p)) for h,p in
                        (a.split(":") for a in addrs.split(","))]
        self.base_url = f"http://{server_host}:{server_port}/api"
        self.session_token = None

        self.idx = 0
        self.set_url()

        # Setting request timeout to be 15 minutes
        self.session = requests.Session()
        self.session.timeout = 900.0


    def set_url(self):
        h, p = self.servers[self.idx]
        self.base_url = f"http://{h}:{p}/api"

    def call(self, method, path, **kwargs):
        kwargs.setdefault("headers", self.get_headers())
        for _ in range(len(self.servers)):
            try:
                return getattr(self.session, method)(self.base_url + path, **kwargs)
            # Try other replicas on ConnectionErrors
            except requests.ConnectionError:
                self.idx = (self.idx + 1) % len(self.servers)
                self.set_url()
        raise RuntimeError("All seller servers unreachable")

    def get_headers(self):
        """Get headers including authorization if session token exists"""
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers

    def create_account(self, username: str, password: str):
        """Function to send REST request to the seller server to create a new seller account."""
        try:
            response = self.call("post", "/sellers/accounts",
                                 json={"username": username, "password": password},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating account: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def login(self, username: str, password: str):
        """Function to send REST request to the seller server to login an existing seller and start a session."""
        try:
            response = self.call("post", "/sellers/sessions",
                                 json={"username": username, "password": password},
                                 timeout=self.session.timeout)
            data = response.json()

            # Store session token if login successful
            if data.get("status") == "OK":
                self.session_token = data.get("session_id")

            return data
        except requests.exceptions.RequestException as e:
            print(f"Error logging in: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def logout(self, session: SellerSession):
        """Function to send REST request to the seller server to logout an existing seller."""
        try:
            response = self.call("delete", "/sellers/sessions",
                                 timeout=self.session.timeout)
            data = response.json()

            # Clear session token on successful logout
            if data.get("status") == "OK":
                self.session_token = None

            return data
        except requests.exceptions.RequestException as e:
            print(f"Error logging out: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def get_seller_rating(self, session: SellerSession):
        """Function to get the seller rating for seller ID associated with current session"""
        try:
            response = self.call("get", "/sellers/rating",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting seller rating: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def register_item_for_sale(self, session: SellerSession, item_data: dict):
        """
        Function to accept item details and send REST request to register item for sale.
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
        try:
            payload = {
                "item_name": item_data["item_name"],
                "category": item_data["category"],
                "keywords": item_data["keywords"],
                "condition": item_data["condition"],
                "sale_price": item_data["sale_price"],
                "quantity": item_data["quantity"]
            }

            response = self.call("post", "/sellers/items",
                                 json=payload,
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error registering item for sale: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def change_item_price(self, session: SellerSession, item_id: int, new_price: float):
        """
        Function to send REST request to update price of an item.
        """
        try:
            response = self.call("patch", f"/sellers/items/{item_id}/price",
                                 json={"new_price": new_price},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error changing item price: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def update_units_for_sale(self, session: SellerSession, item_id: int, quantity_change: int):
        """
       Function to send REST request to update quantity of an item.
        """
        try:
            response = self.call("patch", f"/sellers/items/{item_id}/quantity",
                                 json={"quantity_change": quantity_change},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error updating item quantity: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def display_items_for_sale(self, session: SellerSession):
        """
       Function to send REST request to retrieve all items for sale by the seller.
        """
        try:
            response = self.call("get", "/sellers/items",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error displaying items for sale: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}
