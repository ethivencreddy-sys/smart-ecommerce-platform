from fastapi import APIRouter, HTTPException

from payment_api.database import django
from products.models import Product


router = APIRouter()


@router.get("/")
def get_products(
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: str | None = None,
):
    products = Product.objects.all()

    # Filter by category
    if category:
        products = products.filter(category__iexact=category)

    # Filter by minimum price
    if min_price is not None:
        products = products.filter(price__gte=min_price)

    # Filter by maximum price
    if max_price is not None:
        products = products.filter(price__lte=max_price)

    # Sort products
    if sort == "popularity":
        products = products.order_by("-popularity")
    elif sort == "price_low":
        products = products.order_by("price")
    elif sort == "price_high":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    return [
        {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": str(product.price),
            "stock": product.stock,
            "category": product.category,
            "popularity": product.popularity,
            "image": product.image.url if product.image else None,
            "created_at": product.created_at,
        }
        for product in products
    ]


@router.get("/{product_id}")
def get_product(product_id: int):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": str(product.price),
        "stock": product.stock,
        "category": product.category,
        "popularity": product.popularity,
        "image": product.image.url if product.image else None,
        "created_at": product.created_at,
    }