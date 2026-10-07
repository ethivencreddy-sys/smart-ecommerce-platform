from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import Cart
from .serializers import CartSerializer
from products.models import Product


class CartListCreateView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(
            user=self.request.user
        ).select_related('product')

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        quantity = request.data.get('quantity', 1)

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Quantity must be a valid number.'},
                status=400
            )

        if quantity <= 0:
            return Response(
                {'error': 'Quantity must be greater than zero.'},
                status=400
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found.'},
                status=404
            )

        if product.stock < quantity:
            return Response(
                {'error': 'Not enough stock available.'},
                status=400
            )

        cart_item, created = Cart.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity

            if new_quantity > product.stock:
                return Response(
                    {'error': 'Requested quantity exceeds available stock.'},
                    status=400
                )

            cart_item.quantity = new_quantity
            cart_item.save()

        serializer = self.get_serializer(cart_item)
        return Response(
            serializer.data,
            status=201 if created else 200
        )


class CartDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(
            user=self.request.user
        ).select_related('product')

    def perform_update(self, serializer):
        cart_item = self.get_object()
        quantity = serializer.validated_data.get(
            'quantity',
            cart_item.quantity
        )

        if quantity <= 0:
            raise ValueError('Quantity must be greater than zero.')

        if quantity > cart_item.product.stock:
            raise ValueError('Requested quantity exceeds available stock.')

        serializer.save()