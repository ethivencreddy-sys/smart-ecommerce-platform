from django.contrib import admin
from .models import Cart


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'product',
        'quantity',
        'created_at',
        'updated_at',
    )

    list_filter = (
        'created_at',
        'updated_at',
    )

    search_fields = (
        'user__username',
        'product__name',
    )