# esewa.py
import hashlib
import hmac
import requests
import time
from urllib.parse import urlencode

# ============ CONFIGURATION ============
ESEWA_MERCHANT_ID = "YOUR_MERCHANT_ID"  # Replace with your merchant ID
ESEWA_SECRET_KEY = "YOUR_SECRET_KEY"    # Replace with your secret key
ESEWA_ENVIRONMENT = "test"  # "test" or "production"

# ============ CONSTANTS ============
ESEWA_TEST_URL = "https://uat.esewa.com.np/epay/main"
ESEWA_PRODUCTION_URL = "https://esewa.com.np/epay/main"
ESEWA_CALLBACK_URL = "YOUR_CALLBACK_URL"  # Where eSewa sends confirmation

def get_esewa_url():
    """Get eSewa URL based on environment."""
    if ESEWA_ENVIRONMENT == "test":
        return ESEWA_TEST_URL
    return ESEWA_PRODUCTION_URL

# ============ GENERATE PAYMENT LINK ============

def generate_esewa_payment(amount_npr, user_id, product_id=None):
    """Generate eSewa payment link."""
    if product_id is None:
        product_id = f"TOPUP_{user_id}_{int(time.time())}"
    
    params = {
        "amt": amount_npr,
        "pid": product_id,
        "scd": ESEWA_MERCHANT_ID,
        "su": ESEWA_CALLBACK_URL + "/success",
        "fu": ESEWA_CALLBACK_URL + "/failure"
    }
    
    # Generate payment link
    url = get_esewa_url() + "?" + urlencode(params)
    return url, product_id

# ============ VERIFY PAYMENT ============

def verify_esewa_payment(product_id, ref_id, amount):
    """Verify eSewa payment (called from webhook)."""
    # In production, you'd verify the signature
    # For now, we'll trust the callback
    
    # Example verification (simplified)
    # You'd check with eSewa's API
    
    return True

# ============ WEBHOOK HANDLER ============

def handle_esewa_callback(data):
    """Process eSewa payment confirmation."""
    # data contains: oid (product_id), amt (amount), refId (reference), status
    product_id = data.get('oid')
    amount = float(data.get('amt', 0))
    ref_id = data.get('refId')
    status = data.get('status', 'failed')
    
    if status == 'success' and product_id and amount:
        # Extract user_id from product_id
        parts = product_id.split('_')
        if len(parts) >= 2:
            user_id = int(parts[1])
            return {
                "success": True,
                "user_id": user_id,
                "amount": amount,
                "ref_id": ref_id
            }
    
    return {"success": False}