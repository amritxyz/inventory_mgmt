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
    price = models.IntegerField()
    cost_price = models.IntegerField(null=True, blank=True, default=0)
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
        # FIX: Filter is_deleted=False directly on the StockTransaction queryset
        result = StockTransaction.all_objects.filter(
            variant=self,
            is_deleted=False
        ).aggregate(
            stock=Sum(
                Case(
                    When(
                        transaction_type=StockTransaction.TransactionType.IN,
                        then=F("quantity"),
                    ),
                    When(
                        transaction_type=StockTransaction.TransactionType.OUT,
                        then=-F("quantity"),
                    ),
                    output_field=IntegerField(),
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


class StockTransaction(BaseModel):
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In'
        OUT = 'OUT', 'Stock Out'

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TransactionType.choices)
    quantity = models.PositiveIntegerField()
    unit_price = models.IntegerField(null=True, blank=True, default=0)
    discount = models.IntegerField(null=True, blank=True, default=0)
    cost_price = models.IntegerField(null=True, blank=True, default=0)
    transaction_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['variant', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.variant} (x{self.quantity})"

    @property
    def total_amount(self):
        qty = self.quantity or 0
        price = self.unit_price or 0
        if self.transaction_type == self.TransactionType.OUT:
            disc = self.discount or 0
            return (qty * price) - disc
        return qty * price

    def clean(self):
        super().clean()
        if self.transaction_type == self.TransactionType.OUT:
            # FIX: Exclude current instance if updating, to prevent false "Insufficient stock" errors
            qs = StockTransaction.all_objects.filter(variant=self.variant, is_deleted=False)
            if self.pk:
                qs = qs.exclude(pk=self.pk)

            current_stock = qs.aggregate(
                stock=Sum(
                    Case(
                        When(transaction_type=StockTransaction.TransactionType.IN, then=F("quantity")),
                        When(transaction_type=StockTransaction.TransactionType.OUT, then=-F("quantity")),
                        output_field=IntegerField(),
                    )
                )
            )["stock"] or 0

            if self.quantity > current_stock:
                raise ValidationError("Insufficient stock")

            # validate discount
            price_to_use = self.unit_price if self.unit_price is not None else self.variant.price
            total_before_discount = self.quantity * price_to_use
            disc = self.discount or 0
            if disc > total_before_discount:
                raise ValidationError({"discount": "Discount cannot be greater than the total amount."})
            if disc < 0:
                raise ValidationError({"discount": "Discount cannot be negative."})
        elif self.transaction_type == self.TransactionType.IN:
            if self.discount and self.discount > 0:
                raise ValidationError({"discount": "Discounts can only be applied to Stock Out transactions."})

    def save(self, *args, **kwargs):
        if self.unit_price is None or self.unit_price == 0:
            if self.transaction_type == self.TransactionType.IN:
                self.unit_price = self.variant.cost_price or 0
            else:
                self.unit_price = self.variant.price or 0

        if self.discount is None:
            self.discount = 0

        if self.transaction_type == self.TransactionType.OUT:
            if self.cost_price is None or self.cost_price == 0:
                self.cost_price = self.variant.cost_price or 0
        else:
            self.cost_price = self.unit_price
            self.discount = 0

        self.full_clean()
        super().save(*args, **kwargs)

        # Update the variant's cost price to the price of the latest IN transaction
        if self.transaction_type == self.TransactionType.IN and self.unit_price > 0:
            ProductVariant.objects.filter(pk=self.variant_id).update(cost_price=self.unit_price)
