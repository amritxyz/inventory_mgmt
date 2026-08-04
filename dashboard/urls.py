from django.urls import path
from .views import (
    IndexView,
    PermanentDelete,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductRestoreView,
    ProductUpdateView,
    ProductVariantDeleteView,
    ProductVariantListView,
    ProductVariantCreateView,
    ProductVariantUpdateView,
    RestoreItemView,
    StockTransactionUpdateView,
    StockTransactionDeleteView,
    StockTransactionListView,
    StockTransactionCreateView,
    TrashListView,
    UserListView,
    ApproveUserView,
    ToggleUserStatusView,
    DeleteUserView,
    ProductDetailView,
    ProductVariantDetailView,
    StockTransactionDetailView
)

app_name = "dashboard"

urlpatterns = [
    path("", IndexView.as_view(), name="index"),

    # Products
    path("products/", ProductListView.as_view(), name="product_list"),
    path("products/add", ProductCreateView.as_view(), name="product_create"),
    path("products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product_update"),
    path("products/<int:pk>/delete", ProductDeleteView.as_view(), name="product_delete"),
    path("products/<int:pk>/restore", ProductRestoreView.as_view(), name="product_restore"),
    path( "products/<int:pk>/detail/", ProductDetailView.as_view(), name="product_detail",),

    # Variants
    path("variants/", ProductVariantListView.as_view(), name="variant_list"),
    path("variants/add/", ProductVariantCreateView.as_view(), name="variant_create"),
    path("variants/<int:pk>/edit/", ProductVariantUpdateView.as_view(), name="variant_update"),
    path("variants/<int:pk>/delete/", ProductVariantDeleteView.as_view(), name="variant_delete"),
    path( "variants/<int:pk>/detail/", ProductVariantDetailView.as_view(), name="variant_detail",),

    # Transactions
    path("transactions/", StockTransactionListView.as_view(), name="transaction_list"),
    path("transactions/add/", StockTransactionCreateView.as_view(), name="transaction_create"),
    path("transactions/<int:pk>/edit", StockTransactionUpdateView.as_view(), name="transaction_update"),
    path("transactions/<int:pk>/delete", StockTransactionDeleteView.as_view(), name="transaction_delete"),
    path( "transactions/<int:pk>/detail/", StockTransactionDetailView.as_view(), name="transaction_detail",),

    # Trash
    path("trash/", TrashListView.as_view(), name="trash"),
    path("trash/restore/<str:item_type>/<int:pk>/", RestoreItemView.as_view(), name="restore_item"),
    path("trash/permanent-delete/<str:item_type>/<int:pk>/", PermanentDelete.as_view(), name="permanent_delete"),

    # User Approvals / Management (Admin only)
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/<int:pk>/approve/", ApproveUserView.as_view(), name="user_approve"),
    path("users/<int:pk>/toggle/", ToggleUserStatusView.as_view(), name="user_toggle"),
    path("users/<int:pk>/delete/", DeleteUserView.as_view(), name="user_delete"),
]
