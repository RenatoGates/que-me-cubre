"""Prueba la interfaz sin navegador y sin gastar cuota (streamlit.testing.AppTest).

Usa el proveedor "grabado" (ai/llm.py): la respuesta del modelo es la que ya dio para esa
pregunta en pruebas/salidas/; la búsqueda, la verificación de citas y el bloque de
ausentes corren de verdad. Comprueba el contrato del README ("Cómo se muestra una
respuesta"): veredicto arriba sacado del campo estructurado, explicación, B4 resaltado,
remisiones plegadas, citas desplegables, "podrían aplicar" aparte, aviso permanente, y la
red de seguridad cuando no hay modelo.

    python pruebas/probar_app.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import os

from comun import RAIZ, utf8

os.environ["QMC_PROVEEDOR"] = "grabado"

from streamlit.testing.v1 import AppTest  # noqa: E402

FALLAS: list[str] = []


def caso(nombre: str, ok: bool, detalle: str = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def textos(at: AppTest) -> str:
    partes = [m.value for m in at.markdown] + [m.value for m in at.caption]
    partes += [w.body for w in at.warning] + [w.body for w in at.info] + [e.label for e in at.expander]
    return "\n".join(partes)


def main() -> int:
    utf8()
    at = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=180).run()
    caso("la app carga sin errores", not at.exception, str(at.exception))
    t = textos(at)
    caso("aviso permanente: PDF en memoria", "se procesa en memoria y no se guarda" in t)
    caso("aviso permanente: lo que se envía al proveedor", "Respuesta grabada" in t or "Groq" in t)
    caso("aviso permanente: informativo, decide la aseguradora", "la decisión final sobre la cobertura la toma tu aseguradora" in t)
    caso("dos botones de Tarapoto con el texto exacto",
         [b.label for b in at.button if b.key and b.key.startswith("tarapoto_")] == [
             "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?",
             "Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?"])

    # P02 desde Pacífico: el botón tiene que cambiar a la póliza de Chubb
    at.radio(key="fuente").set_value("pacifico_viajes").run()
    at.button(key="tarapoto_1").click().run()
    caso("P02: responde sin errores", not at.exception, str(at.exception))
    caso("P02: el botón cambia a la póliza de Chubb", at.radio(key="fuente").value == "chubb_viajes_jetsmart")
    t = textos(at)
    html = "\n".join(m.value for m in at.markdown)
    caso("P02: el veredicto arriba es la etiqueta del campo estructurado", 'class="qmc-veredicto"' in html and "Cubre con límites" in html)
    orden = [html.find('class="qmc-veredicto"'), t.find("Lo que tu póliza menciona pero no trae"), t.find("Citas de tu póliza")]
    caso("P02: orden veredicto → menciones → citas", -1 not in orden and orden == sorted(orden), str(orden))
    b4 = [w.body for w in at.warning if "B4" in w.body]
    caso("P02: B4 resaltado con su página", bool(b4) and "pág. 16" in b4[0], str(b4)[:200])
    caso("P02: remisiones plegadas en un desplegable", any(e.label.startswith("Remisiones a otros documentos") for e in at.expander))
    caso("P02: cada cita es un desplegable con su página",
         sum(e.label.startswith("Cita ") and "pág." in e.label for e in at.expander) >= 1)

    # P01: tiene "podrían aplicar" (preexistencia) en la grabación de pruebas/salidas
    at.button(key="tarapoto_0").click().run()
    t = textos(at)
    caso("P01: responde sin errores", not at.exception, str(at.exception))
    caso("P01: 'podrían aplicar' aparte y como posibilidad",
         "Exclusiones que podrían aplicar según tu caso" in t and "No es lo que pasó" in t)

    # Red de seguridad: una pregunta sin grabación (el proveedor de maqueta no responde)
    at.text_area(key="pregunta").set_value("¿Me cubren si pierdo el pasaporte en Cusco?").run()
    at.button[0].click().run()
    t = textos(at)
    html = "\n".join(m.value for m in at.markdown)
    caso("red de seguridad: sin errores", not at.exception, str(at.exception))
    caso("red de seguridad: etiqueta 'Sin veredicto' y el aviso", "Sin veredicto" in html and "No generé una respuesta" in t)
    caso("red de seguridad: muestra las cláusulas encontradas", "Cláusulas que encontré para tu pregunta" in t)

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
