# fivesim_api.py
import requests
import time
import logging

# ============ CONFIGURATION ============
FIVESIM_API_KEY = "YOUR_FIVESIM_API_KEY"  # Replace with your key
USD_TO_NPR = 133.0

HEADERS = {
    "Authorization": f"Bearer {FIVESIM_API_KEY}",
    "Accept": "application/json"
}

# Cache for services
_services_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 minutes

# ============ API REQUEST FUNCTION ============

def api_request(url, timeout=20, retries=2):
    """Make API request with retries."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            else:
                logging.warning(f"API error {resp.status_code}, attempt {attempt+1}")
        except Exception as e:
            logging.warning(f"Request failed: {e}, attempt {attempt+1}")
        time.sleep(1)
    return None

# ============ SERVICES ============

def get_all_services():
    """Fetch all activation services from 5sim."""
    # Check cache first
    now = time.time()
    if _services_cache["data"] and (now - _services_cache["timestamp"]) < CACHE_TTL:
        return _services_cache["data"]
    
    url = "https://5sim.net/v1/guest/products/any/any"
    data = api_request(url, timeout=15)
    
    if not data:
        return []
    
    services = [s for s, info in data.items() if info.get("Category") == "activation"]
    services.sort()
    
    # Update cache
    _services_cache["data"] = services
    _services_cache["timestamp"] = now
    
    return services

def get_countries_for_service(service):
    """Fetch countries with stock for a service."""
    url = f"https://5sim.net/v1/guest/prices?product={service}"
    data = api_request(url, timeout=10)
    
    if not data:
        return []
    
    countries_data = data.get(service, {})
    result = []
    
    for country, operators in countries_data.items():
        if not operators:
            continue
        
        # Find cheapest operator with stock
        min_usd = None
        for op_info in operators.values():
            if op_info.get("count", 0) > 0 and "cost" in op_info:
                cost = op_info["cost"]
                if min_usd is None or cost < min_usd:
                    min_usd = cost
        
        if min_usd is not None:
            result.append({
                "country": country,
                "price_usd": min_usd,
                "price_npr": min_usd * USD_TO_NPR
            })
    
    return sorted(result, key=lambda x: x["price_usd"])

# ============ PURCHASE ============

def buy_number(country, service):
    """Buy a virtual number from 5sim."""
    url = f"https://5sim.net/v1/user/buy/activation/{country}/any/{service}"
    return api_request(url, timeout=20, retries=1)

def check_order(order_id):
    """Check if SMS arrived for an order."""
    url = f"https://5sim.net/v1/user/check/{order_id}"
    return api_request(url, timeout=10, retries=2)

def finish_order(order_id):
    """Mark order as completed."""
    url = f"https://5sim.net/v1/user/finish/{order_id}"
    try:
        requests.get(url, headers=HEADERS, timeout=10)
    except:
        pass

def cancel_order(order_id):
    """Cancel order (refund if no SMS)."""
    url = f"https://5sim.net/v1/user/cancel/{order_id}"
    try:
        requests.get(url, headers=HEADERS, timeout=10)
    except:
        pass

def get_balance_usd():
    """Get your 5sim account balance."""
    url = "https://5sim.net/v1/user/profile"
    data = api_request(url)
    return data.get("balance") if data else None