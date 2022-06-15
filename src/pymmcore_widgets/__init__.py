"""A set of widgets for the pymmcore-plus module."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pymmcore-widgets")
except PackageNotFoundError:
    __version__ = "uninstalled"
__author__ = "Federico Gasparoli"
__email__ = "federico.gasparoli@gmail.com"
