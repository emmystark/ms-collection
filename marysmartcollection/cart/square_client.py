# cart/square_client.py
from square import Square
from square.environment import SquareEnvironment
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

try:
    client = Square(
        token=settings.SQUARE_ACCESS_TOKEN,
        environment=settings.SQUARE_ENVIRONMENT
    )
    logger.debug(f"Orders client methods: {dir(client.orders)}")
    logger.debug(f"Checkout client methods: {dir(client.checkout)}")
except Exception as e:
    logger.error(f"Failed to initialize Square client: {str(e)}")
    raise