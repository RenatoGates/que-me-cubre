"""Prueba la interfaz sin navegador y sin gastar cuota (streamlit.testing.AppTest).

Usa el proveedor "grabado" (ai/llm.py): la respuesta del modelo es la que ya dio para esa
pregunta en pruebas/salidas/; la búsqueda, la verificación de citas y el bloque de
ausentes corren de verdad. Comprueba el contrato del README ("Cómo se muestra una
respuesta"): veredicto arriba sacado del campo estructurado, explicación, B4 resaltado,
remisiones plegadas, citas desplegables, "podrían aplicar" aparte, aviso permanente, y la
red de seguridad cuando no hay modelo. También la pantalla de entrada (subir el PDF arriba,
condicionados de ejemplo debajo, cómo funciona) y la subida de una póliza en dos PDF.

    python pruebas/probar_app.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import os

from comun import RAIZ, partir_pdf, utf8

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
    caso("cómo funciona: los tres pasos debajo del título",
         all(x in t for x in ("Sube el PDF de tu póliza o usa un ejemplo.", "Pregunta en español normal.",
                              "Te respondo con la cláusula exacta y su página.")))
    caso("arriba y destacado: subir el PDF (varios archivos)",
         "Sube el PDF de tu póliza" in t and at.file_uploader(key="pdfs").accept_multiple_files)
    caso("debajo, en chico: los condicionados de ejemplo, Chubb elegido",
         "¿No tienes una a mano? Prueba con un condicionado de ejemplo:" in t
         and at.radio(key="fuente").options == ["Chubb Seguros Perú · Seguro de Viajes JetSmart",
                                                 "Pacífico Seguros · Seguro de Viajes Pacífico",
                                                 "Rimac Seguros · Seguro de Viaje"]
         and at.radio(key="fuente").value == "chubb_viajes_jetsmart", str(at.radio(key="fuente").options))
    caso("ayuda bajo la pregunta: 'Una pregunta a la vez.'", "Una pregunta a la vez." in t)
    def ejemplos(at: AppTest) -> list[str]:
        return [b.label for b in at.button if b.key and b.key.startswith("tarapoto_")]

    caso("con Chubb: los dos ejemplos con el texto exacto (el de la caché)", ejemplos(at) == [
        "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?",
        "Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?"])
    caso("con Chubb: rótulo discreto 'Prueba con un ejemplo:'", "Prueba con un ejemplo:" in t and "Casos reales" not in t)

    # Los ejemplos son de Chubb: con otra póliza no aparecen (con un PDF propio, abajo)
    at.radio(key="fuente").set_value("pacifico_viajes").run()
    caso("con Pacífico: sin ejemplos", not ejemplos(at) and "Prueba con un ejemplo:" not in textos(at), str(ejemplos(at)))

    # P02 con Chubb
    at.radio(key="fuente").set_value("chubb_viajes_jetsmart").run()
    at.button(key="tarapoto_1").click().run()
    caso("P02: responde sin errores", not at.exception, str(at.exception))
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

    # Dónde atenderte: RENIPRESS, sin modelo
    caso("mapa: arranca en San Martín · Tarapoto",
         (at.selectbox(key="mapa_departamento").value, at.selectbox(key="mapa_distrito").value)
         == ("SAN MARTIN", ("SAN MARTIN", "TARAPOTO")))
    tabla = at.dataframe[0].value
    caso("mapa: Tarapoto lista sus establecimientos activos",
         len(tabla) == 148 and "HOSPITAL TARAPOTO" in set(tabla["Nombre"]), str(len(tabla)))
    caso("mapa: el aviso de que no es la red de la aseguradora",
         any("no la red de tu aseguradora" in w.body for w in at.warning))
    caso("mapa: cita la fuente y la licencia", "Fuente: RENIPRESS, SUSALUD" in textos(at) and "ODC-BY" in textos(at))
    at.toggle(key="mapa_internamiento").set_value(True).run()
    tabla = at.dataframe[0].value
    caso("mapa: solo con internamiento", 0 < len(tabla) < 148 and "HOSPITAL TARAPOTO" in set(tabla["Nombre"]), str(len(tabla)))
    at.selectbox(key="mapa_departamento").set_value("LIMA").run()
    caso("mapa: cambiar de departamento no rompe",
         not at.exception and at.selectbox(key="mapa_distrito").value[0] != "SAN MARTIN", str(at.exception))

    # Una póliza en dos PDF (la de Chubb partida antes de la página 11): un solo documento
    parte1, parte2 = partir_pdf((RAIZ / "data" / "polizas" / "chubb_viajes_jetsmart.pdf").read_bytes(), [11])
    at.file_uploader(key="pdfs").set_value([("condiciones_generales.pdf", parte1, "application/pdf"),
                                            ("clausulas_adicionales.pdf", parte2, "application/pdf")]).run()
    t = textos(at)
    caso("dos PDF: se leen como un solo documento", not at.exception and "Listo: 62 páginas, 246 fragmentos" in t,
         str(at.exception) or t[-300:])
    caso("dos PDF: sin condicionados de ejemplo ni ejemplos de Chubb",
         not [r for r in at.radio if r.key == "fuente"] and not ejemplos(at))
    # Sin normalización en la caché para estos archivos, el proveedor de maqueta cae en la red
    # de seguridad: muestra los pasajes encontrados con el archivo de cada uno
    at.text_area(key="pregunta").set_value("¿Me cubren la continuación de tratamiento en mi país de residencia?").run()
    at.button[0].click().run()
    caso("dos PDF: responde sin errores", not at.exception, str(at.exception))
    etiquetas = [e.label for e in at.expander]
    caso("dos PDF: cada pasaje dice de qué archivo sale y su página",
         any("clausulas_adicionales.pdf, pág." in e for e in etiquetas), str(etiquetas)[:300])
    b4 = [w.body for w in at.warning if "B4" in w.body]
    caso("dos PDF: B4 con su archivo y su página en ese archivo",
         bool(b4) and "clausulas_adicionales.pdf, pág. 6" in b4[0], str(b4)[:300])

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
