import os
import logging
from functools import wraps
from flask import Flask, request, jsonify
from marshmallow import Schema, fields, ValidationError
from config import config
from tasks import send_notification

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.getenv('FLASK_CONFIG', 'default')
    app.config.from_object(config[config_name])
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    return app

app = create_app()
logger = logging.getLogger(__name__)

# Rate limiting decorator (simple in-memory implementation)
from collections import defaultdict
import time

request_counts = defaultdict(list)

def rate_limit(max_requests=100, per_seconds=3600):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            now = time.time()
            
            # Clean old requests
            request_counts[client_ip] = [req_time for req_time in request_counts[client_ip] 
                                       if now - req_time < per_seconds]
            
            if len(request_counts[client_ip]) >= max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            request_counts[client_ip].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Security headers middleware
@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

# Input validation schema
class NotificationSchema(Schema):
    message = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0 and len(x) <= 1000)
    recipient = fields.Email(missing=None)
    priority = fields.Str(missing='normal', validate=lambda x: x in ['low', 'normal', 'high'])

notification_schema = NotificationSchema()

@app.errorhandler(400)
def bad_request(error):
    logger.warning(f"Bad request: {error}")
    return jsonify({"error": "Bad request", "message": str(error)}), 400

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

@app.route('/notify', methods=['POST'])
@rate_limit(max_requests=50, per_seconds=3600)
def notify():
    try:
        # Validate content type
        if not request.is_json:
            logger.warning("Request without JSON content type")
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        # Get and validate JSON data
        data = request.get_json()
        if data is None:
            logger.warning("Empty or invalid JSON payload")
            return jsonify({"error": "Invalid JSON payload"}), 400
        
        # Validate input schema
        try:
            validated_data = notification_schema.load(data)
        except ValidationError as err:
            logger.warning(f"Validation error: {err.messages}")
            return jsonify({"error": "Validation failed", "details": err.messages}), 400
        
        message = validated_data['message'].strip()
        
        # Trigger the async task
        logger.info(f"Sending notification: {message[:50]}...")
        task = send_notification.delay(message)
        
        return jsonify({
            "status": "Notification queued successfully",
            "task_id": task.id,
            "message_preview": message[:50] + "..." if len(message) > 50 else message
        }), 202
        
    except Exception as e:
        logger.error(f"Unexpected error in notify endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "notification-app"}), 200

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
