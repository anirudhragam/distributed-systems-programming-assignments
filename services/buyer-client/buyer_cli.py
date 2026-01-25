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

def handle_create_account():
    # called when user selects the create account option from cli menu

    # asks for user registration details

    # sends requestr to buyer api client

    # api client opens tcp connection to buyer server and sends create account request

    # buyer server runs SQL to insert buyer in the customer db

    # buyer server sends OK response to buyer api client

    # buyer api client sends OK to client interface 

    # client cli shows OK message to buyer
    pass

def handle_login():
    # called when user selects the login option from the cli menu

    # asks for user login details

    # sends to api client

    # api client opens tcp connection to buyer server and sends login request

    # buyer server validates the credentials first, and only if valid, 
    # inserts session timestamp in customer db

    # buyer server returns session details to buyer client

    # buyer client stores active session details locally for this user

    # buyer client interface shows success message to buyer on CLI
    pass

def handle_logout():
    # called when user selects the logout option on the cli menu

    # cli sends session id to api client
    
    # api client opens tcp connection to server, passing session id
    
    # server deletes session id from sessions table 
    pass

def handle_search_items():
    pass

def get_item():
    # called when user selects get item option on the cli menu

    # cli sends item id to api client

    # api client opens a tcp connection passing item id to server

    # server queries product db for item id

    # server returns results to api client

    # api client returns results to cli

    # cli displays results
    pass

def add_item_to_cart():
    




# cli with menu options/arg options

# Example:
# option chosen - create account
# calls create account function