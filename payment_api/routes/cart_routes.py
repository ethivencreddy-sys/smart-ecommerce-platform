from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from payment_api.database import django
from payment_api.dependencies import get_current_user

from cart.models import Cart
from products.models import Product


router = APIRouter()


class AddToCartRequest(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


@router.post("/add")
def add_to_cart(
    data: AddToCartRequest,
    current_user=Depends(get_current_user)
):
    try:
        product = Product.objects.get(id=data.product_id)
    except Product.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    if data.quantity > product.stock:
        raise HTTPException(
            status_code=400,
            detail=f"Only {product.stock} items available in stock"
        )

    cart_item, created = Cart.objects.get_or_create(
        user=current_user,
        product=product,
        defaults={"quantity": data.quantity}
    )

    if not created:
        new_quantity = cart_item.quantity + data.quantity

        if new_quantity > product.stock:
            raise HTTPException(
                status_code=400,
                detail=f"Only {product.stock} items available in stock"
            )

        cart_item.quantity = new_quantity
        cart_item.save()

    return {
        "message": "Product added to cart successfully",
        "cart_item_id": cart_item.id,
        "product_id": product.id,
        "product_name": product.name,
        "quantity": cart_item.quantity
    }

@router.get("/")
def get_cart(current_user=Depends(get_current_user)):
    cart_items = Cart.objects.filter(
        user=current_user
    ).select_related("product")

    total_amount = 0
    items = []

    for item in cart_items:
        item_total = item.quantity * item.product.price
        total_amount += item_total

        items.append({
            "cart_item_id": item.id,
            "product_id": item.product.id,
            "product_name": item.product.name,
            "price": str(item.product.price),
            "quantity": item.quantity,
            "item_total": str(item_total),
        })

    return {
        "items": items,
        "total_amount": str(total_amount),
    }
class UpdateCartRequest(BaseModel):
    quantity: int = Field(ge=1)


@router.put("/{cart_item_id}")
def update_cart(
    cart_item_id: int,
    data: UpdateCartRequest,
    current_user=Depends(get_current_user)
):
    try:
        cart_item = Cart.objects.select_related("product").get(
            id=cart_item_id,
            user=current_user
        )
    except Cart.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found"
        )

    if data.quantity > cart_item.product.stock:
        raise HTTPException(
            status_code=400,
            detail=f"Only {cart_item.product.stock} items available in stock"
        )

    cart_item.quantity = data.quantity
    cart_item.save()

    return {
        "message": "Cart updated successfully",
        "cart_item_id": cart_item.id,
        "product_id": cart_item.product.id,
        "product_name": cart_item.product.name,
        "quantity": cart_item.quantity
    }
@router.delete("/{cart_item_id}")
def remove_from_cart(
    cart_item_id: int,
    current_user=Depends(get_current_user)
):
    try:
        cart_item = Cart.objects.get(
            id=cart_item_id,
            user=current_user
        )
    except Cart.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found"
        )

    cart_item.delete()

    return {
        "message": "Product removed from cart successfully"
    }