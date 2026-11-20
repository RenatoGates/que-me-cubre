"""Prueba la interfaz sin navegador y sin gastar cuota (streamlit.testing.AppTest).

Levanta la API en este mismo proceso y la app la consume por HTTP, como desplegada.
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

import socket  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    PUERTO = _s.getsockname()[1]
os.environ.update({
    "QMC_PROVEEDOR": "grabado",
    "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
    "QMC_LIMITE_DISPOSITIVO_DIA": "50",
    "QMC_GOOGLE_CLIENT_IDS": "cliente-de-prueba.apps.googleusercontent.com",
    "LANGFUSE_PUBLIC_KEY": "",
    "LANGFUSE_SECRET_KEY": "",
    "VOYAGE_API_KEY": "",
    "QMC_API_URL": f"http://127.0.0.1:{PUERTO}",
})

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from backend import guardado  # noqa: E402
from backend import main as main_api  # noqa: E402
from backend.main import app as api  # noqa: E402

os.environ["QMC_CLAVE_DATOS"] = guardado.nueva_llave()  # llave de prueba, solo de este proceso


def levantar_api() -> None:
    """La app es cliente de la API: se levanta la de verdad, en este proceso, con respuestas grabadas."""
    servidor = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=PUERTO, log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{PUERTO}/salud", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError("la API no levantó")

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
    levantar_api()
    at = AppTest.from_file(str(RAIZ / "app" / "app.py"), default_timeout=180)
    # Como en Streamlit Cloud con la sección [auth] de Google en los secrets (valores de prueba)
    at.secrets["auth"] = {"redirect_uri": "http://localhost:8501/oauth2callback", "cookie_secret": "prueba",
                          "client_id": "cliente-de-prueba.apps.googleusercontent.com", "client_secret": "prueba",
                          "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
                          "expose_tokens": "id"}
    at.run()
    caso("la app carga sin errores", not at.exception, str(at.exception))
    t = textos(at)
    pie = [m.value for m in at.markdown if 'class="qmc-pie"' in m.value]
    caso("privacidad en un pie de página, con enlace a la política completa",
         len(pie) == 1 and "se procesa en memoria y no se guarda" in pie[0] and "docs/privacidad.md" in pie[0]
         and "Política de privacidad</a>" in pie[0], str(pie)[:300])
    caso("pie: lo que se envía al proveedor y que es informativo",
         ("Respuesta grabada" in pie[0] or "Groq" in pie[0]) and "la decisión final sobre la cobertura la toma tu aseguradora" in pie[0])
    caso("arriba no hay un bloque de texto de privacidad", not any("se procesa en memoria" in i.body for i in at.info))
    caso("el nombre de la app: ¿Qué Cubre?", any("¿Qué Cubre?</p>" in m.value for m in at.markdown))
    caso("cómo funciona: los tres pasos debajo del título",
         all(x in t for x in ("Sube el PDF de tu póliza o usa un ejemplo.", "Pregunta en español normal.",
                              "Te respondo con la cláusula exacta y su página.")))
    caso("arriba y destacado: subir el PDF (varios archivos)",
         "Sube el PDF de tu póliza" in t and at.file_uploader(key="pdfs").accept_multiple_files)
    caso("debajo, en chico: los condicionados de ejemplo, Chubb elegido",
         "¿No tienes una a mano? Prueba con un condicionado de ejemplo:" in t
         and at.radio(key="fuente").options == ["Chubb Seguros Perú · Seguro de Viajes JetSmart",
                                                 "Pacífico Seguros · Seguro de Viajes Pacífico",
                                                 "Rimac Seguros · Seguro de Viaje",
                                                 "Mapfre Perú · Accidentes Personales con Asistencia en Viaje para Turismo",
                                                 "Interseguro · Seguro de Viaje Internacional"]
         and at.radio(key="fuente").value == "chubb_viajes_jetsmart", str(at.radio(key="fuente").options))
    caso("ayuda bajo la pregunta: hasta 3 preguntas en el mismo texto", "hasta 3 preguntas en el mismo texto" in t)
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
    caso("P02: 'podrían aplicar' aparte y como posibilidad",
         "Exclusiones que podrían aplicar según tu caso" in t and "No es lo que pasó" in t)
    orden = [html.find('class="qmc-veredicto"'), t.find("Lo que tu póliza menciona pero no trae"), t.find("Citas de tu póliza")]
    caso("P02: orden veredicto → menciones → citas", -1 not in orden and orden == sorted(orden), str(orden))
    b4 = [w.body for w in at.warning if "B4" in w.body]
    caso("P02: B4 resaltado con su página", bool(b4) and "pág. 16" in b4[0], str(b4)[:200])
    caso("P02: remisiones plegadas en un desplegable", any(e.label.startswith("Remisiones a otros documentos") for e in at.expander))
    caso("P02: cada cita es un desplegable con su página",
         sum(e.label.startswith("Cita ") and "pág." in e.label for e in at.expander) >= 1)

    at.button(key="tarapoto_0").click().run()
    t = textos(at)
    html = "\n".join(m.value for m in at.markdown)
    caso("P01: responde sin errores", not at.exception, str(at.exception))
    caso("P01: veredicto, B4 y citas", "Cubre con límites" in html and any("B4" in w.body for w in at.warning)
         and "Citas de tu póliza" in t)

    # Qué hacer ahora: sin modelo (maqueta) muestra las cláusulas del aviso del siniestro, sin inventar pasos
    at.button(key="ver_pasos").click().run()
    t = textos(at)
    caso("pasos: sin modelo, el aviso y las cláusulas sobre el aviso del siniestro",
         not at.exception and "No pude redactar los pasos ahora" in t and any("Aviso" in e.label for e in at.expander), str(at.exception))

    # Radiografía sin cuenta: se muestra bloqueada, no se oculta
    caso("radiografía sin cuenta: visible y bloqueada",
         any(e.label.startswith("🔒 Radiografía de tu póliza") for e in at.expander) and "Crea una cuenta gratis para ver una" in textos(at)
         and not [b for b in at.button if b.key == "ver_radiografia"])

    # Red de seguridad: una pregunta sin grabación (el proveedor de maqueta no responde)
    at.text_area(key="pregunta").set_value("¿Me cubren si pierdo el pasaporte en Cusco?").run()
    at.button(key="preguntar").click().run()
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
    at.button(key="preguntar").click().run()
    caso("dos PDF: responde sin errores", not at.exception, str(at.exception))
    etiquetas = [e.label for e in at.expander]
    caso("dos PDF: cada pasaje dice de qué archivo sale y su página",
         any("clausulas_adicionales.pdf, pág." in e for e in etiquetas), str(etiquetas)[:300])
    b4 = [w.body for w in at.warning if "B4" in w.body]
    caso("dos PDF: B4 con su archivo y su página en ese archivo",
         bool(b4) and "clausulas_adicionales.pdf, pág. 6" in b4[0], str(b4)[:300])

    # Mi cuenta: Google primero, correo después, «¿Olvidaste tu contraseña?», crear cuenta, guardar y borrar todo
    t = textos(at)
    botones = [b.key for b in at.button]
    caso("acceso: «Entrar con Google» es la opción principal, antes del correo",
         "google" in botones and at.button(key="google").proto.type == "primary" and "o con tu correo" in t
         and botones.index("google") < botones.index("entrar_boton"), str(botones))
    caso("acceso: sin párrafos ni avisos sobre la contraseña",
         not any(x in t for x in ("no podemos recuperarla", "No guardamos el archivo PDF", "Sin cuenta todo funciona igual")))
    caso("acceso: el enlace «¿Olvidaste tu contraseña?» está en la pantalla de entrar", "olvide" in botones)
    at.button(key="olvide").click().run()
    caso("«¿Olvidaste tu contraseña?» lleva a crear una cuenta nueva, sin explicaciones",
         "registro_correo" in [x.key for x in at.text_input] and at.radio(key="modo_acceso").value == "Crear cuenta"
         and not any("contraseña" in x.lower() and "recuper" in x.lower() for x in textos(at).split("\n")),
         at.radio(key="modo_acceso").value)
    casilla = at.checkbox(key="registro_acepto")
    caso("cuenta: la casilla de privacidad, en una línea, sin marcar y con el enlace a la política",
         casilla.value is False and casilla.label.startswith("Acepto la [política de privacidad](")
         and casilla.label.endswith("y que se guarde el texto de mi póliza y mis consultas, que pueden incluir datos de salud."),
         casilla.label)
    at.text_input(key="registro_correo").set_value("prueba@ejemplo.pe")
    at.text_input(key="registro_clave").set_value("clave-de-la-prueba")
    at.button(key="registro_crear").click().run()
    caso("cuenta: sin marcar la casilla no se crea y se dice por qué",
         any("Marca la casilla" in e.value for e in at.error) and guardado.filas(main_api.limites().motor)["usuarios"] == 0)
    at.checkbox(key="registro_acepto").check()
    at.button(key="registro_crear").click().run()
    t = "\n".join([textos(at)] + [m.value for m in at.markdown])
    caso("cuenta: creada, plan gratuito, con sus consultas del día", not at.exception and "<span>prueba</span><span>@ejemplo.pe</span>" in t
         and "Plan gratuito" in t and "Te quedan 3 de 3 consultas hoy." in t and "Pólizas guardadas: 0 de 1" in t, str(at.exception) or t[-400:])
    caso("cuenta gratis: el plan pagado no se vende en la web, se indica que está en la app de Android",
         "⭐ Plan pagado (S/ 3,99, pago único): disponible en la app de Android." in t and not [b for b in at.button if "pag" in (b.key or "")])
    caso("cuenta gratis: ¿Pagas doble? se muestra bloqueada", "¿Pagas doble?" in t and "🔒 Plan pagado, en la app de Android" in t
         and not [b for b in at.button if b.key == "comparar_boton"])
    import datetime as dt

    en_14 = (dt.date.today() + dt.timedelta(days=14)).strftime("%d/%m/%Y")
    caso("guardar: junto al botón, el indicador pequeño de la fecha de borrado",
         f'<span class="qmc-vence">se borra el {en_14}</span>' in "\n".join(m.value for m in at.markdown)
         and "volver a subir el PDF" not in textos(at))
    at.button(key="guardar_poliza").click().run()
    t = "\n".join([textos(at)] + [m.value for m in at.markdown] + [x.value for x in at.success])
    caso("guardar: confirmada en una línea con la fecha, y aparece como tarjeta en la cuenta con su indicador",
         not at.exception and f"Guardada · se borra el {en_14}" in t and t.count(f"se borra el {en_14}") >= 2
         and "Pólizas guardadas: 1 de 1" in t, str(at.exception) or t[-400:])
    caso("borrar: un botón por póliza y la zona de «borrar mi cuenta y todo», que pide contraseña y confirmación",
         any((b.key or "").startswith("borrar_p_g_") for b in at.button) and "confirmar_clave" in [x.key for x in at.text_input]
         and "no se puede deshacer" in at.checkbox(key="confirmar_seguro").label)
    boton = next(b for b in at.button if (b.key or "").startswith("borrar_p_g_"))
    boton.click().run()
    caso("borrar una póliza pide confirmación antes de hacerlo",
         any("Se borra con sus consultas" in w.body for w in at.warning)
         and guardado.filas(main_api.limites().motor)["polizas"] == 1)
    next(b for b in at.button if (b.key or "").startswith("borrar_si_g_")).click().run()
    caso("borrar una póliza: confirmada, ya no está", guardado.filas(main_api.limites().motor)["polizas"] == 0
         and "Pólizas guardadas: 0 de 1" in textos(at), guardado.filas(main_api.limites().motor))
    # Radiografía: con la cuenta gratis, una completa de muestra; después, bloqueada
    at.file_uploader(key="pdfs").set_value([]).run()
    at.radio(key="fuente").set_value("chubb_viajes_jetsmart").run()
    caso("radiografía con cuenta gratis: abierta, con el botón de la radiografía gratis",
         at.button(key="ver_radiografia").label == "Ver la radiografía · tu radiografía gratis", str([b.label for b in at.button])[:300])
    at.button(key="ver_radiografia").click().run()
    t = textos(at)
    caso("radiografía gratis: completa (qué cubre, exclusiones, deducibles y carencias) con el aviso de que es un resumen",
         not at.exception and all(x in t for x in ("Qué cubre y hasta cuánto", "Exclusiones principales", "Deducibles y copagos",
                                                    "Carencias y períodos de espera", "no la póliza entera")), str(at.exception))
    at.radio(key="fuente").set_value("pacifico_viajes").run()
    caso("radiografía de otra póliza: bloqueada, en la app de Android",
         any(e.label.startswith("🔒 Radiografía") for e in at.expander) and "🔒 Plan pagado, en la app de Android" in textos(at)
         and not [b for b in at.button if b.key == "ver_radiografia"])

    at.text_input(key="confirmar_clave").set_value("clave-de-la-prueba")
    at.button(key="borrar_cuenta").click().run()
    caso("borrar todo sin marcar la casilla: no borra nada y lo dice",
         any("marca la casilla" in e.value for e in at.error) and guardado.filas(main_api.limites().motor)["usuarios"] == 1)
    caso("la radiografía gratis quedó anotada en la base (no en el navegador)",
         guardado.filas(main_api.limites().motor)["usuarios"] == 1 and main_api.limites().motor.connect().execute(
             guardado.usuarios.select()).first().radiografia_gratis == "chubb_viajes_jetsmart")
    at.text_input(key="confirmar_clave").set_value("clave-de-la-prueba")
    at.checkbox(key="confirmar_seguro").check()
    at.button(key="borrar_cuenta").click().run()
    caso("borrar mi cuenta y todo: no queda ninguna fila y la pantalla vuelve a ofrecer crear una cuenta",
         not at.exception and all(v == 0 for v in guardado.filas(main_api.limites().motor).values())
         and any("se borraron" in x.value for x in at.success) and "google" in [b.key for b in at.button],
         (str(at.exception), guardado.filas(main_api.limites().motor)))

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
