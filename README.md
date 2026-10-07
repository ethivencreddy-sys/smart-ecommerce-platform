# Smart E-Commerce Platform

A backend-only Smart E-Commerce Platform built using Django, Django REST Framework, FastAPI, MySQL, Stripe, Auth0, WebSockets and email notifications.

## Project Architecture

### Django Admin Backend
- User management and roles
- Product management
- Product image uploads
- Order management
- Payment records
- Notifications
- Analytics dashboard
- CSV sales reports
- PDF sales reports

### FastAPI User Backend
- User registration
- User login with JWT
- JWT-protected APIs
- Auth0 authentication
- Google login
- Facebook login
- Product browsing and filtering
- Cart management
- Checkout
- Order history
- Stripe PaymentIntent integration

## Technologies

- Python
- Django
- Django REST Framework
- FastAPI
- MySQL
- SQLAlchemy/Django ORM integration
- Simple JWT
- Auth0
- Stripe
- Django Channels
- WebSockets
- SMTP/Gmail
- Chart.js
- ReportLab
- Postman

## Main Features

### Authentication
- Email/password registration and login
- JWT authentication
- Auth0 integration
- Google authentication
- Facebook authentication

### Products
- Browse products
- Filter by category
- Filter by minimum and maximum price
- Sort by popularity
- Sort by price
- Product image upload

### Cart
- Add product
- View cart
- Update quantity
- Remove product

### Orders
- Checkout
- Order creation
- Order items
- Order history
- Order status management
- Stock reduction

### Payments
- Stripe PaymentIntent
- Payment status tracking
- Stripe webhook handling
- Payment success notifications
- Payment success email

### Notifications
- In-app notifications
- Email notifications
- Real-time WebSocket notifications

### Admin Analytics
- Total orders
- Total revenue
- Paid revenue
- Total products
- Top products chart
- Low-stock products chart

### Reports
- CSV sales report
- PDF sales report
- MySQL database dump

## API Documentation

FastAPI Swagger:

http://127.0.0.1:8001/docs

FastAPI OpenAPI:

http://127.0.0.1:8001/openapi.json

Django Swagger:

http://127.0.0.1:8000/api/docs/

## Admin

Django Admin:

http://127.0.0.1:8000/admin/

Analytics Dashboard:

http://127.0.0.1:8000/api/orders/analytics/dashboard-page/

## Running the Project

### Django

```bash
python manage.py migrate
python manage.py runserver