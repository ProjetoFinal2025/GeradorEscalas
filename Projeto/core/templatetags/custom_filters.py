from django import template
import logging

logger = logging.getLogger(__name__)
register = template.Library()

@register.filter
def get_item(dictionary, key):
    logger.debug(f"get_item chamado com dictionary: {dictionary}, key: {key}")
    return dictionary.get(key) 