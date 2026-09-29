"""`{{ text|bullets }}` — see `jobs.markup`."""

from django import template
from django.utils.safestring import SafeString

from jobs.markup import bullets as render_bullets

register = template.Library()


@register.filter
def bullets(text: str) -> SafeString:
    """Escape free text, listing its `- ` lines. The only markup the board reads."""
    return render_bullets(text)
