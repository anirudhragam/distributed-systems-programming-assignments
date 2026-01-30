"""
Performance testing harness for measuring response time and throughput.

This script creates concurrent seller and buyer clients and measures:
1. Average response time: time from request to response for each API call
2. Average throughput: number of API calls completed per second

Usage:
    python performance_test.py --num-sellers 1 --num-buyers 1 --runs 10
"""

import sys
import time
import threading
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import argparse
import os

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'seller_client'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'buyer_client'))
sys.path.insert(0, os.path.dirname(__file__))

from services.buyer_client.api_client import BuyerAPIClient
from services.seller_client.api_client import SellerAPIClient
from services.buyer_client.session import BuyerSession
from services.seller_client.session import SellerSession


@dataclass
class PerformanceMetrics:
    """Container for performance metrics"""
    response_times: List[float]  # Individual response times in seconds
    throughput: float  # Operations per second
    avg_response_time: float  # Average response time in milliseconds
    min_response_time: float
    max_response_time: float
    
    def to_dict(self):
        return {
            'avg_response_time_ms': self.avg_response_time,
            'min_response_time_ms': self.min_response_time,
            'max_response_time_ms': self.max_response_time,
            'throughput_ops_per_sec': self.throughput,
            'num_operations': len(self.response_times)
        }


class PerformanceTester:
    """Harness for running performance tests with multiple concurrent clients"""
    
    def __init__(self, seller_host: str = "localhost", seller_port: int = 5001,
                 buyer_host: str = "localhost", buyer_port: int = 6001):
        self.seller_host = seller_host
        self.seller_port = seller_port
        self.buyer_host = buyer_host
        self.buyer_port = buyer_port
        self.all_response_times = []
        self.lock = threading.Lock()
    
    def run_seller_workload(self, seller_id: int, operations_per_client: int = 1000) -> List[float]:
        """
        Run a seller workload: create account, login, register items, update prices.
        Returns list of response times in milliseconds.
        """
        response_times = []
        try:
            client = SellerAPIClient(self.seller_host, self.seller_port)
            
            # Create unique credentials
            username = f"seller_{seller_id}_{int(time.time() * 1000)}"
            password = "password123"
            
            # 1. Create Account
            start = time.time()
            response = client.create_account(username, password)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
            if not response.get('success'):
                print(f"Seller {seller_id}: Failed to create account")
                return response_times
            
            # 2. Login
            start = time.time()
            response = client.login(username, password)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
            if not response.get('success'):
                print(f"Seller {seller_id}: Failed to login")
                return response_times
            
            session = SellerSession()
            session.seller_id = response.get('seller_id')
            session.session_id = response.get('session_id')
            
            # Register items and update prices
            # Perform these operations until approcimately 1000 operations are done
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


            
            # 4. Logout
            start = time.time()
            response = client.logout(session)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
        except Exception as e:
            print(f"Seller {seller_id} error: {e}")
        
        return response_times
    
    def run_buyer_workload(self, buyer_id: int, operations_per_client: int = 1000) -> List[float]:
        """
        Run a buyer workload: create account, login, search items, add to cart, provide feedback.
        Returns list of response times in milliseconds.
        """
        response_times = []
        try:
            client = BuyerAPIClient(self.buyer_host, self.buyer_port)
            
            # Create unique credentials
            username = f"buyer_{buyer_id}_{int(time.time() * 1000)}"
            password = "password123"
            
            # 1. Create Account
            start = time.time()
            response = client.create_account(username, password)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
            if not response.get('success'):
                print(f"Buyer {buyer_id}: Failed to create account")
                return response_times
            
            # 2. Login
            start = time.time()
            response = client.login(username, password)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
            if not response.get('success'):
                print(f"Buyer {buyer_id}: Failed to login")
                return response_times
            
            session = BuyerSession()
            session.buyer_id = response.get('buyer_id')
            session.session_id = response.get('session_id')
            
            # 3. Search items, add to cart (bulk of operations)
            for i in range((operations_per_client - 2) // 3):
                # Search items
                start = time.time()
                response = client.search_items(session, category=i % 5, keywords=["keyword1"])
                elapsed = (time.time() - start) * 1000
                response_times.append(elapsed)
                
                # Get item (if results exist)
                if response.get('success') and response.get('items'):
                    item_id = response['items'][0]['item_id']
                    
                    start = time.time()
                    response = client.get_item(session, item_id)
                    elapsed = (time.time() - start) * 1000
                    response_times.append(elapsed)
                    
                    # Add to cart
                    start = time.time()
                    response = client.add_item_to_cart(session, item_id, quantity=1)
                    elapsed = (time.time() - start) * 1000
                    response_times.append(elapsed)
            
            # 4. Logout
            start = time.time()
            response = client.logout(session)
            elapsed = (time.time() - start) * 1000
            response_times.append(elapsed)
            
        except Exception as e:
            print(f"Buyer {buyer_id} error: {e}")
        
        return response_times
    
    def run_scenario(self, num_sellers: int, num_buyers: int, 
                    operations_per_client: int = 1000) -> Tuple[PerformanceMetrics, PerformanceMetrics]:
        """
        Run a performance scenario with given number of sellers and buyers.
        Returns (seller_metrics, buyer_metrics)
        """
        all_seller_times = []
        all_buyer_times = []
        
        with ThreadPoolExecutor(max_workers=num_sellers + num_buyers) as executor:
            # Submit all seller tasks
            seller_futures = {
                executor.submit(self.run_seller_workload, i, operations_per_client): i 
                for i in range(num_sellers)
            }
            
            # Submit all buyer tasks
            buyer_futures = {
                executor.submit(self.run_buyer_workload, i, operations_per_client): i 
                for i in range(num_buyers)
            }
            
            # Collect results
            for future in as_completed(seller_futures):
                try:
                    times = future.result()
                    all_seller_times.extend(times)
                except Exception as e:
                    print(f"Seller task failed: {e}")
            
            for future in as_completed(buyer_futures):
                try:
                    times = future.result()
                    all_buyer_times.extend(times)
                except Exception as e:
                    print(f"Buyer task failed: {e}")
        
        # Calculate metrics
        seller_metrics = self._calculate_metrics(all_seller_times, num_sellers, operations_per_client)
        buyer_metrics = self._calculate_metrics(all_buyer_times, num_buyers, operations_per_client)
        
        return seller_metrics, buyer_metrics
    
    def _calculate_metrics(self, response_times: List[float], num_clients: int, 
                          ops_per_client: int) -> PerformanceMetrics:
        """Calculate performance metrics from response times"""
        if not response_times:
            return PerformanceMetrics([], 0, 0, 0, 0)
        
        total_time = sum(response_times) / 1000  # Convert back to seconds
        num_ops = len(response_times)
        throughput = num_ops / total_time if total_time > 0 else 0
        
        return PerformanceMetrics(
            response_times=response_times,
            throughput=throughput,
            avg_response_time=statistics.mean(response_times),
            min_response_time=min(response_times),
            max_response_time=max(response_times)
        )


def run_all_scenarios(runs: int = 10):
    """Run all three scenarios with specified runs"""
    scenarios = [
        (1, 1, "Scenario 1: 1 Seller + 1 Buyer"),
        (10, 10, "Scenario 2: 10 Sellers + 10 Buyers"),
        (100, 100, "Scenario 3: 100 Sellers + 100 Buyers")
    ]
    
    results = {}
    
    for num_sellers, num_buyers, scenario_name in scenarios:
        print(f"\n{'='*60}")
        print(f"{scenario_name}")
        print(f"{'='*60}")
        print(f"Running {runs} runs...\n")
        
        seller_metrics_list = []
        buyer_metrics_list = []
        
        tester = PerformanceTester()
        
        for run in range(runs):
            print(f"Run {run + 1}/{runs}...", end=" ", flush=True)
            start_time = time.time()
            
            seller_metrics, buyer_metrics = tester.run_scenario(num_sellers, num_buyers)
            
            seller_metrics_list.append(seller_metrics)
            buyer_metrics_list.append(buyer_metrics)
            
            elapsed = time.time() - start_time
            print(f"Completed in {elapsed:.2f}s")
        
        # Aggregate metrics across all runs
        results[scenario_name] = {
            'sellers': aggregate_metrics(seller_metrics_list),
            'buyers': aggregate_metrics(buyer_metrics_list)
        }
    
    # Print summary
    print_results_summary(results)
    return results


def aggregate_metrics(metrics_list: List[PerformanceMetrics]) -> Dict:
    """Aggregate metrics across multiple runs"""
    all_response_times = []
    throughputs = []
    
    for m in metrics_list:
        all_response_times.extend(m.response_times)
        throughputs.append(m.throughput)
    
    return {
        'avg_response_time_ms': statistics.mean(all_response_times),
        'min_response_time_ms': min(all_response_times),
        'max_response_time_ms': max(all_response_times),
        'avg_throughput_ops_per_sec': statistics.mean(throughputs),
        'total_operations': len(all_response_times)
    }


def print_results_summary(results: Dict):
    """Print a summary of all results"""
    print(f"\n\n{'='*80}")
    print("PERFORMANCE EVALUATION RESULTS")
    print(f"{'='*80}\n")
    
    for scenario, metrics in results.items():
        print(f"\n{scenario}")
        print("-" * 60)
        
        print("\nSellers:")
        seller_m = metrics['sellers']
        print(f"  Average Response Time:  {seller_m['avg_response_time_ms']:.2f} ms")
        print(f"  Min Response Time:      {seller_m['min_response_time_ms']:.2f} ms")
        print(f"  Max Response Time:      {seller_m['max_response_time_ms']:.2f} ms")
        print(f"  Average Throughput:     {seller_m['avg_throughput_ops_per_sec']:.2f} ops/sec")
        print(f"  Total Operations:       {seller_m['total_operations']}")
        
        print("\nBuyers:")
        buyer_m = metrics['buyers']
        print(f"  Average Response Time:  {buyer_m['avg_response_time_ms']:.2f} ms")
        print(f"  Min Response Time:      {buyer_m['min_response_time_ms']:.2f} ms")
        print(f"  Max Response Time:      {buyer_m['max_response_time_ms']:.2f} ms")
        print(f"  Average Throughput:     {buyer_m['avg_throughput_ops_per_sec']:.2f} ops/sec")
        print(f"  Total Operations:       {buyer_m['total_operations']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Performance testing harness')
    parser.add_argument('--num-sellers', type=int, default=None, help='Number of sellers')
    parser.add_argument('--num-buyers', type=int, default=None, help='Number of buyers')
    parser.add_argument('--runs', type=int, default=10, help='Number of runs')
    parser.add_argument('--seller-host', type=str, default='localhost', help='Seller server host')
    parser.add_argument('--seller-port', type=int, default=5001, help='Seller server port')
    parser.add_argument('--buyer-host', type=str, default='localhost', help='Buyer server host')
    parser.add_argument('--buyer-port', type=int, default=6001, help='Buyer server port')
    
    args = parser.parse_args()
    
    if args.num_sellers is not None and args.num_buyers is not None:
        # Run single scenario
        tester = PerformanceTester(args.seller_host, args.seller_port, 
                                   args.buyer_host, args.buyer_port)
        seller_m, buyer_m = tester.run_scenario(args.num_sellers, args.num_buyers)
        print(f"\nSellers: {seller_m.to_dict()}")
        print(f"Buyers: {buyer_m.to_dict()}")
    else:
        # Run all scenarios
        run_all_scenarios(args.runs)