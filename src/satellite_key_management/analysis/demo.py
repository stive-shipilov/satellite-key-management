"""Короткая демонстрация для защиты. Числа в примерах открыты."""
from ..crypto.blakley import Blakley
from ..crypto.xor_scheme import CRTScheme, XorScheme
from ..simulation.leo_model import LEOModel
from ..simulation.telemetry import TelemetrySession
from .threshold import choose_threshold


def telemetry_demo():
    """Одна и та же видимость для всех четырёх реализаций, независимые ключи."""
    leo = LEOModel(n_sats=72, n_planes=6, seed=7)
    members = leo.visible_at(53)
    print(f"Телеметрия AES-128-GCM. Спутники сеанса: {members}.")
    message = b"temperature=21.5"
    for name, k in (("shamir", 2), ("blakley", 2), ("xor", len(members)), ("crt", len(members))):
        session = TelemetrySession.issue(name, members, k, message, aad=b"telemetry/v1")
        for minute in (53, 54):
            received = session.receive(leo, minute)
            value = received.decode("ascii") if received is not None else "ожидаем кворум"
            print(f"  {name:7} {k} из {len(members)}, t={minute} мин: {value}")


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
    telemetry_demo()


if __name__ == "__main__":
    main()
