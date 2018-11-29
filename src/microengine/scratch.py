import logging
from polyswarmclient.abstractmicroengine import AbstractMicroengine

logger = logging.getLogger(__name__)  # Initialize logger


class Microengine(AbstractMicroengine):
    """Scratch microengine is the same as the default behavior."""
    pass
