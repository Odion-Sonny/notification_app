import os
import logging
from celery import Celery
from celery.exceptions import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration with environment variables
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)

# Initialize Celery with better configuration
celery_app = Celery(
    'notification_tasks',
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_notification(self, message):
    try:
        logger.info(f"Processing notification task {self.request.id}: {message[:50]}...")
        
        # Input validation
        if not message or not isinstance(message, str):
            raise ValueError("Invalid message format")
        
        if len(message.strip()) == 0:
            raise ValueError("Message cannot be empty")
        
        # Simulate notification sending (replace with actual service integration)
        logger.info(f"📢 Notification sent: {message}")
        
        # Here you'd typically integrate with:
        # - Twilio for SMS
        # - SendGrid/SES for email  
        # - Push notification services
        # - Slack/Discord webhooks
        
        result = {
            "status": "success",
            "message": f"Notification sent successfully",
            "task_id": self.request.id,
            "message_length": len(message)
        }
        
        logger.info(f"Task {self.request.id} completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Task {self.request.id} failed: {str(exc)}")
        
        # Don't retry for validation errors
        if isinstance(exc, ValueError):
            return {
                "status": "failed",
                "error": str(exc),
                "task_id": self.request.id
            }
        
        # Retry for other exceptions
        raise self.retry(exc=exc)
