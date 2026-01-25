# Stub API client for communicating with backend server
from typing import Dict, Any, Optional

class SellerAPIClient:
    """Client for making API calls to the seller backend server"""
    
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.host = host
        self.port = port
        # TODO: Implement TCP socket connection
        # implement some mechanism to close idle tcp connections (easy way: timeout)

    
    def create_account(self, username: str, password: str) -> Dict[str, Any]:
        """
        CreateAccount: Sets up username and password for a new seller.
        Server returns the registered seller ID.
        
        Args:
            username: Seller username
            password: Seller password
            
        Returns:
            Response with seller_id or error message
        """
        print(f"[STUB] CreateAccount called with username={username}")
        return {
            "status": "success",
            "seller_id": 1,
            "message": "Account created successfully"
        }
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Login: Seller provides username and password, begins an active session.
        
        Args:
            username: Seller username
            password: Seller password
            
        Returns:
            Response with session_id and seller details
        """
        print(f"[STUB] Login called with username={username}")

        # server will select * username, passwd verify
        # if exists, start a session - insert into, session table
        # if doesn't exist then handle error 

        return {
            "status": "success",
            "session_id": "sess_12345abcde",
            "seller_id": 1,
            "seller_name": username,
            "message": "Login successful"
        }
    
    def logout(self, session_id: str) -> Dict[str, Any]:
        """
        Logout: Ends active seller session.
        
        Args:
            session_id: Current session ID
            
        Returns:
            Response confirming logout
        """
        print(f"[STUB] Logout called with session_id={session_id}")
        return {
            "status": "success",
            "message": "Logout successful"
        }
    
    def get_seller_rating(self, session_id: str) -> Dict[str, Any]:
        """
        GetSellerRating: Returns the feedback for the seller of this session.
        
        Args:
            session_id: Current session ID
            
        Returns:
            Response with thumbs_up and thumbs_down counts
        """
        print(f"[STUB] GetSellerRating called with session_id={session_id}")
        return {
            "status": "success",
            "thumbs_up": 15,
            "thumbs_down": 2,
            "rating": "4.5/5"
        }
    
    def register_item_for_sale(self, session_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        RegisterItemForSale: Register items for sale with item attributes and quantity.
        Server returns the assigned item ID.
        
        Args:
            session_id: Current session ID
            item_data: Dictionary containing:
                - item_name (str): Name of the item
                - category (int): Item category
                - keywords (list): Up to 5 keywords
                - condition (str): "New" or "Used"
                - sale_price (float): Price of the item
                - quantity (int): Number of units available
                
        Returns:
            Response with item_id
        """
        print(f"[STUB] RegisterItemForSale called with session_id={session_id}, item_data={item_data}")
        return {
            "status": "success",
            "item_id": 101,
            "message": "Item registered for sale successfully"
        }
    
    def change_item_price(self, session_id: str, item_id: int, new_price: float) -> Dict[str, Any]:
        """
        ChangeItemPrice: Update item with new sale price.
        
        Args:
            session_id: Current session ID
            item_id: ID of the item to update
            new_price: New sale price
            
        Returns:
            Response confirming price update
        """
        print(f"[STUB] ChangeItemPrice called with session_id={session_id}, item_id={item_id}, new_price={new_price}")
        return {
            "status": "success",
            "item_id": item_id,
            "new_price": new_price,
            "message": "Price updated successfully"
        }
    
    def update_units_for_sale(self, session_id: str, item_id: int, quantity_change: int) -> Dict[str, Any]:
        """
        UpdateUnitsForSale: Given Item ID, remove a quantity of items for sale.
        
        Args:
            session_id: Current session ID
            item_id: ID of the item to update
            quantity_change: Number of units to remove (negative) or add (positive)
            
        Returns:
            Response with updated quantity
        """
        print(f"[STUB] UpdateUnitsForSale called with session_id={session_id}, item_id={item_id}, quantity_change={quantity_change}")
        return {
            "status": "success",
            "item_id": item_id,
            "remaining_quantity": 45,
            "message": "Units updated successfully"
        }
    
    def display_items_for_sale(self, session_id: str) -> Dict[str, Any]:
        """
        DisplayItemsForSale: Display all items currently on sale by the seller.
        
        Args:
            session_id: Current session ID
            
        Returns:
            Response with list of items
        """
        print(f"[STUB] DisplayItemsForSale called with session_id={session_id}")
        return {
            "status": "success",
            "items": [
                {
                    "item_id": 101,
                    "item_name": "Laptop Computer",
                    "category": 1,
                    "condition": "New",
                    "sale_price": 999.99,
                    "quantity": 50
                },
                {
                    "item_id": 102,
                    "item_name": "Wireless Mouse",
                    "category": 2,
                    "condition": "New",
                    "sale_price": 29.99,
                    "quantity": 200
                }
            ],
            "total_items": 2
        }