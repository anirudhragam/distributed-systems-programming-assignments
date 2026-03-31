# API client for communicating with buyer server using REST

import os

import requests

try:
    from .session import BuyerSession
except ImportError:
    from session import BuyerSession


class BuyerAPIClient:
    """Client for making REST API calls to the buyer backend server"""

    def __init__(self, server_idx: int = 0, server_host: str = "buyer-server-0", server_port: int = 6000):
        addrs = os.getenv("BUYER_SERVERS", f"{server_host}:{server_port}")
        self.servers = [(h, int(p)) for h, p in
                        (a.split(":") for a in addrs.split(","))]
        print(f'Buyer {server_host} servers: {self.servers}')
        self.idx = server_idx
        self.set_url()
        self.session_token = None

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
            except requests.ConnectionError:
                self.idx = (self.idx + 1) % len(self.servers)
                self.set_url()
        raise RuntimeError("All buyer servers unreachable")

    def get_headers(self):
        """Get headers including authorization if session token exists"""
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers

    def create_account(self, username: str, password: str):
        """Function to send REST request to create a new buyer account"""
        try:
            response = self.call("post", "/buyers/accounts",
                                 json={"username": username, "password": password},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating account: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def login(self, username: str, password: str):
        """Function to send REST request to login and start a session"""
        try:
            response = self.call("post", "/buyers/sessions",
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

    def logout(self, session: BuyerSession):
        """Function to send REST request to logout"""
        try:
            response = self.call("delete", "/buyers/sessions",
                                 timeout=self.session.timeout)
            data = response.json()

            # Clear session token on successful logout
            if data.get("status") == "OK":
                self.session_token = None

            return data
        except requests.exceptions.RequestException as e:
            print(f"Error logging out: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def search_items(self, session: BuyerSession, category: int, keywords: list[str]):
        """Function to send REST request to search items"""
        try:
            params = {"category": category}
            if keywords:
                params["keywords"] = keywords

            response = self.call("get", "/buyers/items/search",
                                 params=params,
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error searching items: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def get_item(self, session: BuyerSession, item_id: int):
        """Function to send REST request to get item details"""
        try:
            response = self.call("get", f"/buyers/items/{item_id}",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting item: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def add_item_to_cart(self, session: BuyerSession, item_id: int, quantity: int):
        """Function to send REST request to add items to cart"""
        try:
            response = self.call("post", f"/buyers/cart/items/{item_id}",
                                 json={"quantity": quantity},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error adding item to cart: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def remove_item_from_cart(self, session: BuyerSession, item_id: int, quantity: int):
        """Function to send REST request to remove items from cart"""
        try:
            response = self.call("delete", f"/buyers/cart/items/{item_id}",
                                 json={"quantity": quantity},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error removing item from cart: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def save_cart(self, session: BuyerSession):
        """Function to send REST request to save cart"""
        try:
            response = self.call("post", "/buyers/cart/save",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error saving cart: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def clear_cart(self, session: BuyerSession):
        """Function to send REST request to clear cart"""
        try:
            response = self.call("delete", "/buyers/cart",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error clearing cart: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def display_cart(self, session: BuyerSession):
        """Function to send REST request to display cart"""
        try:
            response = self.call("get", "/buyers/cart",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error displaying cart: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def make_purchase(self, session: BuyerSession, cardholder_name: str, card_number: str, expiry_month: int, expiry_year: int, security_code: str):
        """Function to send REST request to make purchase (stubbed)"""
        try:
            response = self.call("post", "/buyers/purchases",
                                 json={
                                     "cardholder_name": cardholder_name,
                                     "card_number": card_number,
                                     "expiry_month": expiry_month,
                                     "expiry_year": expiry_year,
                                     "security_code": security_code
                                 },
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making purchase: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def provide_feedback(self, session: BuyerSession, item_id: int, feedback: int):
        """Function to send REST request to provide feedback"""
        try:
            response = self.call("post", "/buyers/feedback",
                                 json={"item_id": item_id, "feedback": feedback},
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error providing feedback: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def get_seller_rating(self, session: BuyerSession, seller_id: int):
        """Function to send REST request to get seller rating"""
        try:
            response = self.call("get", f"/buyers/sellers/{seller_id}/rating",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting seller rating: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}

    def get_buyer_purchases(self, session: BuyerSession):
        """Function to send REST request to get buyer purchases (stubbed)"""
        try:
            response = self.call("get", "/buyers/purchases",
                                 timeout=self.session.timeout)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting buyer purchases: {e}")
            return {"status": "Error", "message": f"Connection error: {e}"}
