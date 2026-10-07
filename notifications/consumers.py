import json
from channels.generic.websocket import WebsocketConsumer


class NotificationConsumer(WebsocketConsumer):

    def connect(self):
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            self.room_group_name = f"user_{self.user.id}"

            self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            self.accept()

            self.send(text_data=json.dumps({
                "message": "WebSocket connected successfully",
                "user": self.user.username
            }))
        else:
            self.close()

    def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    def send_notification(self, event):
        self.send(text_data=json.dumps({
            "title": event["title"],
            "message": event["message"],
            "notification_type": event["notification_type"]
        }))