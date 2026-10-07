from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_realtime_notification(notification):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"user_{notification.user.id}",
        {
            "type": "send_notification",
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type,
        },
    )