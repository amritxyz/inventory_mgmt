from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Import Nepalese number formatting utility
from dashboard.utils.formatting import format_nepalese_number

from datetime import datetime

@register.filter
def get_attr(obj, attr):
    """Retrieve attribute and format monetary values, callables, emails, and dates."""
    val = getattr(obj, attr, "")
    if callable(val):
        try:
            val = val()
        except Exception:
            pass
    if val is None:
        return ""
    if attr in ['price', 'cost_price', 'unit_price', 'discount', 'total_amount']:
        if val != "":
            try:
                return f"Rs. {format_nepalese_number(int(val))}"
            except Exception:
                pass
    elif attr == "email":
        return val if val else "—"
    elif isinstance(val, datetime):
        return mark_safe(f'<span class="cell-muted">{val.strftime("%b %d, %Y %H:%M")}</span>')
    return val

@register.filter(name='currency')
def currency(value):
    """Format integer as Nepalese currency string."""
    try:
        return f"Rs. {format_nepalese_number(int(value))}"
    except Exception:
        return value


