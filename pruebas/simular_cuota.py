"""Simulador del límite de tokens por minuto del plan gratuito de Groq (openai/gpt-oss-120b).

Regla medida con las cabeceras x-ratelimit-* y los 429 de Groq (pruebas/medir_cuota.py):
- un balde de 8000 tokens que se rellena continuo, a 8000/60 = 133,3 tokens por segundo;
- una llamada entra si en el balde quedan al menos los tokens que Groq "pide" por ella, que
  estima de la entrada: pidió 5428 para una entrada de 5040 (factor 1,077), sin contar el
  máximo de salida;
- después se descuenta lo gastado de verdad: entrada + salida, razonamiento incluido;
- la app reintenta una vez si Groq pide esperar 8 s o menos (ESPERA_MAXIMA_REINTENTO).

Con gpt-oss-20b Groq sí suma el máximo de salida a lo pedido (ver pruebas/opciones.md), así
que este simulador no vale para ese modelo.

    python pruebas/simular_cuota.py     # ejemplo con la consulta medida a mano (P01)
"""

from __future__ import annotations

CAP = 8000.0
RITMO = CAP / 60  # tokens por segundo
FACTOR_PEDIDO = 5428 / 5040
ESPERA_APP = 8.0
DURACION = 3.0  # s que tarda cada llamada (medido: 1,4 a 6 s)

Llamada = tuple[int, int]  # (tokens de entrada, tokens de salida)


def correr(consultas: list[list[Llamada]], delta: float, nivel0: float = CAP) -> tuple[bool, list[dict]]:
    """Consultas una cada `delta` segundos; cada una es la lista de sus llamadas en orden.
    Con el balde no lleno (nivel0 < CAP: alguien acaba de consultar), la primera empieza
    `delta` segundos después. Devuelve (todas entraron, detalle por consulta)."""
    desfase = delta if nivel0 < CAP else 0.0
    nivel, t, detalle = nivel0, 0.0, []
    for i, llamadas in enumerate(consultas):
        inicio = i * delta + desfase
        nivel, t = min(CAP, nivel + (inicio - t) * RITMO), inicio
        espera_total, ok = 0.0, True
        for entrada, salida in llamadas:
            pedido = entrada * FACTOR_PEDIDO
            if nivel < pedido:
                espera = (pedido - nivel) / RITMO
                if espera > ESPERA_APP:
                    ok = False
                    break
                espera_total += espera
                nivel, t = nivel + espera * RITMO, t + espera
            nivel -= entrada + salida
            nivel, t = min(CAP, nivel + DURACION * RITMO), t + DURACION
        detalle.append({"ok": ok, "espera_s": round(espera_total, 1), "nivel_despues": round(nivel)})
        if not ok:
            return False, detalle
    return True, detalle


def delta_minimo(consultas: list[list[Llamada]], nivel0: float = CAP) -> float:
    """Menor separación (s) entre consultas para que entren todas seguidas."""
    lo, hi = 0.0, 300.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if correr(consultas, mid, nivel0)[0] else (mid, hi)
    return hi


def cuantas_entran(consultas: list[list[Llamada]], delta: float, nivel0: float = CAP) -> int:
    return sum(d["ok"] for d in correr(consultas, delta, nivel0)[1])


if __name__ == "__main__":
    # P01 medida a mano: normalización 632 + 388; respuesta 5040 + 1018 (y 5040 + 1770 con la misma entrada)
    for salida in (1018, 1770):
        cache = [[(5040, salida)]] * 5
        nueva = [[(632, 388), (5040, salida)]] * 5
        print(
            f"salida {salida}: Δ mínimo para 5 seguidas · en caché {delta_minimo(cache):.0f} s, nuevas "
            f"{delta_minimo(nueva):.0f} s · con el balde recién usado {delta_minimo(cache, 0):.0f} s · "
            f"a 36 s entran {cuantas_entran(cache, 36)} de 5"
        )
