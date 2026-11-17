"""Общая фикстура для тестов: настраивает sys.path так, чтобы работали
импорты вида ``from crypto.shamir import ...`` (как в коде проекта)
и ``from satellite_key_management.crypto import ...`` (пакетный вариант)."""
import os
import sys

# Корень пакета: src/satellite_key_management — туда, где лежит crypto/.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_ROOT = os.path.abspath(os.path.join(_HERE, "..", "src", "satellite_key_management"))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))

for p in (_PACKAGE_ROOT, _SRC):
    if p not in sys.path:
        sys.path.insert(0, p)