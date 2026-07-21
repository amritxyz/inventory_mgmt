from django import template

register = template.Library()

# Import Nepalese number formatting utility
from dashboard.utils.formatting import format_nepalese_number

@register.filter
def get_attr(obj, attr):
    """Retrieve attribute and format monetary values with Nepalese style."""
    val = getattr(obj, attr, "")
    if val is None:
        return ""
    if attr in ['price', 'cost_price', 'unit_price', 'discount', 'total_amount']:
        if val != "":
            try:
                return f"Rs. {format_nepalese_number(int(val))}"
            except Exception:
                pass
    return val

@register.filter(name='currency')
def currency(value):
    """Format integer as Nepalese currency string."""
    try:
        return f"Rs. {format_nepalese_number(int(value))}"
    except Exception:
        return value


