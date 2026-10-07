from decimal import Decimal

import stripe
import csv
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Sum
from django.shortcuts import render
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from users.permissions import IsAdmin
from cart.models import Cart
from products.models import Product
from orders.models import Order, OrderItem, Payment
from notifications.models import Notification
from notifications.email_service import (
    send_order_email,
    send_payment_success_email,
)
from notifications.utils import send_realtime_notification


stripe.api_key = settings.STRIPE_SECRET_KEY


# =========================
# ORDER LIST
# =========================

class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user)
            .prefetch_related("items__product")
            .order_by("-created_at")
        )

        result = []

        for order in orders:
            result.append({
                "order_id": order.id,
                "total_amount": str(order.total_amount),
                "status": order.status,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "items": [
                    {
                        "product_id": item.product.id,
                        "product_name": item.product.name,
                        "quantity": item.quantity,
                        "price": str(item.price),
                    }
                    for item in order.items.all()
                ],
            })

        return Response(result)


# =========================
# ORDER DETAIL
# =========================

class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = (
                Order.objects
                .prefetch_related("items__product")
                .get(id=pk, user=request.user)
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "order_id": order.id,
            "total_amount": str(order.total_amount),
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": [
                {
                    "product_id": item.product.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": str(item.price),
                }
                for item in order.items.all()
            ],
        })


# =========================
# CHECKOUT
# =========================

class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart_items = (
            Cart.objects
            .filter(user=request.user)
            .select_related("product")
        )

        if not cart_items.exists():
            return Response(
                {"detail": "Cart is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_amount = Decimal("0.00")

        for item in cart_items:
            if item.quantity > item.product.stock:
                return Response(
                    {
                        "detail": (
                            f"Insufficient stock for "
                            f"{item.product.name}"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            total_amount += item.product.price * item.quantity

        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            status="pending"
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )

            item.product.stock -= item.quantity
            item.product.save()

        Payment.objects.create(
            order=order,
            amount=total_amount,
            status="pending"
        )

        cart_items.delete()

        notification = Notification.objects.create(
            user=request.user,
            title=f"Order #{order.id} placed",
            message=(
                f"Your order #{order.id} has been placed successfully."
            ),
            notification_type="order",
        )

        send_realtime_notification(notification)

        send_order_email(request.user, order)

        return Response(
            {
                "message": "Checkout successful",
                "order_id": order.id,
                "total_amount": str(order.total_amount),
                "status": order.status,
                "payment_status": "pending",
            },
            status=status.HTTP_201_CREATED
        )


# =========================
# CREATE STRIPE PAYMENT INTENT
# =========================

class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")

        if not order_id:
            return Response(
                {"detail": "order_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Order.objects.get(
                id=order_id,
                user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if order.payment.status == "paid":
            return Response(
                {"detail": "Order is already paid"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),
                currency="inr",
                metadata={
                    "order_id": str(order.id)
                },
            )

            order.payment.stripe_payment_intent_id = payment_intent.id
            order.payment.save()

            return Response({
                "message": "Payment intent created successfully",
                "order_id": order.id,
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": str(order.total_amount),
                "currency": "inr",
            })

        except Exception:
            return Response(
                {"detail": "Unable to create payment intent"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =========================
# STRIPE WEBHOOK
# =========================

class StripeWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                webhook_secret
            )
        except ValueError:
            return Response(
                {"detail": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except stripe.error.SignatureVerificationError:
            return Response(
                {"detail": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if event["type"] == "payment_intent.succeeded":

            payment_intent = event["data"]["object"]

            order_id = payment_intent["metadata"].get("order_id")

            if order_id:
                try:
                    order = Order.objects.get(id=order_id)

                    payment = order.payment
                    payment.status = "paid"
                    payment.save()

                    order.status = "confirmed"
                    order.save()

                    notification = Notification.objects.create(
                        user=order.user,
                        title=f"Payment successful for Order #{order.id}",
                        message=(
                            f"Payment of ₹{order.total_amount} "
                            f"was successful."
                        ),
                        notification_type="payment",
                    )

                    send_realtime_notification(notification)

                    send_payment_success_email(
                        order.user,
                        order
                    )

                except Order.DoesNotExist:
                    pass

        elif event["type"] == "payment_intent.payment_failed":

            payment_intent = event["data"]["object"]

            order_id = payment_intent["metadata"].get("order_id")

            if order_id:
                try:
                    order = Order.objects.get(id=order_id)

                    payment = order.payment
                    payment.status = "failed"
                    payment.save()

                    notification = Notification.objects.create(
                        user=order.user,
                        title=f"Payment failed for Order #{order.id}",
                        message=(
                            f"Payment for order #{order.id} "
                            f"could not be completed."
                        ),
                        notification_type="payment",
                    )

                    send_realtime_notification(notification)

                except Order.DoesNotExist:
                    pass

        return Response({"status": "success"})


# =========================
# ADMIN ANALYTICS
# =========================

class AnalyticsDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):

        total_orders = Order.objects.count()

        total_revenue = (
            Order.objects.aggregate(
                total=Sum("total_amount")
            )["total"]
            or Decimal("0.00")
        )

        paid_revenue = (
            Payment.objects
            .filter(status="paid")
            .aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        total_products = Product.objects.count()

        top_products = (
            OrderItem.objects
            .values(
                "product__id",
                "product__name"
            )
            .annotate(
                total_sold=Sum("quantity")
            )
            .order_by("-total_sold")[:10]
        )

        low_stock_products = (
            Product.objects
            .filter(stock__lte=5)
            .values(
                "id",
                "name",
                "stock"
            )
        )

        return Response({
            "total_orders": total_orders,
            "total_revenue": str(total_revenue),
            "paid_revenue": str(paid_revenue),
            "total_products": total_products,
            "top_products": list(top_products),
            "low_stock_products": list(low_stock_products),
        })


# =========================
# ADMIN ORDER STATUS UPDATE
# =========================

class AdminOrderStatusSerializer(serializers.Serializer):

    status = serializers.ChoiceField(
        choices=[
            choice[0]
            for choice in Order.STATUS_CHOICES
        ]
    )


class AdminOrderStatusUpdateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminOrderStatusSerializer)
    def patch(self, request, pk):

        try:
            order = Order.objects.get(id=pk)

        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AdminOrderStatusSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        new_status = serializer.validated_data["status"]

        order.status = new_status
        order.save()

        notification = Notification.objects.create(
            user=order.user,
            title=f"Order #{order.id} status updated",
            message=(
                f"Your order status is now {order.status}."
            ),
            notification_type="order",
        )

        send_realtime_notification(notification)

        return Response({
            "message": "Order status updated successfully",
            "order_id": order.id,
            "status": order.status,
        })
class AnalyticsDashboardPageView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        total_orders = Order.objects.count()

        total_revenue = Order.objects.aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")

        paid_revenue = Payment.objects.filter(
            status="paid"
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        total_products = Product.objects.count()

        top_products = (
            OrderItem.objects
            .values("product__name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )

        low_stock_products = Product.objects.filter(
            stock__lte=10
        ).order_by("stock")

        return render(
            request,
            "orders/analytics_dashboard.html",
            {
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "paid_revenue": paid_revenue,
                "total_products": total_products,
                "top_products": top_products,
                "low_stock_products": low_stock_products,
            },
        )    
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
@staff_member_required
def analytics_dashboard_page(request):
    total_orders = Order.objects.count()

    total_revenue = Order.objects.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    paid_revenue = Payment.objects.filter(
        status="paid"
    ).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    total_products = Product.objects.count()

    top_products = (
        OrderItem.objects
        .values("product__name")
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:5]
    )

    low_stock_products = Product.objects.filter(
        stock__lte=10
    ).order_by("stock")

    return render(
        request,
        "orders/analytics_dashboard.html",
        {
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "paid_revenue": paid_revenue,
            "total_products": total_products,
            "top_products": top_products,
            "low_stock_products": low_stock_products,
        },
    )    
@staff_member_required
def sales_csv_report(request):
    response = HttpResponse(
        content_type="text/csv"
    )

    response["Content-Disposition"] = (
        'attachment; filename="sales_report.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "Order ID",
        "Username",
        "Total Amount",
        "Payment Status",
        "Order Status",
        "Created At",
    ])

    orders = (
        Order.objects
        .select_related("user")
        .prefetch_related("payment")
        .order_by("-created_at")
    )

    for order in orders:
        payment_status = (
            order.payment.status
            if hasattr(order, "payment")
            else "N/A"
        )

        writer.writerow([
            order.id,
            order.user.username,
            order.total_amount,
            payment_status,
            order.status,
            order.created_at,
        ])

    return response
@staff_member_required
def sales_pdf_report(request):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.units import mm

    response = HttpResponse(
        content_type="application/pdf"
    )
    response["Content-Disposition"] = (
        'attachment; filename="sales_report.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "Smart E-Commerce Sales Report",
        styles["Title"]
    )
    elements.append(title)

    data = [[
        "Order ID",
        "Username",
        "Amount",
        "Payment",
        "Status",
        "Created At",
    ]]

    orders = (
        Order.objects
        .select_related("user")
        .prefetch_related("payment")
        .order_by("-created_at")
    )

    for order in orders:
        payment_status = (
            order.payment.status
            if hasattr(order, "payment")
            else "N/A"
        )

        data.append([
            str(order.id),
            order.user.username,
            f"₹{order.total_amount}",
            payment_status,
            order.status,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            15 * mm,
            35 * mm,
            25 * mm,
            25 * mm,
            25 * mm,
            45 * mm,
        ],
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ])
    )

    elements.append(table)

    doc.build(elements)

    return response