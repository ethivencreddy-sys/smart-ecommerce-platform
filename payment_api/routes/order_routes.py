import os
import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

from fastapi import APIRouter, Depends, HTTPException
from django.contrib.auth.models import User

from payment_api.database import django
from payment_api.dependencies import get_current_user

from cart.models import Cart
from orders.models import Order, OrderItem, Payment
from products.models import Product

from notifications.models import Notification
from notifications.utils import send_realtime_notification
from notifications.email_service import send_order_email


router = APIRouter()


# ---------------------------------------------------------
# CHECKOUT
# ---------------------------------------------------------

@router.post("/checkout")
def checkout(
    current_user: User = Depends(get_current_user)
):
    cart_items = Cart.objects.filter(user=current_user).select_related("product")

    if not cart_items.exists():
        raise HTTPException(
            status_code=400,
            detail="Cart is empty"
        )

    total_amount = 0

    for item in cart_items:
        if item.quantity > item.product.stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {item.product.name}"
            )

        total_amount += item.product.price * item.quantity

    # Create order
    order = Order.objects.create(
        user=current_user,
        total_amount=total_amount,
        status="pending"
    )

    # Create order items and reduce stock
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price
        )

        item.product.stock -= item.quantity
        item.product.save()

    # Create payment record
    Payment.objects.create(
        order=order,
        amount=total_amount,
        status="pending"
    )

    # Clear cart
    cart_items.delete()

    # Create in-app notification
    notification = Notification.objects.create(
        user=current_user,
        title=f"Order #{order.id} placed",
        message=(
            f"Your order #{order.id} has been placed successfully. "
            f"Order amount: ₹{order.total_amount}"
        ),
        notification_type="order"
    )

    # Send realtime WebSocket notification
    try:
        send_realtime_notification(notification)
    except Exception:
        pass

    # Send order confirmation email
    try:
        send_order_email(current_user, order)
    except Exception:
        pass

    return {
        "message": "Order placed successfully",
        "order_id": order.id,
        "total_amount": str(order.total_amount),
        "status": order.status
    }


# ---------------------------------------------------------
# GET ALL ORDERS
# ---------------------------------------------------------

@router.get("/")
def get_orders(
    current_user: User = Depends(get_current_user)
):
    orders = (
        Order.objects
        .filter(user=current_user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    return [
        {
            "id": order.id,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "created_at": order.created_at,
            "items": [
                {
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                }
                for item in order.items.all()
            ],
        }
        for order in orders
    ]


# ---------------------------------------------------------
# GET SINGLE ORDER
# ---------------------------------------------------------

@router.get("/{order_id}")
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user)
):
    try:
        order = (
            Order.objects
            .filter(
                id=order_id,
                user=current_user
            )
            .prefetch_related("items__product")
            .get()
        )
    except Order.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    return {
        "id": order.id,
        "total_amount": str(order.total_amount),
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "price": str(item.price),
            }
            for item in order.items.all()
        ],
    }


# ---------------------------------------------------------
# CREATE STRIPE PAYMENT INTENT
# ---------------------------------------------------------

@router.post("/{order_id}/payment-intent")
def create_payment_intent(
    order_id: int,
    current_user: User = Depends(get_current_user)
):
    try:
        order = Order.objects.get(
            id=order_id,
            user=current_user
        )
    except Order.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    try:
        payment = Payment.objects.get(order=order)
    except Payment.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found"
        )

    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=int(order.total_amount * 100),
            currency="inr",
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never"
            },
            metadata={
                "order_id": str(order.id)
            }
        )

        payment.stripe_payment_intent_id = payment_intent.id
        payment.save()

        return {
            "message": "Payment intent created successfully",
            "payment_intent_id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "amount": str(order.total_amount),
            "currency": "inr"
        }

    except stripe.error.StripeError as e:
        print("STRIPE ERROR:", e)
        raise HTTPException(
        status_code=400,
        detail=str(e)
    )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Payment service error"
        )