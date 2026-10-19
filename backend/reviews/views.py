import json
import hmac
import hashlib
import logging
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config

logger = logging.getLogger(__name__)

# Retrieve the webhook secret from your .env file
GITHUB_WEBHOOK_SECRET = config('GITHUB_WEBHOOK_SECRET', default='')

def verify_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256."""
    if not signature_header:
        return False
    
    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

@csrf_exempt
def github_webhook(request):
    if request.method == "POST":
        # Get the signature from the headers
        signature_header = request.headers.get("X-Hub-Signature-256")
        
        # Verify the payload signature
        if not verify_signature(request.body, GITHUB_WEBHOOK_SECRET, signature_header):
            return HttpResponseForbidden("Invalid signature!")
            
        try:
            payload = json.loads(request.body)
            event_type = request.headers.get("X-GitHub-Event")
            
            # Here you can process different events
            if event_type == "pull_request":
                action = payload.get("action")
                logger.info(f"Received pull_request event. Action: {action}")
                # TODO: Trigger the AI review process here!
                
            elif event_type == "ping":
                logger.info("Received ping event from GitHub App installation.")
                
            return JsonResponse({"status": "success", "message": f"Processed {event_type} event"})
            
        except json.JSONDecodeError:
            return HttpResponse(status=400, content="Invalid JSON payload")
            
    return HttpResponse(status=405, content="Method Not Allowed")
