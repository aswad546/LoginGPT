"""Logging utilities."""

import logging


class Logger(object):
    """
    Logging helper class.
    """

    __slots__ = [
        # "logging" object
        '__l',
    ]

    def __init__(self, name: str):
        """
        Initialize logger object for a given name.

        :param name: Module name that the logger should be initialized for.
        """
        self.__l = logging.getLogger(name)

    def error(self, message: str) -> None:
        """
        Log error message.

        :param message: Message to log.
        """
        self.__l.info(message)

    def warning(self, message: str) -> None:
        """
        Log warning message.

        :param message: Message to log.
        """
        self.__l.info(message)

    def info(self, message: str) -> None:
        """
        Log informational message.

        :param message: Message to log.
        """
        self.__l.info(message)

    def debug(self, message: str) -> None:
        """
        Log debugging message.

        :param message: Message to log.
        """
        self.__l.debug(message)


def create_logger(name: str) -> Logger:
    """
    Create and return Logger object.

    :param name: Module name that the logger should be initialized for.
    :return: Logger object.
    """
    return Logger(name=name)
