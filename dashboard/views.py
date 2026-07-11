from dashboard.utils.actions import resolve_actions
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Case, Count, QuerySet, Sum, When, F
from django.db.models import IntegerField
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

"""
Helper classes / methods
"""
class IndexView(TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # OPTIMIZATION: Annotate stock to avoid N+1 database queries in the loop below
        variants = ProductVariant.objects.annotate(
            stock_balance=Sum(
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

        context["total_variants"] = variants.count()
        context["low_stock_count"] = sum(
            1 for variant in variants if (variant.stock_balance or 0) <= variant.reorder_level
        )

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

        order_field = self.allowed_sort_fields.get(order_key, self.default_sort_field)
        ordering = f"-{order_field}" if direction == "desc" else order_field

        return queryset.order_by(ordering, "-id")

class Action:
    table = {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []

        for obj in context[self.context_object_name]:
            rows.append({
                "obj": obj,
                "actions": resolve_actions(
                    self.table["model_key"],
                    self.table.get("actions", []),
                    obj,
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
class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def form_valid(self, form):
        messages.success(self.request, "Product created successfully")
        response = super().form_valid(form)
        return redirect(f"{reverse_lazy('dashboard:variant_create')}?product={self.object.pk}")

class ProductUpdateView(UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def get_queryset(self):
        return Product.all_objects

    def form_valid(self, form):
        messages.success(self.request, "Product updated successfully.")
        return super().form_valid(form)

class ProductDeleteView(View):
    def post(self, request, pk):
        product = get_object_or_404(Product.all_objects, pk=pk)
        product.soft_delete()
        messages.success(request, "Product deleted successfully")
        return redirect("dashboard:product_list")

class ProductRestoreView(View):
    def post(self, request, pk):
        product = get_object_or_404(Product.all_objects, pk=pk)
        product.restore()
        messages.success(request, "Product restored.")
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer)

class ProductListView(Action, Search, Sort, ListView):
    model = Product
    template_name = "dashboard/product_list.html"
    context_object_name = "products"
    paginate_by = 10
    search_fields = ["name"]

    default_sort_field = "name"
    allowed_sort_fields = {
        "name": "name",
        "variants": "variant_count"
    }

    table = {
        "columns": [
            {"key": "name", "label": "Product Name"},
            {"key": "variant_count", "label": "Variants"},
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

class ProductVariantListView(Action, Search, Sort, ListView):
    model = ProductVariant
    template_name = "dashboard/productvariant_list.html"
    context_object_name = "variants"
    search_fields = ["name", "sku", "product__name"]
    paginate_by = 10

    default_sort_field = "name"
    allowed_sort_fields = {
        "product_name": "product__name",
        "variant": "name",
        "sku": "sku",
        "price": "price",
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

    table = {
        "columns": [
            {"key": "product", "label": "Product"},
            {"key": "name", "label": "Variant"},
            {"key": "sku", "label": "SKU"},
            {"key": "price", "label": "Price"},
            {"key": "stock_balance", "label": "Stock"},
        ],
        "actions": ["transact", "edit", "delete"],
        "model_key": "variant",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class ProductVariantCreateView(CreateView):
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

class ProductVariantUpdateView(UpdateView):
    model = ProductVariant
    form_class = ProductVariantForm
    template_name = "dashboard/productvariant_form.html"
    success_url = reverse_lazy("dashboard:variant_list")

    def form_valid(self, form):
        messages.success(self.request, "Variant updated successfully")
        return super().form_valid(form)

class ProductVariantDeleteView(View):
    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant.all_objects, pk=pk)
        variant.soft_delete()
        messages.success(request, "Variant deleted successfully.")
        return redirect("dashboard:variant_list")

class ProductVariantRestoreView(View):
    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant.all_objects, pk=pk)
        variant.restore()
        messages.success(request, "Variant restored.")
        referer = request.META.get("HTTP_REFERER")
        return redirect(referer)

class StockTransactionListView(Action, Search, Sort, ListView):
    model = StockTransaction
    template_name = "dashboard/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 10
    search_fields = ["variant__name", "transaction_type"]

    default_sort_field = "transaction_date"
    allowed_sort_fields = {
        "transaction_date": "transaction_date",
        "variant": "variant__name",
        "quantity": "quantity",
        "transaction_type": "transaction_type"
    }

    table = {
        "columns": [
            {"key": "variant", "label": "Variant"},
            {"key": "transaction_type", "label": "Transaction Type"},
            {"key": "quantity", "label": "Quantity"},
            {"key": "transaction_date", "label": "Date"},
        ],
        "actions": ["edit", "delete"],
        "model_key": "transaction",
    }

    def get_queryset(self):
        qs = super().get_queryset().select_related("variant__product")

        direction = self.request.GET.get("sort", "desc")
        order_key = self.request.GET.get("order")

        order_field = self.allowed_sort_fields.get(order_key, self.default_sort_field)

        ordering = f"-{order_field}" if direction == "desc" else order_field
        return qs.order_by(ordering, "id")

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)

class StockTransactionCreateView(CreateView):
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

class StockTransactionUpdateView(UpdateView):
    model = StockTransaction
    form_class = StockTransactionForm
    template_name = "dashboard/stocktransaction_form.html"
    success_url = reverse_lazy("dashboard:transaction_list")

    def form_valid(self, form):
        messages.success(self.request, "Transaction updated successfully")
        return super().form_valid(form)

class StockTransactionDeleteView(View):
    def post(self, request, pk):
        transaction = get_object_or_404(StockTransaction.all_objects, pk=pk)
        transaction.soft_delete()
        messages.success(request, "Transaction deleted successfully.")
        return redirect("dashboard:transaction_list")

class TrashListView(Search, ListView):
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
                # FIX: StockTransaction doesn't have a 'name' field, search by variant name or notes
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

class RestoreItemView(View):
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

class PermanentDelete(View):
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
