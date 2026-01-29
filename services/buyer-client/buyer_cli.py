"""
Buyer’s interface
●
CreateAccount: Sets up username and password for a new buyer. The server
should return the registered buyer ID associated with this buyer.
●
Login: Buyer provides username and password, begins an active session.
○
As with sellers, buyers must first be logged in in order to interact with the
server. After logging in, all following actions are associated with the buyer
of the active session.
●
Logout: Ends the active buyer session.
●
SearchItemsForSale: Given an item category and up to five keywords, return
available items (and their attributes) for sale.
●
GetItem: Given an item ID, return attributes of the item.
●
AddItemToCart: Given item ID and quantity, add items to the shopping cart (if
available).
●
RemoveItemFromCart: Given item ID and quantity, remove items from shopping
cart (if available).
●
SaveCart: Save the shopping cart to persist across a buyer’s different active
sessions. Otherwise, the shopping cart is cleared when the buyer logs out.
●
ClearCart: Clears the buyer’s shopping cart.
●
DisplayCart: Shows the item IDs and quantities in the buyer’s active shopping
cart.
●
MakePurchase: Perform a purchase.
○
Note: this API does not need to be implemented in this assignment.
●
ProvideFeedback: Given an item ID, provide a thumbs up or thumbs down for the
item.
●
GetSellerRating: Given a seller ID, return the feedback for the seller.
●
GetBuyerPurchases: Get a history of item IDs purchased by the buyer of the
active session.
"""

import os
from api_client import BuyerAPIClient
from session import BuyerSession


class BuyerCLI:
    """Interactive CLI for buyers"""

    def __init__(self, server_host: str = "buyer-server", server_port: int = 6000):
        self.api_client = BuyerAPIClient(server_host, server_port)
        self.session = BuyerSession()
  
    def display_authentication_menu(self):
        """Display main menu for logged-out users"""
        print("\n" + "="*50)
        print("BUYER - E-Commerce System")
        print("="*50)
        print("1. Create Account")
        print("2. Login")
        print("3. Exit")
        print("="*50)
    
    def display_main_menu(self):
        """Display menu for logged-in buyers"""
        print("\n" + "="*50)
        print("="*50)
        print("1. Search Items for Sale")
        print("2. Get Item")
        print("3. Add Item to Cart")
        print("4. Remove Item from Cart")
        print("5. Save Cart")
        print("6. Clear Cart")
        print("7. Display Cart")
        print("8. Make Purchase")
        print("9. Provide Feedback")
        print("10. Get Seller Rating")
        print("11. Get Buyer Purchases")
        print("12. Logout")
        print("="*50)
 
    def handle_create_account(self):
        """Handle account creation"""
        print("\n--- Create Account ---")
        username = input("Enter username: ").strip()
        if not username:
            print("Error: Username cannot be empty")
            return
        
        password = input("Enter password: ").strip()
        if not password:
            print("Error: Password cannot be empty")
            return
        
        response = self.api_client.create_account(username, password)
        
        if response.get("status") == "OK":
            print(f"Your Buyer ID: {response.get('buyer_id')}")
        else:
            print(f"Error: {response.get('message', 'Unknown error')}")
    
    def handle_login(self):
        """Handle buyer login"""
        print("\n--- Login ---")
        username = input("Enter username: ").strip()
        if not username:
            print("Error: Username cannot be empty")
            return
        
        password = input("Enter password: ").strip()
        if not password:
            print("Error: Password cannot be empty")
            return
        
        response = self.api_client.login(username, password)
        
        if response.get("status") == "OK":
            self.session.session_id = response.get("session_id")
            self.session.buyer_id = response.get("buyer_id")
            print(f"{response.get('message')}")
        else:
            print(f"Error: {response.get('message', 'Login failed')}")
    
    def handle_logout(self):
        """Handle buyer logout"""
        response = self.api_client.logout(self.session)
        
        if response.get("status") == "OK":
            print(f"{response.get('message')}")
            self.session.clear()
        else:
            print(f"Error: {response.get('message', 'Logout failed')}")
    
    def handle_search_items(self):
        """Handle search items for sale"""

        # Given an item category and up to five keywords, return
# available items (and their attributes) for sale.
        print("\n--- Search Items for Sale ---")
        category = input("Enter item category: ").strip()
        keywords = input("Enter up to five keywords (comma-separated): ").strip().split(",")
        pass

    def handle_get_item(self):
        """Handle get item by id"""
        try:
            item_id = int(input("Item ID: ").strip())
            response = self.api_client.get_item(self.session, item_id)

            if response.get('status') == 'Timeout':
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()

            elif response.get('status') == 'Error':
                if response.get('message') == 'Item not found.':
                    print(f"Error: Item with ID {item_id} not found.")
                else:
                    print(f"Error: {response.get('message', 'Unknown error')}")

            elif response.get('status') == 'OK':
                item = response.get('item')
                print("\n--- Item Details ---")
                print(f"Item ID: {item['item_id']}")
                print(f"  Name: {item['item_name']}")
                print(f"  Seller ID: {item['seller_id']}")
                print(f"  Category: {item['category']}")
                print(f"  Keywords: {', '.join(item['keywords'])}")
                print(f"  Condition: {item['condition']}")
                print(f"  Price: ${item['sale_price']}")
                print(f"  Quantity: {item['quantity']}")
                print(f"  Thumbs Up: {item['thumbs_up']}")
                print(f"  Thumbs Down: {item['thumbs_down']}")
                print()

        except ValueError as e:
            print(f"Error: Invalid input : {str(e)}")


    def handle_add_item_to_cart(self):
        """Handle add item to cart"""
        pass

    def handle_remove_item_from_cart(self):
        """Handle remove item from cart"""
        pass

    def handle_save_cart(self):
        """Handle save cart"""
        pass

    def handle_clear_cart(self):
        """Handle clear cart"""
        pass

    def handle_display_cart(self):
        """Handle display cart"""
        pass

    def handle_make_purchase(self):
        """To be implemented in future. Handle make purchase"""
        pass

    def handle_provide_feedback(self):
        """Handle provide feedback for item"""
        try:
            item_id = int(input("Item ID: ").strip())
            feedback = input("Feedback (1 for thumbs up, 0 for thumbs down): ").strip()
            if feedback not in ["0", "1"]:
                print("Error: Invalid feedback. Please enter 1 for thumbs up or 0 for thumbs down.")
                return
            
            response = self.api_client.provide_feedback(self.session, item_id, int(feedback))

            if response.get("status") == "Timeout":
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()

            elif response.get("status") == "OK":
                print(f"Feedback submitted successfully for item {item_id}")
                
            else:
                print(f"Error: {response.get('message', 'Failed to submit feedback')}")

        except ValueError:
            print("Error: Invalid input.")

    def handle_get_seller_rating(self):
        """Handle get seller rating"""
        try:
            seller_id = int(input("Seller ID: ").strip())
            response = self.api_client.get_seller_rating(self.session, seller_id)

            if response.get("status") == "Timeout":
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()

            if response.get("status") == "OK":
                print(f"Rating for seller {seller_id}: Thumbs Up: {response.get('thumbs_up')}, Thumbs Down: {response.get('thumbs_down')}")
                
            else:
                print(f"Error: {response.get('message', 'Failed to retrieve seller rating')}")
        except ValueError:
            print("Error: Invalid seller ID.")

    def handle_get_buyer_purchases(self):
        """Handle get buyer purchase history"""
        pass

    def run(self):
        """Main CLI loop"""
        print("\nBuyer Client initialised successfully!")
        print(f"API Server: {self.api_client.server_host}:{self.api_client.server_port}")

        while True:
            try:
                if not self.session.is_active():
                    self.display_authentication_menu()
                    choice = input("Select an option: ").strip()

                    if choice == "1":
                        self.handle_create_account()
                    elif choice == "2":
                        self.handle_login()
                    elif choice == "3":
                        print("\nGoodbye!")
                        break
                    else:
                        print("Invalid option. Please try again.")
                else:
                    self.display_main_menu()
                    choice = input("Select an option: ").strip()

                    if choice == "1":
                        self.handle_search_items()
                    elif choice == "2":
                        self.handle_get_item()
                    elif choice == "3":
                        self.handle_add_item_to_cart()
                    elif choice == "4":
                        self.handle_remove_item_from_cart()
                    elif choice == "5":
                        self.handle_save_cart()
                    elif choice == "6":
                        self.handle_clear_cart()
                    elif choice == "7":
                        self.handle_display_cart()
                    elif choice == "8":
                        self.handle_make_purchase()
                    elif choice == "9":
                        self.handle_provide_feedback()
                    elif choice == "10":
                        self.handle_get_seller_rating()
                    elif choice == "11":
                        self.handle_get_buyer_purchases()
                    elif choice == "12":
                        self.handle_logout()
                    else:
                        print("Invalid option. Please try again.")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
    

def main():
    """Entry point for buyer CLI"""
    server_host = os.getenv("SERVER_HOST", "buyer-server")
    server_port = int(os.getenv("SERVER_PORT", "6000"))

    cli = BuyerCLI(server_host, server_port)
    cli.run()

if __name__ == "__main__":
    main()