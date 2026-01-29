#!/usr/bin/env python3
"""
Seller-side CLI Client for the Distributed E-commerce System
Provides interactive menu for sellers to manage their inventory
"""

import sys
import os
from typing import Optional
from api_client import SellerAPIClient
from session import SellerSession

class SellerCLI:
    """Interactive CLI for sellers"""
    
    def __init__(self, server_host: str = "seller-server", server_port: int = 5000):
        self.api_client = SellerAPIClient(server_host, server_port)
        self.session = SellerSession()
    
    def display_authentication_menu(self):
        """Display main menu for logged-out users"""
        print("\n" + "="*50)
        print("SELLER - E-Commerce System")
        print("="*50)
        print("1. Create Account")
        print("2. Login")
        print("3. Exit")
        print("="*50)
    
    def display_main_menu(self):
        """Display menu for logged-in sellers"""
        print("\n" + "="*50)
        # print(f"Welcome {self.session.seller_name} (ID: {self.session.seller_id})")
        print("="*50)
        print("1. View My Rating")
        print("2. Register Item for Sale")
        print("3. Change Item Price")
        print("4. Update Units for Sale")
        print("5. Display My Items for Sale")
        print("6. Logout")
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
            print(f"Your Seller ID: {response.get('seller_id')}")
        else:
            print(f"Error: {response.get('message', 'Unknown error')}")
    
    def handle_login(self):
        """Handle seller login"""
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
            self.session.seller_id = response.get("seller_id")
            print(f"{response.get('message')}")
        else:
            print(f"Error: {response.get('message', 'Login failed')}")
    
    def handle_logout(self):
        """Handle seller logout"""
        response = self.api_client.logout(self.session)
        
        if response.get("status") == "OK":
            print(f"{response.get('message')}")
            self.session.clear()
        else:
            print(f"Error: {response.get('message', 'Logout failed')}")
    
    def handle_get_rating(self):
        """Handle get seller rating"""
        response = self.api_client.get_seller_rating(self.session)
        
        if response.get("status") == "OK":
            print("\n--- Your Rating ---")
            print(f"Thumbs Up: {response.get('thumbs_up')}")
            print(f"Thumbs Down: {response.get('thumbs_down')}")
        elif response.get("status") == "Timeout":
            print(f"Error: {response.get('message', 'Session timed out')}")
            self.session.clear()
        else:
            print(f"Error: {response.get('message', 'Could not fetch rating')}")
    
    def handle_register_item(self):
        """Handle item registration"""
        print("\n--- Register Item for Sale ---")
        
        try:
            item_name = input("Item name (max 32 chars): ").strip()
            if not item_name or len(item_name) > 32:
                print("Error: Invalid item name")
                return
            
            category = int(input("Category (integer): ").strip())
            
            keywords_input = input("Keywords (comma-separated, max 5): ").strip()
            keywords = [k.strip()[:8] for k in keywords_input.split(",") if k.strip()]
            if len(keywords) > 5:
                print("Error: Maximum 5 keywords allowed")
                return
            
            condition = input("Condition (New/Used): ").strip()
            if condition not in ["New", "Used"]:
                print("Error: Condition must be 'New' or 'Used'")
                return
            
            sale_price = float(input("Sale price: ").strip())
            quantity = int(input("Quantity available: ").strip())
            
            item_data = {
                "item_name": item_name,
                "category": category,
                "keywords": keywords,
                "condition": condition,
                "sale_price": sale_price,
                "quantity": quantity
            }
            
            response = self.api_client.register_item_for_sale(self.session, item_data)
            
            if response.get("status") == "OK":
                print(f"{response.get('message')}")
            elif response.get("status") == "Timeout":
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()
            else:
                print(f"Error: {response.get('message', 'Could not register item')}")
        
        except ValueError as e:
            print(f"Error: Invalid input - {str(e)}")
    
    def handle_change_price(self):
        """Handle price change"""
        print("\n--- Change Item Price ---")
        
        try:
            item_id = int(input("Item ID: ").strip())
            new_price = float(input("New price: ").strip())
            
            response = self.api_client.change_item_price(self.session, item_id, new_price)
            
            if response.get("status") == "OK":
                print(f"{response.get('message')}")
            elif response.get("status") == "Timeout":
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()
            else:
                print(f"Error: {response.get('message', 'Could not update price')}")
        
        except ValueError as e:
            print(f"Error: Invalid input : {str(e)}")
    
    def handle_update_units(self):
        """Handle units update"""
        print("\n--- Update Units for Sale ---")
        
        try:
            item_id = int(input("Item ID: ").strip())
            quantity_change = int(input("Quantity Change: ").strip())
            
            response = self.api_client.update_units_for_sale(self.session, item_id, quantity_change)
            
            if response.get("status") == "OK":
                print(f"{response.get('message')}")
            elif response.get("status") == "Timeout":
                print(f"Error: {response.get('message', 'Session timed out')}")
                self.session.clear()
            else:
                print(f"Error: {response.get('message', 'Could not update units')}")
        
        except ValueError as e:
            print(f"Error: Invalid input - {str(e)}")
    
    def handle_display_items(self):
        """Handle display items"""
        response = self.api_client.display_items_for_sale(self.session)
        
        if response.get("status") == "OK":
            
            items = response.get("items", [])
            
            if not items and response.get("status") == "OK":
                print(f"{response.get('message')}")
                return
            
            print("\n--- Your Items for Sale ---")
            for i, item in enumerate(items, start=1):
                print(f"{i}. Item ID: {item['item_id']}")
                print(f"  Name: {item['item_name']}")
                print(f"  Category: {item['category']}")
                print(f"  Keywords: {', '.join(item['keywords'])}")
                print(f"  Condition: {item['condition']}")
                print(f"  Price: ${item['sale_price']}")
                print(f"  Quantity: {item['quantity']}")
                print(f"  Thumbs Up: {item['thumbs_up']}")
                print(f"  Thumbs Down: {item['thumbs_down']}")
                print()
        elif response.get("status") == "Timeout":
            print(f"Error: {response.get('message', 'Session timed out')}")
            self.session.clear()
        else:
            print(f"Error: {response.get('message', 'Could not fetch items')}")
    
    def run(self):
        """Main CLI loop"""
        print("\nSeller Client initialized successfully!")
        print(f"API Server: {self.api_client.server_host}:{self.api_client.server_port}")
        
        while True:
            try:
                if not self.session.session_id:
                    self.display_authentication_menu()
                    choice = input("Enter your choice: ").strip()
                    
                    if choice == "1":
                        self.handle_create_account()
                    elif choice == "2":
                        self.handle_login()
                    elif choice == "3":
                        print("\nGoodbye!")
                        break
                    else:
                        print("Invalid choice. Please try again.")
                
                else:
                    self.display_main_menu()
                    choice = input("Enter your choice: ").strip()
                    
                    if choice == "1":
                        self.handle_get_rating()
                    elif choice == "2":
                        self.handle_register_item()
                    elif choice == "3":
                        self.handle_change_price()
                    elif choice == "4":
                        self.handle_update_units()
                    elif choice == "5":
                        self.handle_display_items()
                    elif choice == "6":
                        self.handle_logout()
                    else:
                        print("Invalid choice. Please try again.")
            
            except KeyboardInterrupt:
                print("\n\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")

def main():
    """Entry point"""
    server_host = os.getenv("SERVER_HOST", "seller-server")
    server_port = int(os.getenv("SERVER_PORT", "5000"))
    
    cli = SellerCLI(server_host, server_port)
    cli.run()

if __name__ == "__main__":
    main()