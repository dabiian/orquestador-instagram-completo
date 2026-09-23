"""Explicit wait helpers."""

from __future__ import annotations

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def wait_for_presence(driver, locator, timeout: int):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))


def wait_for_visible(driver, locator, timeout: int):
    return WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))


def wait_for_clickable(driver, locator, timeout: int):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))


def wait_for_enabled(driver, locator, timeout: int):
    element = wait_for_presence(driver, locator, timeout)
    if not element.is_enabled():
        raise TimeoutError("Element is not enabled")
    return element


def wait_for_unique(driver, locator, timeout: int):
    elements = WebDriverWait(driver, timeout).until(lambda current_driver: current_driver.find_elements(*locator))
    if len(elements) != 1:
        raise TimeoutError("Expected exactly one element")
    return elements[0]


def wait_for_many(driver, locator, timeout: int):
    elements = WebDriverWait(driver, timeout).until(lambda current_driver: current_driver.find_elements(*locator))
    if not elements:
        raise TimeoutError("Expected at least one element")
    return elements