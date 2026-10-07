from .views import (
    AnalyticsDashboardPageView,
    analytics_dashboard_page,
    sales_csv_report,
    sales_pdf_report,
)
from django.urls import path
from .views import (
    OrderListView,
    OrderDetailView,
    CheckoutView,
    CreatePaymentIntentView,
    StripeWebhookView,
    AnalyticsDashboardView,
    AdminOrderStatusUpdateView,
    
)

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment/create-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('payment/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('analytics/', AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    path(
        'admin/<int:pk>/status/',
        AdminOrderStatusUpdateView.as_view(),
        name='admin-order-status-update'
    ),
    path(
        "analytics/dashboard/",
        AnalyticsDashboardPageView.as_view(),
        name="analytics-dashboard"
    ),
    path(
        "analytics/dashboard-page/",
         analytics_dashboard_page,
         name="analytics-dashboard-page",
    ),
    path(
         "reports/sales.csv",
         sales_csv_report,
         name="sales-csv-report",
    ),
    path(
         "reports/sales.pdf",
         sales_pdf_report,
         name="sales-pdf-report",
),
]