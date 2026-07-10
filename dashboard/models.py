from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import F, Q, Sum, Case, When, IntegerField


# TODO: add meaningful comments :)
# Base
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])

    def restore(self):
        self.is_deleted = False
        self.save(update_fields=['is_deleted', 'updated_at'])


# Models
class Category(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Product(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ProductVariant(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=50, null=True, blank=True, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='variants')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    color = models.CharField(max_length=50, blank=True)
    reorder_level = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['-created_at']

        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['is_deleted']),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=['product', 'name'],
                name='unique_variant_name_per_product'
            ),
            models.UniqueConstraint(
                fields=['sku'],
                condition=Q(sku__isnull=False),
                name='unique_sku_when_not_null'
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def current_stock(self):
        result = self.transactions.aggregate(
            stock = Sum(
                Case(
                    When(
                        transaction_type = StockTransaction.TransactionType.IN,
                        then=F("quantity"),
                    ),
                    When(
                        transaction_type = StockTransaction.TransactionType.OUT,
                        then = -F("quantity"),
                    ),
                    output_field = IntegerField(),
                )
            )
        )
        return result["stock"] or 0
    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.sku:
            self.sku = f"PV-{self.pk:04d}"
            super().save(update_fields=["sku"])

class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    quantity = models.PositiveIntegerField()
    transaction_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    ALLOWED_SORT_FIELDS = {
        "transaction_date": "transaction_date",
        "variant": "variant__name",
        "quantity": "quantity",
        "transaction_type": "transaction_type",
    }

    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['variant', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.variant} (x{self.quantity})"

    def clean(self):
        if (
            self.transaction_type == self.TransactionType.OUT
            and self.quantity > self.variant.current_stock
        ):
            raise ValidationError("Insufficient stock")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    def get_queryset(self):
        qs = super().get_queryset().select_related("variant__product")
        direction = self.request.GET.get("sort", "desc")
        order_key = self.request.GET.get("order")

        order_field = self.ALLOWED_SORT_FIELDS.get(order_key, "transaction_date")

        ordering = f"-{order_field}" if direction == "desc" else order_field
        qs = qs.order_by(ordering, "id")

        return qs
