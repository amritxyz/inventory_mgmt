from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from dashboard.models import Category, Product, ProductVariant, StockTransaction

class FinancialFeatureTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics", description="Electronic gadgets")
        self.product = Product.objects.create(name="Smartphone")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Model X",
            sku="PV-X100",
            category=self.category,
            price=800,
            cost_price=500,
            reorder_level=5
        )

    def test_stock_in_defaults(self):
        # Create a Stock In transaction
        tx = StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=10
        )
        # unit_price should default to variant's cost_price
        self.assertEqual(tx.unit_price, 500)
        # cost_price for IN should match unit_price
        self.assertEqual(tx.cost_price, 500)
        # discount for IN should be 0
        self.assertEqual(tx.discount, 0)
        # total_amount calculation: 10 * 500 = 5000
        self.assertEqual(tx.total_amount, 5000)

    def test_stock_out_defaults(self):
        # First stock in so we have enough inventory
        StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=10
        )
        # Create a Stock Out transaction without price/discount
        tx = StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=3
        )
        # unit_price should default to variant's selling price
        self.assertEqual(tx.unit_price, 800)
        # cost_price should default to variant's cost_price
        self.assertEqual(tx.cost_price, 500)
        # discount should default to 0
        self.assertEqual(tx.discount, 0)
        # total_amount: 3 * 800 - 0 = 2400
        self.assertEqual(tx.total_amount, 2400)

    def test_stock_out_with_custom_price_and_discount(self):
        # Stock in first
        StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=10
        )
        # Create Stock Out with custom price and discount
        tx = StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.OUT,
            quantity=2,
            unit_price=750,
            discount=50
        )
        self.assertEqual(tx.unit_price, 750)
        self.assertEqual(tx.discount, 50)
        self.assertEqual(tx.cost_price, 500)
        # total_amount: 2 * 750 - 50 = 1450
        self.assertEqual(tx.total_amount, 1450)

    def test_invalid_discount_validation(self):
        StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=10
        )
        # Discount cannot be negative
        with self.assertRaises(ValidationError):
            tx = StockTransaction(
                variant=self.variant,
                transaction_type=StockTransaction.TransactionType.OUT,
                quantity=1,
                discount=-10
            )
            tx.full_clean()

        # Discount cannot exceed transaction total
        with self.assertRaises(ValidationError):
            tx = StockTransaction(
                variant=self.variant,
                transaction_type=StockTransaction.TransactionType.OUT,
                quantity=1,
                unit_price=800,
                discount=850
            )
            tx.full_clean()

        # Discount cannot be applied to IN transaction
        with self.assertRaises(ValidationError):
            tx = StockTransaction(
                variant=self.variant,
                transaction_type=StockTransaction.TransactionType.IN,
                quantity=5,
                discount=10
            )
            tx.full_clean()

    def test_cost_price_auto_updates_on_variant(self):
        # Initial variant cost_price is 500
        self.assertEqual(self.variant.cost_price, 500)
        # Create a Stock In transaction at cost 600
        StockTransaction.objects.create(
            variant=self.variant,
            transaction_type=StockTransaction.TransactionType.IN,
            quantity=5,
            unit_price=600
        )
        # Refresh from database
        self.variant.refresh_from_db()
        # The variant's cost_price should be updated to 600
        self.assertEqual(self.variant.cost_price, 600)


class TemplateTagTestCase(TestCase):
    def test_get_attr_currency_formatting(self):
        from dashboard.templatetags.dynamic import get_attr
        class Dummy:
            def __init__(self):
                self.price = 12345
                self.cost_price = 0
                self.name = "Test Name"
                self.other = None

        d = Dummy()
        self.assertEqual(get_attr(d, "price"), "Rs. 12,345")
        self.assertEqual(get_attr(d, "cost_price"), "Rs. 0")
        self.assertEqual(get_attr(d, "name"), "Test Name")
        self.assertEqual(get_attr(d, "other"), "")
