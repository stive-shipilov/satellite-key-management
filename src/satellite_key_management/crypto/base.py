from abc import ABC, abstractmethod
from typing import List, Tuple, Any


class SecretSharingScheme(ABC):
    """
    Базовый интерфейс для схем разделения секрета.
    
    Любая конкретная схема (Шамир, Блэкли, KGH) должна наследоваться
    от этого класса и реализовывать методы split() и reconstruct().
    """

    @abstractmethod
    def split(self, secret: bytes, n: int, k: int) -> List[Tuple[int, bytes]]:
        """
        Разделить секрет на n долей с порогом k.
        
        :param secret: секрет в виде байтовой строки
        :param n: общее число долей
        :param k: пороговое число долей для восстановления
        :return: список долей в виде (индекс, доля)
        """
        pass

    @abstractmethod
    def reconstruct(self, shares: List[Tuple[int, bytes]]) -> bytes:
        """
        Восстановить секрет по k (или более) долям.
        
        :param shares: список долей в виде (индекс, доля)
        :return: восстановленный секрет в виде байтовой строки
        """
        pass