from fastapi import FastAPI
from payment_api.routes.cart_routes import router as cart_router
from payment_api.routes.auth import router as auth_router
from payment_api.routes.product_routes import router as product_router
from payment_api.routes.order_routes import router as order_router

app = FastAPI(
    title="Smart E-Commerce Platform API",
    description="FastAPI backend for the Smart E-Commerce Platform",
    version="1.0.0"
)


app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)

app.include_router(
    product_router,
    prefix="/api/products",
    tags=["Products"]
)

app.include_router(
    cart_router,
    prefix="/api/cart",
    tags=["Cart"]
)

app.include_router(
    order_router,
    prefix="/api/orders",
    tags=["Orders"]
)

@app.get("/")
def home():
    return {
        "message": "Smart E-Commerce Platform FastAPI is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }