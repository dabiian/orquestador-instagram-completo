"""
Módulo de localizadores para diferentes partes del proyecto.

Aquí agrupamos y re-exportamos clases o constantes con selectores XPath u otros
locators que se usan en los servicios y flujos de RPA.
"""

from .login_locators import LoginLocators

__all__ = ["LoginLocators"]

