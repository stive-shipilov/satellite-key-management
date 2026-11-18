"""Короткая демонстрация для защиты. Числа в примерах открыты."""
from ..crypto.blakley import Blakley
from ..crypto.xor_scheme import CRTScheme, XorScheme
from .threshold import choose_threshold


def main():
    planes = [(4, 8, 2, 6), (2, 6, 8, 3), (6, 8, 4, 1)]
    blakley = Blakley(11)
    print("Блэкли, GF(11). Секрет по трём плоскостям:", blakley.reconstruct(planes))
    try:
        blakley.reconstruct(planes[:2])
    except ValueError as error:
        print("По двум плоскостям:", error)
    for scheme in (XorScheme(6, 8), CRTScheme(6, 8)):
        shares = scheme.split_secret(42)
        print(f"{type(scheme).__name__}, 6 из 6: {scheme.reconstruct(shares)}")
        try:
            scheme.reconstruct(shares[:-1])
        except ValueError as error:
            print("5 из 6:", error)
    print("Шесть спутников, видны четыре:")
    for threat in (0, 0.4, 0.8):
        k = choose_threshold(6, 4, threat)
        print(f"  Уровень угрозы {threat:g} —", f"порог {k}" if k else "сессия отложена")


if __name__ == "__main__":
    main()
