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

    def test_get_attr_datetime_formatting(self):
        from dashboard.templatetags.dynamic import get_attr
        from datetime import datetime
        class Dummy:
            def __init__(self):
                self.created_at = datetime(2026, 7, 23, 12, 0)

        d = Dummy()
        expected = '<span class="cell-muted">Jul 23, 2026 12:00</span>'
        self.assertEqual(get_attr(d, "created_at"), expected)


from django.contrib.auth.models import User
from django.urls import reverse

class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "password123"
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_unauthenticated_access_redirects_to_login(self):
        dashboard_urls = [
            reverse('dashboard:index'),
            reverse('dashboard:product_list'),
            reverse('dashboard:product_create'),
            reverse('dashboard:variant_list'),
            reverse('dashboard:transaction_list'),
            reverse('dashboard:trash'),
        ]
        for url in dashboard_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_authenticated_access_granted(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)

    def test_login_view(self):
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': self.password,
        })
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_invalid_login_view(self):
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password.")

    def test_register_creates_inactive_user_pending_approval(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123',
        })
        self.assertRedirects(response, reverse('login'))
        new_user = User.objects.get(username='newuser')
        self.assertFalse(new_user.is_active)

    def test_inactive_user_login_shows_pending_message(self):
        # Attempt to log in with an inactive user
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse('login'), {
            'username': self.username,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending admin approval")

    def test_admin_seeding_and_login_with_email(self):
        admin_user = User.objects.get(email='admin@mail.com')
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_active)

        # Login using email
        response = self.client.post(reverse('login'), {
            'username': 'admin@mail.com',
            'password': 'Admin@admin123',
        })
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_admin_can_approve_user(self):
        # Register pending user
        pending_user = User.objects.create_user(username="pendinguser", password="password123", is_active=False)

        # Admin logs in
        self.client.post(reverse('login'), {
            'username': 'admin@mail.com',
            'password': 'Admin@admin123',
        })

        # Admin views user list
        response = self.client.get(reverse('dashboard:user_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pendinguser")

        # Admin approves user
        approve_url = reverse('dashboard:user_approve', kwargs={'pk': pending_user.pk})
        response = self.client.post(approve_url)
        self.assertRedirects(response, reverse('dashboard:user_list'))

        pending_user.refresh_from_db()
        self.assertTrue(pending_user.is_active)

    def test_non_admin_cannot_access_user_list(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('dashboard:user_list'))
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_logout_view(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        # After logout, accessing dashboard should redirect to login
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_access_listings(self):
        self.client.login(username=self.username, password=self.password)
        urls = [
            reverse('dashboard:product_list'),
            reverse('dashboard:variant_list'),
            reverse('dashboard:transaction_list'),
            reverse('dashboard:trash'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed to access {url}")

