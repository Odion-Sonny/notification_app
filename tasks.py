from celery import Celery

# Initialize Celery
celery_app = Celery(
    'notification_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def send_notification(message):
    print(f"📢 Notification: {message}")
    # Here you'd typically integrate with Twilio, email, etc.
    return f"Sent: {message}"
