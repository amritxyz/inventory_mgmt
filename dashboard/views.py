from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from dashboard.utils.actions import resolve_actions
from django.contrib import messages
from django.db import transaction
from django.db.models import (
    Q, Case, Count, QuerySet, Sum, When, F,
    IntegerField, DecimalField, ExpressionWrapper
)
from django.db.models.functions import Coalesce
from django.http import Http404, request
from django.shortcuts import _get_queryset, render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    DeleteView,
    View,
    TemplateView,
    ListView,
    CreateView,
    UpdateView
)

from .models import Category, StockTransaction, Product, ProductVariant
from .forms import (
    ProductForm,
    ProductVariantForm,
    StockTransactionForm
)

from django.utils.safestring import mark_safe
import html
import json

if not hasattr(User, 'username_display'):
    def _user_username_display(self):
        avatar_letter = html.escape(self.username[0].upper()) if self.username else "U"
        username_clean = html.escape(self.username)
        you_badge = ""
        if getattr(self, "_request_user", None) == self:
            you_badge = ' <span class="badge-user" style="background: #e0e0e0; color: #181818; font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; font-weight: 600;">You</span>'
        return mark_safe(
            f'<div style="display: flex; align-items: center; gap: 10px;">'
            f'<div class="user-avatar" style="width: 32px; height: 32px; font-size: 0.85rem;">{avatar_letter}</div>'
            f'<strong>{username_clean}</strong>{you_badge}'
            f'</div>'
        )
    User.username_display = property(_user_username_display)

if not hasattr(User, 'role_display'):
    def _user_role_display(self):
        if self.is_superuser or self.is_staff:
            return mark_safe('<span class="badge-admin" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase;">Admin</span>')
        return mark_safe('<span class="badge-user" style="font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 500; text-transform: uppercase; background: #e0e0e0; color: #333333;">User</span>')
    User.role_display = property(_user_role_display)

if not hasattr(User, 'status_display'):
    def _user_status_display(self):
        if self.is_active:
            return mark_safe('<span class="badge-active" style="background: #e8e8e8; color: #181818; font-size: 0.75rem; padding: 4px 10px; border-radius: 12px; font-weight: 600;">Active</span>')
        return mark_safe('<span class="badge-pending" style="background: #181818; color: #ffffff; font-size: 0.75rem; padding: 4px 10px; border-radius: 12px; font-weight: 500;">Pending Approval</span>')
    User.status_display = property(_user_status_display)

if not hasattr(User, 'date_joined_display'):
    def _user_date_joined_display(self):
        if self.date_joined:
            return mark_safe(f'<span class="cell-muted">{self.date_joined.strftime("%b %d, %Y %H:%M")}</span>')
        return ""
    User.date_joined_display = property(_user_date_joined_display)

"""
Helper classes / methods
"""

class IndexView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # stat cards
        total_products = Product.objects.count()
        total_variants = ProductVariant.objects.count()
        total_transactions = StockTransaction.objects.count()

        # low stock count
        variants = ProductVariant.objects.annotate(
            stock_balance=Sum(
                Case(
                    When(transactions__transaction_type=StockTransaction.TransactionType.IN, then=F("transactions__quantity")),
                    When(transactions__transaction_type=StockTransaction.TransactionType.OUT, then=-F("transactions__quantity")),
                    output_field=IntegerField(),
                ),
                filter=Q(transactions__is_deleted=False)
            )
        )
        low_stock_count = sum(1 for v in variants if (v.stock_balance or 0) <= v.reorder_level)

        # bar chart: stock by category
        category_data = (
            Category.objects.annotate(
                total_stock=Sum(
                    Case(
                        When(variants__transactions__transaction_type=StockTransaction.TransactionType.IN,
                             then=F("variants__transactions__quantity")),
                        When(variants__transactions__transaction_type=StockTransaction.TransactionType.OUT,
                             then=-F("variants__transactions__quantity")),
                        output_field=IntegerField(),
                    ),
                    filter=Q(variants__transactions__is_deleted=False)
                )
            )
            .filter(total_stock__isnull=False)
            .order_by('-total_stock')[:6]
        )
        category_labels = json.dumps([c.name for c in category_data])
        category_values = json.dumps([c.total_stock or 0 for c in category_data])

        # doughnut chart: quantities by type
        tx_totals = (
            StockTransaction.objects
            .filter(is_deleted=False)
            .values('transaction_type')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('transaction_type')
        )
        tx_labels = json.dumps([t['transaction_type'] for t in tx_totals])
        tx_values = json.dumps([t['total_quantity'] or 0 for t in tx_totals])

        # recent transactions [last 5]
        recent_transactions = StockTransaction.objects.select_related('variant__product').order_by('-transaction_date')[:5]

        # Financial Calculations
        transactions_qs = StockTransaction.objects.filter(is_deleted=False)

        # Cash inflow (Revenue): Sum of (quantity * unit_price - discount) for OUT transactions
        inflow_agg = (
            transactions_qs.filter(transaction_type=StockTransaction.TransactionType.OUT)
            .annotate(
                item_revenue=ExpressionWrapper(
                    F('quantity') * Coalesce(F('unit_price'), 0) - Coalesce(F('discount'), 0),
                    output_field=IntegerField()
                )
            )
            .aggregate(total=Sum('item_revenue'))
        )
        total_inflow = inflow_agg['total'] or 0

        # Cash outflow (Purchases): Sum of (quantity * unit_price) for IN transactions
        outflow_agg = (
            transactions_qs.filter(transaction_type=StockTransaction.TransactionType.IN)
            .annotate(
                item_cost=ExpressionWrapper(
                    F('quantity') * Coalesce(F('unit_price'), 0),
                    output_field=IntegerField()
                )
            )
            .aggregate(total=Sum('item_cost'))
        )
        total_outflow = outflow_agg['total'] or 0

        # Cashflow = Inflow - Outflow
        cashflow = total_inflow - total_outflow

        # Cost of Goods Sold (COGS): Sum of (quantity * cost_price) for OUT transactions
        cogs_agg = (
            transactions_qs.filter(transaction_type=StockTransaction.TransactionType.OUT)
            .annotate(
                item_cogs=ExpressionWrapper(
                    F('quantity') * Coalesce(F('cost_price'), 0),
                    output_field=IntegerField()
                )
            )
            .aggregate(total=Sum('item_cogs'))
        )
        total_cogs = cogs_agg['total'] or 0

        # Profit/Loss = Revenue (Inflow) - COGS
        profit_loss = total_inflow - total_cogs

        context.update({
            "total_products": total_products,
            "total_variants": total_variants,
            "total_transactions": total_transactions,
            "low_stock_count": low_stock_count,
            "category_labels": category_labels,
            "category_values": category_values,
            "tx_labels": tx_labels,
            "tx_values": tx_values,
            "recent_transactions": recent_transactions,
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
            "cashflow": cashflow,
            "profit_loss": profit_loss,
        })
        return context

class Search:
    search_fields = []

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q")

        if query:
            q_object = Q()
            for field in self.search_fields:
                q_object |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(q_object)

        return queryset

class Sort:
    allowed_sort_fields = {}
    default_sort_field = "id"

    def get_queryset(self):
        queryset = super().get_queryset()
        direction = self.request.GET.get("sort", "desc")
        order_key = self.request.GET.get("order")

        # Looks up the key sent from the frontend table
        order_field = self.allowed_sort_fields.get(order_key, self.default_sort_field)
        ordering = f"-{order_field}" if direction == "desc" else order_field

        return queryset.order_by(ordering, "-id")

class Action:
    table = {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []

        req = getattr(self, "request", None)
        req_user = getattr(req, "user", None) if req else None

        for obj in context[self.context_object_name]:
            obj._request_user = req_user
            rows.append({
                "obj": obj,
                "actions": resolve_actions(
                    self.table["model_key"],
                    self.table.get("actions", []),
                    obj,
                    request=req,
                ),
            })

        self.table["colspan"] = (
            1
            + len(self.table["columns"])
            + (1 if self.table.get("actions") else 0)
        )

        context["rows"] = rows
        context["table"] = self.table

        return context

"""
Views classes for dashboard_app
"""
class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def form_valid(self, form):
        messages.success(self.request, "Product created successfully")
        response = super().form_valid(form)
        return redirect(f"{reverse_lazy('dashboard:variant_create')}?product={self.object.pk}")

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def get_queryset(self):
        return Product.all_objects

    def form_valid(self, form):
        messages.success(self.request, "Product updated successfully.")
        return super().form_valid(form)

class ProductDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product.all_objects, pk=pk)
        product.soft_delete()
        messages.success(request, "Product deleted successfully")
        return redirect("dashboard:product_list")

class ProductRestoreView(LoginRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product.all_objects, pk=pk)
        product.restore()
        messages.success(request, "Product restored.")
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer)

class ProductListView(LoginRequiredMixin, Action, Search, Sort, ListView):
    model = Product
    template_name = "dashboard/product_list.html"
    context_object_name = "products"
    paginate_by = 10
    search_fields = ["name"]

    default_sort_field = "name"

    allowed_sort_fields = {
        "name": "name",
        "variant_count": "variant_count",
        "date": "created_at"
    }

    table = {
        "columns": [
            {"key": "name", "label": "Product Name"},
            {"key": "variant_count", "label": "Variants"},
            {"key": "created_at", "label": "Date", "default_hidden": True},
        ],
        "actions": ["edit", "delete"],
        "model_key": "product",
    }

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(variant_count=Count("variants"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_products"] = Product.all_objects.count()
        return context

class ProductVariantListView(LoginRequiredMixin, Action, Search, Sort, ListView):
    model = ProductVariant
    template_name = "dashboard/productvariant_list.html"
    context_object_name = "variants"
    search_fields = ["name", "sku", "product__name", "category__name"]
    paginate_by = 10

    default_sort_field = "name"

    allowed_sort_fields = {
        "product": "product__name",
        "name": "name",
        "category": "category__name",
        "sku": "sku",
        "cost_price": "cost_price",
        "price": "price",
        "stock_balance": "stock_balance",
        "date": "created_at"
    }

    table = {
        "columns": [
            {"key": "product", "label": "Product"},
            {"key": "name", "label": "Variant"},
            {"key": "category", "label": "Category"},
            {"key": "sku", "label": "SKU"},
            {"key": "cost_price", "label": "Cost Price", "default_hidden": True},
            {"key": "price", "label": "Selling Price"},
            {"key": "stock_balance", "label": "Stock"},
            {"key": "created_at", "label": "Date", "default_hidden": True},
        ],
        "actions": ["transact", "edit", "delete"],
        "model_key": "variant",
    }

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("product", "category")
            .annotate(
                stock_balance = Sum(
                    Case(
                        When(
                            transactions__transaction_type=StockTransaction.TransactionType.IN,
                            then=F("transactions__quantity"),
                        ),
                        When(
                            transactions__transaction_type=StockTransaction.TransactionType.OUT,
                            then=-F("transactions__quantity"),
                        ),
                        output_field=IntegerField(),
                    ),
                    filter=Q(transactions__is_deleted=False)
                )
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class ProductVariantCreateView(LoginRequiredMixin, CreateView):
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = "dashboard/productvariant_form.html"
    success_url = reverse_lazy("dashboard:variant_list")

    def get_initial(self):
        initial = super().get_initial()
        product_id = self.request.GET.get('product')
        if product_id:
            initial['product'] = product_id
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Variant created successfully.")
        response = super().form_valid(form)
        return redirect(f"{reverse_lazy('dashboard:transaction_create')}?variant={self.object.pk}")

class ProductVariantUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = "dashboard/productvariant_form.html"
    success_url = reverse_lazy("dashboard:variant_list")

    def form_valid(self, form):
        messages.success(self.request, "Variant updated successfully")
        return super().form_valid(form)

class ProductVariantDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant.all_objects, pk=pk)
        variant.soft_delete()
        messages.success(request, "Variant deleted successfully.")
        return redirect("dashboard:variant_list")

class ProductVariantRestoreView(LoginRequiredMixin, View):
    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant.all_objects, pk=pk)
        variant.restore()
        messages.success(request, "Variant restored.")
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer)

class StockTransactionListView(LoginRequiredMixin, Action, Search, Sort, ListView):
    model = StockTransaction
    template_name = "dashboard/stocktransaction_list.html"
    context_object_name = "transactions"
    paginate_by = 10
    search_fields = ["variant__name", "transaction_type"]

    default_sort_field = "transaction_date"
    allowed_sort_fields = {
        "transaction_date": "transaction_date",
        "variant": "variant__name",
        "quantity": "quantity",
        "transaction_type": "transaction_type",
        "unit_price": "unit_price",
        "discount": "discount",
    }

    table = {
        "columns": [
            {"key": "variant", "label": "Variant"},
            {"key": "transaction_type", "label": "Type"},
            {"key": "quantity", "label": "Quantity"},
            {"key": "unit_price", "label": "Unit Price"},
            {"key": "discount", "label": "Discount", "default_hidden": True},
            {"key": "total_amount", "label": "Total Amount"},
            {"key": "transaction_date", "label": "Date", "default_hidden": True},
        ],
        "actions": ["edit", "delete"],
        "model_key": "transaction",
    }

    def get_queryset(self):
        return super().get_queryset().select_related("variant__product")

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)

class StockTransactionCreateView(LoginRequiredMixin, CreateView):
    model = StockTransaction
    form_class = StockTransactionForm
    template_name = "dashboard/stocktransaction_form.html"
    success_url = reverse_lazy("dashboard:transaction_list")

    def get_initial(self):
        initial = super().get_initial()
        variant_id = self.request.GET.get('variant')
        if variant_id:
            initial['variant'] = variant_id
        return initial

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            messages.success(
                self.request,
                "Stock transaction recorded successfully."
            )
            return response

        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

class StockTransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = StockTransaction
    form_class = StockTransactionForm
    template_name = "dashboard/stocktransaction_form.html"
    success_url = reverse_lazy("dashboard:transaction_list")

    def form_valid(self, form):
        messages.success(self.request, "Transaction updated successfully")
        return super().form_valid(form)

class StockTransactionDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        transaction = get_object_or_404(StockTransaction.all_objects, pk=pk)
        transaction.soft_delete()
        messages.success(request, "Transaction deleted successfully.")
        return redirect("dashboard:transaction_list")

class TrashListView(LoginRequiredMixin, Search, ListView):
    template_name = "dashboard/trash_list.html"
    context_object_name = "trash_items"
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get("q")
        type_filter = self.request.GET.get("type")

        items = []

        if not type_filter or type_filter == "product":
            qs = Product.all_objects.filter(is_deleted=True)
            if query:
                qs = qs.filter(name__icontains=query)
            items.extend([{
                "id": p.id,
                "type": "product",
                "name": p.name,
                "stock": "",
                "updated_at": p.updated_at,
                "obj": p
            } for p in qs])

        if not type_filter or type_filter == "variant":
            qs = ProductVariant.all_objects.filter(is_deleted=True)
            if query:
                qs = qs.filter(Q(name__icontains=query) | Q(product__name__icontains=query))
            items.extend([{
                "id": v.id,
                "type": "variant",
                "name": f"{v.product.name} - {v.name}",
                "stock": "",
                "updated_at": v.updated_at,
                "obj": v
            } for v in qs])

        if not type_filter or type_filter == "category":
            qs = Category.all_objects.filter(is_deleted=True)
            if query:
                qs = qs.filter(name__icontains=query)
            items.extend([{
                "id": c.id,
                "type": "category",
                "name": c.name,
                "stock": "",
                "updated_at": c.updated_at,
                "obj": c
            } for c in qs])

        if not type_filter or type_filter == "transaction":
            qs = StockTransaction.all_objects.filter(is_deleted=True)
            if query:
                qs = qs.filter(Q(variant__name__icontains=query) | Q(notes__icontains=query))
            items.extend([{
                "id": c.id,
                "type": "transaction",
                "name": str(c.variant),
                "stock": c.quantity,
                "updated_at": c.updated_at,
                "obj": c
            } for c in qs])

        items.sort(key=lambda x: x['updated_at'], reverse=True)
        return items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_deleted"] = (
            Product.all_objects.filter(is_deleted=True).count() +
            ProductVariant.all_objects.filter(is_deleted=True).count() +
            Category.all_objects.filter(is_deleted=True).count()
        )
        context["type_filter"] = self.request.GET.get("type")
        return context

class RestoreItemView(LoginRequiredMixin, View):
    def post(self, request, item_type, pk):
        try:
            if item_type == "product":
                item = Product.all_objects.get(pk=pk)
            elif item_type == "variant":
                item = ProductVariant.all_objects.get(pk=pk)
            elif item_type == "category":
                item = Category.all_objects.get(pk=pk)
            elif item_type == "transaction":
                item = StockTransaction.all_objects.get(pk=pk)
            else:
                raise Http404
            item.restore()
            messages.success(request, f"{item_type.title()} restored successfully.")
        except Exception as e:
            messages.error(request, "Error responding item.")
        return redirect("dashboard:trash")

class PermanentDelete(LoginRequiredMixin, View):
    def post(self, request, item_type, pk):
        try:
            if item_type == "product":
                item = Product.all_objects.get(pk=pk)
            elif item_type == "variant":
                item = ProductVariant.all_objects.get(pk=pk)
            elif item_type == "category":
                item = Category.all_objects.get(pk=pk)
            elif item_type == "transaction":
                item = StockTransaction.all_objects.get(pk=pk)
            else:
                raise Http404
            item.delete()
            messages.success(request, f"{item_type.title()} permanently deleted.")
        except Exception as e:
            messages.error(request, "Error deleting item.")
        return redirect("dashboard:trash")


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

    def handle_no_permission(self):
        messages.error(self.request, "Access restricted to administrators only.")
        return redirect("dashboard:index")

class UserListView(LoginRequiredMixin, AdminRequiredMixin, Action, Search, Sort, ListView):
    model = User
    template_name = "dashboard/user_list.html"
    context_object_name = "users_list"
    paginate_by = 10
    search_fields = ["username", "email"]

    default_sort_field = "date_joined"

    allowed_sort_fields = {
        "username_display": "username",
        "username": "username",
        "email": "email",
        "role_display": "is_staff",
        "status_display": "is_active",
        "date_joined_display": "date_joined",
        "date_joined": "date_joined"
    }

    table = {
        "columns": [
            {"key": "username_display", "label": "User"},
            {"key": "email", "label": "Email"},
            {"key": "role_display", "label": "Role"},
            {"key": "status_display", "label": "Status"},
            {"key": "date_joined_display", "label": "Joined"},
        ],
        "actions": ["approve", "deactivate", "delete"],
        "model_key": "user",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_count"] = User.objects.filter(is_active=False).count()
        context["active_count"] = User.objects.filter(is_active=True).count()
        return context

class ApproveUserView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        target_user.is_active = True
        target_user.save()
        messages.success(request, f"User '{target_user.username}' has been approved and activated.")
        return redirect("dashboard:user_list")

class ToggleUserStatusView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        if target_user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("dashboard:user_list")
        target_user.is_active = not target_user.is_active
        target_user.save()
        status_str = "activated" if target_user.is_active else "deactivated"
        messages.success(request, f"User '{target_user.username}' has been {status_str}.")
        return redirect("dashboard:user_list")

class DeleteUserView(LoginRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        if target_user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect("dashboard:user_list")
        target_user.delete()
        messages.success(request, f"User '{target_user.username}' has been deleted.")
        return redirect("dashboard:user_list")

