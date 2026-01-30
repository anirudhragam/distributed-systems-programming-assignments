import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import argparse
from services.buyer_client.api_client import BuyerAPIClient
from services.seller_client.api_client import SellerAPIClient
from services.buyer_client.session import BuyerSession
from services.seller_client.session import SellerSession


BUYER_SERVER = "34.182.100.10"
BUYER_PORT = 6001

SELLER_SERVER = "34.182.100.10"
SELLER_SERVER_PORT = 5001

def run_seller_operations(seller_id: int):
    response_times = []
    try:
        client = SellerAPIClient(SELLER_SERVER, SELLER_SERVER_PORT)

        # Create unique credentials
        username = f"seller_{seller_id}_{int(time.time() * 1000)}"
        password = "password123"

        # Create Account
        start = time.time()
        response = client.create_account(username, password)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)

        if not response.get('status') == 'OK':
            print(f"Seller {seller_id}: Failed to create account")
            return response_times
        
        # Login
        start = time.time()
        response = client.login(username, password)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)
        
        if not response.get('status') == 'OK':
            print(f"Seller {seller_id}: Failed to login")
            return response_times
        
        session = SellerSession()
        session.seller_id = response.get('seller_id')
        session.session_id = response.get('session_id')

        # Register items and update prices
        # Repeat these operations until approximately 1000 operations are done
        for i in range((1000 - 2) // 3): 
            # Register item for sale
            item_data = {
                "item_name": f"Item_{seller_id}_{i}",
                "category": i % 5,
                "keywords": ["keyword1", "keyword2"],
                "condition": "New",
                "sale_price": 10.0 + i,
                "quantity": 10
            }

            start = time.time()
            response = client.register_item_for_sale(session, item_data)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
            if response.get('status') == 'OK':
                item_id = response.get('item_id')
                # Change price
                start = time.time()
                response = client.change_item_price(session, item_id, 15.0 + i)
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)
                
                # Update units
                start = time.time()
                response = client.update_units_for_sale(session, item_id, 5)
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)

        # Logout
        start = time.time()
        response = client.logout(session)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)
    
    except Exception as e:
            print(f"Seller {seller_id} error: {e}")
        
    return response_times


def run_buyer_operations(buyer_id: int):
    response_times = []
    try:
        client = BuyerAPIClient(BUYER_SERVER, BUYER_PORT)

        # Create unique credentials
        username = f"buyer_{buyer_id}_{int(time.time() * 1000)}"
        password = "password123"

        # Create Account
        start = time.time()
        response = client.create_account(username, password)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)

        if not response.get('status') == 'OK':
            print(f"Buyer {buyer_id}: Failed to create account")
            return response_times
        
        # Login
        start = time.time()
        response = client.login(username, password)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)
        
        if not response.get('status') == 'OK':
            print(f"Buyer {buyer_id}: Failed to login")
            return response_times
        
        session = BuyerSession()
        session.buyer_id = response.get('buyer_id')
        session.session_id = response.get('session_id')

        # Search items, get item, add to cart, remove from cart, save cart, display cart, clear cart, provide feedback, get seller rating
        # Repeat these operations until approximately 1000 operations are done
        for i in range((1000 - 2) // 9): 
            # Search items
            start = time.time()
            response = client.search_items(session, category=i % 5, keywords=["keyword1"])
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)

            # Get item
            start = time.time()
            response = client.get_item(session, item_id=i % 5)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)

            if response.get("status") == "OK" and response.get("item"):
                item_id = response.get("item").get("item_id")
                # Provide feedback
                start = time.time()
                # random feedback between thumbs up (1) and thumbs down (0)
                response = client.provide_feedback(session, item_id=item_id, feedback=random.choice([0, 1]))
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)

                # Add item to cart
                start = time.time()
                response = client.add_item_to_cart(session, item_id=item_id, quantity=1)
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)

                # Remove item from cart
                start = time.time()
                response = client.remove_item_from_cart(session, item_id=item_id, quantity=1)
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)

                seller_id = response.get("item").get("seller_id")
                # Get seller rating
                start = time.time()
                response = client.get_seller_rating(session, seller_id=seller_id)
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)

            # Save cart
            start = time.time()
            response = client.save_cart(session)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)

            # Display cart
            start = time.time()
            response = client.display_cart(session)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)

            # Clear cart
            start = time.time()
            response = client.clear_cart(session)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)

        # Logout
        start = time.time()
        response = client.logout(session)
        elapsed = (time.time() - start) * 1000
        response_times.append(elapsed)
    
    except Exception as e:
            print(f"Buyer {buyer_id} error: {e}")
        
    return response_times

def compute_metrics(response_times):
    """Function to compute average response time and throughput"""

    total_response_time = sum(response_times)
    total_response_time_secs = total_response_time / 1000
    total_operations = len(response_times) # Around 1000 * num_clients
    
    average_response_time = total_response_time / total_operations
    throughput = total_operations / total_response_time_secs

    return average_response_time, throughput
   

def run_scenario(num_sellers: int, num_buyers: int):
    seller_response_times = []
    buyer_response_times = []

    with ThreadPoolExecutor(max_workers=num_sellers + num_buyers) as executor:
        # Submit all seller tasks
        seller_futures = { executor.submit(run_seller_operations, i): ("seller", i) for i in range(num_sellers)}
        buyer_futures = { executor.submit(run_buyer_operations, i): ("buyer", i) for i in range(num_buyers) }

        # Concatenate all futures
        all_futures = seller_futures | buyer_futures

        # As each thread completes, collect response times
        for future in as_completed(all_futures):
            client_type, client_id = all_futures[future]
            try:
                response_times = future.result()
                if client_type == "seller":
                    seller_response_times.extend(response_times)
                else:
                    buyer_response_times.extend(response_times)
            except Exception as e:
                print(f"{client_type} {client_id} exception: {e}")

        # Compute metrics from response times
        seller_average_response_time, seller_throughput = compute_metrics(seller_response_times)
        buyer_average_response_time, buyer_throughput = compute_metrics(buyer_response_times)
        
        return (seller_average_response_time, seller_throughput,
                buyer_average_response_time, buyer_throughput)
    
def run_experiments(num_sellers: int, num_buyers: int):
    seller_avg_response_times = []
    seller_throughputs = []
    buyer_avg_response_times = []
    buyer_throughputs = []

    for i in range(10):
        (seller_art, seller_tp,
         buyer_art, buyer_tp) = run_scenario(num_sellers, num_buyers)
        
        seller_avg_response_times.append(seller_art)
        seller_throughputs.append(seller_tp)
        buyer_avg_response_times.append(buyer_art)
        buyer_throughputs.append(buyer_tp)

        print(f"Iteration {i+1}: Sellers - Avg Response Time: {seller_art:.2f} ms, Throughput: {seller_tp:.2f} ops/sec")
        print(f"Iteration {i+1}: Buyers - Avg Response Time: {buyer_art:.2f} ms, Throughput: {buyer_tp:.2f} ops/sec")

    print("\nFinal Results after {} iterations:".format(10))
    print(f"Sellers - Avg Response Time: {sum(seller_avg_response_times)/10:.2f} ms, Throughput: {sum(seller_throughputs)/10:.2f} ops/sec")
    print(f"Buyers - Avg Response Time: {sum(buyer_avg_response_times)/10:.2f} ms, Throughput: {sum(buyer_throughputs)/10:.2f} ops/sec")
           
if __name__ == "__main__":
    # Accept arguments for number of buyers, sellers and buyer/seller host and port from CLI
    parser = argparse.ArgumentParser(description="Run performance tests")
    parser.add_argument('--num-sellers', type=int, default=None, help='Number of sellers')
    parser.add_argument('--num-buyers', type=int, default=None, help='Number of buyers')
    
    args = parser.parse_args()

    num_sellers = args.num_sellers
    num_buyers = args.num_buyers
    

