from rest_framework import serializers
from .models import Cart


class CartSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source='product.name',
        read_only=True
    )

    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )

        if self.instance and value > self.instance.product.stock:
            raise serializers.ValidationError(
                "Requested quantity exceeds available stock."
            )

        return value

    class Meta:
        model = Cart
        fields = [
            'id',
            'product',
            'product_name',
            'product_price',
            'quantity',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'product',
            'product_name',
            'product_price',
            'created_at',
            'updated_at',
        ]