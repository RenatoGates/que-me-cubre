"""Prueba, sin red y sin gasto, la Fase 3: cuentas, pólizas guardadas, historial y borrados.

- Registro: exige aceptar la política (la casilla no viene marcada), avisa que la contraseña
  no se puede recuperar y no existe ningún endpoint para recuperarla.
- Lo guardado va cifrado: ni la base ni la fila traen texto de la póliza ni de la pregunta.
- No se guarda el PDF: una póliza cargada de la base responde con citas verificadas por los
  dos lectores contra el texto de las páginas extraído al subirla.
- Límites ordenados: sin cuenta < cuenta gratis < cuenta pagada.
- Plan gratis: la póliza guardada tiene fecha de borrado a 7 días; adelantando el reloj, la
  limpieza no deja ninguna fila de ella.
- Borrar una consulta, una póliza y "mi cuenta y todo": no queda ninguna fila en ninguna tabla.

    python pruebas/probar_cuentas.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

from comun import RAIZ, utf8

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
                   "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "VOYAGE_API_KEY": "", "QMC_LIMITE_SUBIDAS_DIA": "50",
                   "QMC_LIMITE_IP_DIA": "500"})

from fastapi.testclient import TestClient  # noqa: E402

from backend import almacen, cuentas, guardado, main  # noqa: E402

os.environ["QMC_CLAVE_DATOS"] = guardado.nueva_llave()  # llave de prueba, solo de este proceso

from ai.llm import ProveedorGrabado  # noqa: E402
from ai.respuesta import responder  # noqa: E402

FALLAS: list[str] = []
CHUBB = "chubb_viajes_jetsmart"
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
CLAVE = "una-clave-de-prueba"


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def main_() -> int:
    utf8()
    pdf = (RAIZ / "data" / "polizas" / f"{CHUBB}.pdf").read_bytes()
    with TestClient(main.app) as api:
        motor = main.limites().motor
        anonimo = {"X-Dispositivo": "cuentas-prueba-0001"}

        # --- Registro y sesión ---
        avisos = api.get("/cuenta/avisos").json()
        caso("avisos: la contraseña no se recupera y la llave está en el servidor (el dueño podría leer)",
             avisos["clave"] == "Si olvidas tu contraseña no podemos recuperarla. Tendrías que registrarte de nuevo y volver a subir tu póliza."
             and "podría leerlo" in avisos["guardado"] and "No guardamos el archivo PDF" in avisos["guardado"])
        r = api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": CLAVE})
        caso("registro sin marcar la casilla de privacidad: se rechaza", r.status_code == 400 and r.json()["detail"]["codigo"] == "falta_consentimiento", r.text[:150])
        r = api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": "corta", "acepto_privacidad": True})
        caso("registro con contraseña corta: se rechaza", r.status_code == 400 and r.json()["detail"]["codigo"] == "clave_corta")
        r = api.post("/cuenta/registro", json={"correo": " Ana@Ejemplo.pe ", "clave": CLAVE, "acepto_privacidad": True})
        ana = {"Authorization": f"Bearer {r.json().get('token')}"}
        caso("registro: crea la cuenta gratis, abre sesión y repite el aviso de la contraseña",
             r.status_code == 201 and r.json()["cuenta"]["plan"] == "gratis" and r.json()["cuenta"]["correo"] == "ana@ejemplo.pe"
             and "no podemos recuperarla" in r.json()["aviso_clave"], r.text[:200])
        caso("registro con un correo ya usado: 409", api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).status_code == 409)
        caso("entrar con otra contraseña: 401", api.post("/cuenta/sesion", json={"correo": "ana@ejemplo.pe", "clave": "otra-clave-mala"}).status_code == 401)
        caso("la contraseña no está en la base, solo su hash", CLAVE.encode() not in Path(_base.name).read_bytes())
        rutas = [x.path for x in main.app.routes]
        caso("no hay ningún endpoint para recuperar la contraseña", not any("recuper" in x or "restablec" in x or "reset" in x for x in rutas), rutas)
        caso("un token inventado no entra", api.get("/cuenta", headers={"Authorization": "Bearer inventado"}).status_code == 401)

        # --- Guardar: sin PDF, cifrado, con fecha de borrado ---
        subida = api.post("/polizas", files=[("archivos", ("mi_poliza.pdf", pdf, "application/pdf"))], headers=anonimo).json()
        caso("guardar sin sesión: 401", api.post(f"/polizas/{subida['poliza_id']}/guardar").status_code == 401)
        r = api.post(f"/polizas/{subida['poliza_id']}/guardar", headers=ana)
        g = r.json()
        en_7 = (guardado.ahora() + timedelta(days=7)).astimezone(main.LIMA).strftime("%d/%m/%Y")
        caso("guardar (plan gratis): devuelve la fecha exacta de borrado, a 7 días, y dice que habrá que volver a subir",
             r.status_code == 201 and g["borrado_automatico"] == en_7 and en_7 in g["aviso"] and "volver a subir el PDF" in g["aviso"], r.text[:200])
        caso("plan gratis: una sola póliza guardada (la segunda, 409)",
             api.post(f"/polizas/{subida['poliza_id']}/guardar", headers=ana).status_code == 409)
        cuenta = api.get("/cuenta", headers=ana).json()
        caso("mi cuenta: lista la póliza con su fecha de borrado",
             len(cuenta["polizas"]) == 1 and cuenta["polizas"][0]["borrado_automatico"] == en_7 and cuenta["polizas"][0]["paginas"] == 62, cuenta.get("polizas"))
        cruda = Path(_base.name).read_bytes()
        caso("en la base no hay texto de la póliza ni el PDF: el contenido va cifrado",
             b"COMPA" not in cruda and "Tarapoto".encode() not in cruda and b"%PDF" not in cruda and "Gastos Médicos".encode() not in cruda)

        # --- Responder desde lo guardado, sin el PDF ---
        api.delete(f"/polizas/{subida['poliza_id']}", headers=anonimo)  # ya no está en memoria
        main._guardadas.clear()
        r = api.post("/preguntar", json={"poliza_id": g["poliza_id"], "pregunta": P01}, headers=ana)
        caso("preguntar a la póliza guardada: responde (sin red, las cláusulas encontradas) y trae lo que queda del mes",
             r.status_code == 200 and len(r.json()["pasajes"]) > 0 and r.json()["limites"]["plan"] == "gratis"
             and r.json()["limites"]["restantes_mes"] == 29, (r.status_code, r.text[:200]))
        caso("otra cuenta o nadie no puede usar esa póliza",
             api.post("/preguntar", json={"poliza_id": g["poliza_id"], "pregunta": P01}, headers=anonimo).status_code == 401)

        # Con veredicto y citas: una póliza con vectores, guardada y vuelta a cargar sin PDF
        usuario_id = cuentas.de_sesion(motor, ana["Authorization"][7:])["usuario_id"]
        guardado.borrar_poliza(motor, usuario_id, g["poliza_id"])
        original = almacen.precargada(CHUBB)
        g2 = guardado.guardar_poliza(motor, usuario_id, original, 7)
        cargada = guardado.cargar_poliza(motor, usuario_id, g2["poliza_id"])
        r = responder(P01, cargada, ProveedorGrabado())
        caso("la póliza cargada de la base no tiene PDF", cargada.pdf_bytes == b"" and len(cargada.paginas_leidas) == 2 * 62)
        caso("y aun así responde con veredicto y todas sus citas verificadas por los dos lectores",
             r["modo"] == "completo" and r["cubre"] == "con_limites" and len(r["citas"]) > 0
             and all(c["verificacion"]["pdfplumber"] and c["verificacion"]["pypdf"] for c in r["citas"]), (r["modo"], r.get("citas", [])[:1]))
        con_pdf = responder(P01, original, ProveedorGrabado())
        caso("con las mismas citas y páginas que la póliza con su PDF",
             [(c["texto_literal"], c["pagina"]) for c in r["citas"]] == [(c["texto_literal"], c["pagina"]) for c in con_pdf["citas"]])
        try:
            guardado.descifrar(guardado.cifrar({"a": 1}, "fila-1|ana"), "fila-1|otra")
            caso("un contenido cifrado no se descifra para otra cuenta", False)
        except Exception:  # noqa: BLE001
            caso("un contenido cifrado no se descifra para otra cuenta", True)

        # --- Historial ---
        main._guardadas.clear()
        ids = [api.post("/preguntar", json={"poliza_id": g2["poliza_id"], "pregunta": P01}, headers=ana).json().get("consulta_id") for _ in range(2)]
        h = api.get(f"/polizas/{g2['poliza_id']}/consultas", headers=ana).json()["consultas"]
        caso("historial: las consultas de la póliza guardada, con su respuesta y sus citas verificadas",
             len(h) == 2 and h[0]["pregunta"] == P01 and h[0]["cubre"] == "con_limites" and h[0]["citas"]
             and h[0]["citas"][0]["verificacion"]["pypdf"] and "pasajes" not in h[0], [x.get("modo") for x in h])
        caso("historial: se borra una consulta sola", api.delete(f"/consultas/{ids[0]}", headers=ana).json() == {"borrada": True}
             and len(api.get(f"/polizas/{g2['poliza_id']}/consultas", headers=ana).json()["consultas"]) == 1)
        for i in range(23):
            guardado.guardar_consulta(motor, usuario_id, g2["poliza_id"], {"modo": "completo", "pregunta": f"pregunta {i}"})
        caso("historial: solo quedan las últimas 20", guardado.filas(motor, usuario_id)["consultas"] == 20)
        caso("la pregunta guardada tampoco está en claro en la base", "Tarapoto".encode() not in Path(_base.name).read_bytes())
        sin_cuenta = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=anonimo).json()
        caso("sin cuenta no se guarda historial", "consulta_id" not in sin_cuenta and guardado.filas(motor)["consultas"] == 20)

        # --- Borrado automático: se adelanta el reloj ---
        antes = guardado.purgar(motor)
        caso("limpieza hoy: no borra nada (faltan 7 días)", antes["polizas"] == 0 and guardado.filas(motor, usuario_id)["polizas"] == 1, antes)
        casi = guardado.purgar(motor, guardado.ahora() + timedelta(days=6, hours=23))
        caso("limpieza a los 6 días y 23 horas: todavía no", casi["polizas"] == 0)
        despues = guardado.purgar(motor, guardado.ahora() + timedelta(days=7, minutes=1))
        f = guardado.filas(motor, usuario_id)
        caso("limpieza a los 7 días: se va la póliza con todo su historial y no queda ninguna fila suya",
             despues["polizas"] == 1 and despues["consultas"] == 20 and f["polizas"] == 0 and f["consultas"] == 0 and f["usuarios"] == 1, (despues, f))
        g3 = guardado.guardar_poliza(motor, usuario_id, original, 7)
        with motor.begin() as c:  # vencida pero todavía sin limpiar
            c.execute(guardado.polizas.update().where(guardado.polizas.c.id == g3["poliza_id"]).values(borrar_el=guardado.ahora() - timedelta(minutes=1)))
        caso("una póliza vencida no se entrega aunque la limpieza no haya pasado todavía",
             guardado.cargar_poliza(motor, usuario_id, g3["poliza_id"]) is None and guardado.listar_polizas(motor, usuario_id) == [])
        guardado.purgar(motor)

        # --- Límites ordenados ---
        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers={"X-Dispositivo": "limite-prueba-0002"}).status_code for _ in range(4)]
        caso("sin cuenta: 3 consultas al día", codigos == [200, 200, 200, 429], codigos)
        lim = main.limites()
        for _ in range(lim.limite_dispositivo_mes):
            lim.tomar("d:mensual", lim.limite_dispositivo_mes, lim.mes())
        caso("sin cuenta: 15 al mes", lim.limite_dispositivo_mes == 15 and not lim.tomar("d:mensual", 15, lim.mes()))
        usados = lim.usadas("u:" + usuario_id, lim.mes())
        for _ in range(30 - usados):
            lim.tomar("u:" + usuario_id, 30, lim.mes())
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana)
        caso("cuenta gratis: 30 al mes, y después 429", lim.limite_gratis_mes == 30 and r.status_code == 429 and r.json()["detail"]["codigo"] == "limite_cuenta", r.status_code)
        caso("activar el plan pagado a mano (punto de integración de la pasarela)", cuentas.cambiar_plan(motor, "ana@ejemplo.pe", "pagado"))
        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana).status_code for _ in range(11)]
        caso("cuenta pagada: 10 al día", codigos == [200] * 10 + [429], codigos)
        caso("orden: sin cuenta < gratis < pagada, en consultas al mes y en pólizas guardadas",
             lim.limite_dispositivo_mes < lim.limite_gratis_mes < lim.limite_pagado_dia * 30
             and 0 < cuentas.polizas_permitidas("gratis") < cuentas.polizas_permitidas("pagado"))
        guardadas = [guardado.guardar_poliza(motor, usuario_id, original, cuentas.dias_de_guardado("pagado")) for _ in range(4)]
        nueva = api.post("/polizas", files=[("archivos", ("otra.pdf", pdf, "application/pdf"))], headers=anonimo).json()
        caso("plan pagado: 4 pólizas, sin fecha de borrado, y la quinta no entra",
             all(x["borrar_el"] is None for x in guardadas) and api.post(f"/polizas/{nueva['poliza_id']}/guardar", headers=ana).status_code == 409)
        lejos = guardado.purgar(motor, guardado.ahora() + timedelta(days=300))
        caso("plan pagado: la limpieza no las borra ni 300 días después", lejos["polizas"] == 0 and guardado.filas(motor, usuario_id)["polizas"] == 4, lejos)
        caso("la sesión de 30 días sí venció con el reloj adelantado: hay que volver a entrar",
             lejos["sesiones"] >= 1 and api.get("/cuenta", headers=ana).status_code == 401)
        ana = {"Authorization": f"Bearer {api.post('/cuenta/sesion', json={'correo': 'ana@ejemplo.pe', 'clave': CLAVE}).json()['token']}"}

        # --- Borrar una póliza y borrar todo ---
        guardado.guardar_consulta(motor, usuario_id, guardadas[0]["poliza_id"], {"modo": "completo", "pregunta": "x"})
        r = api.delete(f"/polizas/{guardadas[0]['poliza_id']}", headers=ana)
        f = guardado.filas(motor, usuario_id)
        caso("borrar una póliza guardada se lleva su historial", r.json() == {"borrada": True} and f["polizas"] == 3 and f["consultas"] == 0, f)
        guardado.guardar_consulta(motor, usuario_id, guardadas[1]["poliza_id"], {"modo": "completo", "pregunta": "y"})
        r = api.request("DELETE", "/cuenta", json={"clave": "no-es-la-clave"}, headers=ana)
        caso("borrar la cuenta pide la contraseña: con una mala no borra nada", r.status_code == 401 and guardado.filas(motor, usuario_id)["polizas"] == 3)
        r = api.request("DELETE", "/cuenta", json={"clave": CLAVE}, headers=ana)
        f, total = guardado.filas(motor, usuario_id), guardado.filas(motor)
        caso("borrar mi cuenta y todo: no queda ninguna fila suya en ninguna tabla",
             r.status_code == 200 and all(v == 0 for v in f.values()) and all(v == 0 for v in total.values()), (f, total))
        caso("ni sus contadores de uso", lim.usadas("u:" + usuario_id) == 0 and lim.usadas("u:" + usuario_id, lim.mes()) == 0)
        caso("y su sesión deja de servir", api.get("/cuenta", headers=ana).status_code == 401)
        caso("ni queda su correo en la base", b"ana@ejemplo.pe" not in Path(_base.name).read_bytes() or guardado.filas(motor)["usuarios"] == 0)

        # --- Cuenta inactiva y sin llave ---
        t2 = api.post("/cuenta/registro", json={"correo": "luis@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).json()["token"]
        guardado.purgar(motor, guardado.ahora() + timedelta(days=370))
        caso("una cuenta sin entrar en 12 meses se borra entera", all(v == 0 for v in guardado.filas(motor).values()) and cuentas.de_sesion(motor, t2) is None)
        llave = os.environ.pop("QMC_CLAVE_DATOS")
        r = api.post("/cuenta/registro", json={"correo": "eva@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True})
        caso("sin la llave de cifrado configurada no se crean cuentas (503) y lo demás sigue igual",
             r.status_code == 503 and api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers={"X-Dispositivo": "sin-llave-0003"}).status_code == 200)
        os.environ["QMC_CLAVE_DATOS"] = llave

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main_())
