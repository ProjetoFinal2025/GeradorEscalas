from django import template
import logging

logger = logging.getLogger(__name__)
logger.info("Carregando custom_filters.py")  # Adicionando log para debug

register = template.Library()

@register.filter
def get_item(dictionary, key):
    # logger.debug(f"get_item chamado com dictionary: {dictionary}, key: {key}")
    return dictionary.get(key)

@register.filter
def subtract(value, arg):
    """Subtrai o argumento do valor"""
    try:
        return value - arg
    except (ValueError, TypeError):
        return value 