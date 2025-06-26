from flask import Flask, request, jsonify
from tasks import send_notification

app = Flask(__name__)

@app.route('/notify', methods=['POST'])
def notify():
    data = request.get_json()
    message = data.get('message', 'Hello from Celery!')
    
    # Trigger the async task
    send_notification.delay(message)
    
    return jsonify({"status": "Notification sent!"}), 200

if __name__ == '__main__':
    app.run(debug=True)
