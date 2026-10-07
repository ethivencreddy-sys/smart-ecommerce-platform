from django.core.mail import send_mail
from django.conf import settings


def send_order_email(user, order):
    subject = f"Order #{order.id} placed successfully"

    message = (
        f"Hello {user.username},\n\n"
        f"Your order #{order.id} has been placed successfully.\n"
        f"Order amount: ₹{order.total_amount}\n"
        f"Order status: {order.status}\n\n"
        f"Thank you for shopping with us!"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_payment_success_email(user, order):
    subject = f"Payment successful for Order #{order.id}"

    message = (
        f"Hello {user.username},\n\n"
        f"Your payment for order #{order.id} was successful.\n"
        f"Amount paid: ₹{order.total_amount}\n\n"
        f"Thank you for your purchase!"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )