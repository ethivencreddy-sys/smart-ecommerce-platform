from django.contrib import admin
from .models import Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        'product',
        'quantity',
        'price',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'total_amount',
        'status',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'status',
        'created_at',
    )

    search_fields = (
        'user__username',
        'user__email',
    )

    readonly_fields = (
        'user',
        'total_amount',
        'created_at',
        'updated_at',
    )

    inlines = [OrderItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'amount',
        'status',
        'stripe_payment_intent_id',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'status',
        'created_at',
    )

    search_fields = (
        'order__user__username',
        'stripe_payment_intent_id',
    )

    readonly_fields = (
        'order',
        'amount',
        'stripe_payment_intent_id',
        'created_at',
        'updated_at',
    )