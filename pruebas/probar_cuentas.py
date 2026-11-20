"""Prueba, sin red y sin gasto, la Fase 3: cuentas, pólizas guardadas, historial, plan pagado y borrados.

- Registro con correo: exige aceptar la política (la casilla no viene marcada); no existe ningún
  endpoint para recuperar la contraseña ni ningún texto que hable de eso.
- Google: el backend verifica el ID token (firma, emisor, cliente, vencimiento, correo
  verificado). Se prueba con una llave y un certificado creados aquí, en lugar de los de Google.
- Lo guardado va cifrado: ni la base ni la fila traen texto de la póliza ni de la pregunta.
- No se guarda el PDF: una póliza cargada de la base responde con citas verificadas por los
  dos lectores contra el texto de las páginas extraído al subirla.
- Topes por día y por mes, corta el primero: sin cuenta 3 y 10, gratis 3 y 20. La cuenta
  pagada usa una bolsa de 200 consultas por pago que no caduca (la radiografía descuenta 5),
  con un freno de 20 al día.
- Plan gratis: la póliza guardada tiene fecha de borrado a 14 días; adelantando el reloj, la
  limpieza no deja ninguna fila de ella.
- Plan pagado: un solo punto de cobro (backend/pagos.py); hoy el cobro responde 501.
  ¿Pagas doble? es del plan pagado; la radiografía también, con una gratis por cuenta.
- Borrar una consulta, una póliza y "mi cuenta y todo": no queda ninguna fila en ninguna tabla.

    python pruebas/probar_cuentas.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import datetime as dt
import os
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from comun import RAIZ, utf8

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
CLIENTE = "cliente-de-prueba.apps.googleusercontent.com"
os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
                   "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "VOYAGE_API_KEY": "", "QMC_LIMITE_SUBIDAS_DIA": "50",
                   "QMC_LIMITE_IP_DIA": "500", "QMC_GOOGLE_CLIENT_IDS": CLIENTE})

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from google.auth import crypt as google_crypt  # noqa: E402
from google.auth import jwt as google_jwt  # noqa: E402

from backend import acceso_google, almacen, cuentas, guardado, main, pagos  # noqa: E402
from backend.limites import uso_diario  # noqa: E402

os.environ["QMC_CLAVE_DATOS"] = guardado.nueva_llave()  # llave de prueba, solo de este proceso

from ai import radiografia  # noqa: E402
from ai.llm import ProveedorGrabado  # noqa: E402
from ai.respuesta import responder  # noqa: E402

FALLAS: list[str] = []
CHUBB, PACIFICO = "chubb_viajes_jetsmart", "pacifico_viajes"
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
CLAVE = "una-clave-de-prueba"


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def llave_y_certificado() -> tuple[str, str]:
    """Una llave RSA y su certificado, como los que publica Google para firmar sus ID tokens."""
    llave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "prueba")])
    ahora = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(llave.public_key())
            .serial_number(1).not_valid_before(ahora - timedelta(days=1)).not_valid_after(ahora + timedelta(days=1))
            .sign(llave, hashes.SHA256()))
    privada = llave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return privada.decode(), cert.public_bytes(serialization.Encoding.PEM).decode()


PRIVADA, CERTIFICADO = llave_y_certificado()
OTRA_PRIVADA, _ = llave_y_certificado()


def token_google(correo: str, sub: str, privada: str = PRIVADA, **cambios) -> str:
    ahora = int(time.time())
    datos = {"iss": "https://accounts.google.com", "aud": CLIENTE, "sub": sub, "email": correo, "email_verified": True,
             "iat": ahora, "exp": ahora + 3600} | cambios
    return google_jwt.encode(google_crypt.RSASigner.from_string(privada, key_id="k1"), datos).decode()


def almacen_otra() -> str:
    """Un condicionado de ejemplo cuya radiografía la cuenta todavía no tiene."""
    return "rimac_viajes"


def main_() -> int:
    utf8()
    pdf = (RAIZ / "data" / "polizas" / f"{CHUBB}.pdf").read_bytes()
    # Los certificados de Google, reemplazados por el de la prueba (sin red)
    acceso_google._cache.update(certificados={"k1": CERTIFICADO}, hasta=time.time() + 3600)
    with TestClient(main.app) as api:
        motor = main.limites().motor
        lim = main.limites()
        anonimo = {"X-Dispositivo": "cuentas-prueba-0001"}

        # --- Registro con correo y sesión ---
        avisos = api.get("/cuenta/avisos").json()
        caso("avisos: solo la casilla de consentimiento, con el enlace a la política; nada sobre recuperar la contraseña",
             avisos["consentimiento"] == "Acepto la política de privacidad y que se guarde el texto de mi póliza y mis consultas, "
                                        "que pueden incluir datos de salud."
             and avisos["politica_privacidad"].endswith("docs/privacidad.md") and set(avisos) == {
                 "consentimiento", "politica_privacidad", "disponible", "google_disponible"}, avisos)
        r = api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": CLAVE})
        caso("registro sin marcar la casilla de privacidad: se rechaza", r.status_code == 400 and r.json()["detail"]["codigo"] == "falta_consentimiento", r.text[:150])
        r = api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": "corta", "acepto_privacidad": True})
        caso("registro con contraseña corta: se rechaza", r.status_code == 400 and r.json()["detail"]["codigo"] == "clave_corta")
        r = api.post("/cuenta/registro", json={"correo": " Ana@Ejemplo.pe ", "clave": CLAVE, "acepto_privacidad": True})
        ana = {"Authorization": f"Bearer {r.json().get('token')}"}
        caso("registro: crea la cuenta gratis y abre sesión, sin avisos sobre la contraseña",
             r.status_code == 201 and r.json()["cuenta"]["plan"] == "gratis" and r.json()["cuenta"]["correo"] == "ana@ejemplo.pe"
             and "recuper" not in r.text, r.text[:200])
        caso("registro con un correo ya usado: 409", api.post("/cuenta/registro", json={"correo": "ana@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).status_code == 409)
        caso("entrar con otra contraseña: 401", api.post("/cuenta/sesion", json={"correo": "ana@ejemplo.pe", "clave": "otra-clave-mala"}).status_code == 401)
        caso("la contraseña no está en la base, solo su hash", CLAVE.encode() not in Path(_base.name).read_bytes())
        rutas = [x.path for x in main.app.routes]
        caso("no hay ningún endpoint para recuperar la contraseña", not any("recuper" in x or "restablec" in x or "reset" in x for x in rutas), rutas)
        fuentes = "".join((RAIZ / "backend" / n).read_text(encoding="utf-8") for n in ("main.py", "cuentas.py"))
        caso("ningún texto del backend explica que la contraseña no se recupera", "no podemos recuperarla" not in fuentes)
        caso("un token inventado no entra", api.get("/cuenta", headers={"Authorization": "Bearer inventado"}).status_code == 401)

        # --- Google ---
        caso("Google: el servidor lo ofrece cuando tiene el ID de cliente", api.get("/info").json()["google_disponible"] is True)
        antes = guardado.filas(motor)["usuarios"]
        r = api.post("/cuenta/google", json={"id_token": token_google("bea@gmail.com", "sub-bea")})
        caso("Google, cuenta nueva sin marcar la casilla: no se crea (400 falta_consentimiento)",
             r.status_code == 400 and r.json()["detail"]["codigo"] == "falta_consentimiento" and guardado.filas(motor)["usuarios"] == antes, r.text[:200])
        r = api.post("/cuenta/google", json={"id_token": token_google("Bea@Gmail.com", "sub-bea"), "acepto_privacidad": True})
        bea = {"Authorization": f"Bearer {r.json().get('token')}"}
        caso("Google, con la casilla: crea la cuenta gratis con el correo verificado por Google",
             r.status_code == 200 and r.json()["cuenta_nueva"] and r.json()["cuenta"]["correo"] == "bea@gmail.com"
             and r.json()["cuenta"]["acceso"] == "google" and r.json()["cuenta"]["plan"] == "gratis", r.text[:200])
        r = api.post("/cuenta/google", json={"id_token": token_google("bea@gmail.com", "sub-bea")})
        caso("Google, la segunda vez: entra a la misma cuenta sin pedir la casilla",
             r.status_code == 200 and not r.json()["cuenta_nueva"] and guardado.filas(motor)["usuarios"] == antes + 1, r.text[:200])
        malos = {"otro cliente": token_google("bea@gmail.com", "sub-bea", aud="otro.apps.googleusercontent.com"),
                 "vencido": token_google("bea@gmail.com", "sub-bea", iat=int(time.time()) - 7200, exp=int(time.time()) - 3600),
                 "otro emisor": token_google("bea@gmail.com", "sub-bea", iss="https://falso.example"),
                 "correo sin verificar": token_google("bea@gmail.com", "sub-bea", email_verified=False),
                 "firmado con otra llave": token_google("bea@gmail.com", "sub-bea", privada=OTRA_PRIVADA)}
        codigos = {k: api.post("/cuenta/google", json={"id_token": v, "acepto_privacidad": True}).status_code for k, v in malos.items()}
        caso("Google: rechaza el token de otro cliente, vencido, de otro emisor, sin correo verificado o con firma falsa",
             set(codigos.values()) == {401}, codigos)
        r = api.post("/cuenta/sesion", json={"correo": "bea@gmail.com", "clave": "cualquier-cosa"})
        caso("una cuenta de Google no entra con contraseña", r.status_code == 401 and r.json()["detail"]["codigo"] == "entra_con_google", r.text[:150])
        eva = api.post("/cuenta/registro", json={"correo": "eva@gmail.com", "clave": CLAVE, "acepto_privacidad": True}).json()
        r = api.post("/cuenta/google", json={"id_token": token_google("eva@gmail.com", "sub-eva")})
        caso("Google con el correo de una cuenta con contraseña: entra a esa cuenta, la contraseña deja de servir y la sesión vieja se cierra",
             r.status_code == 200 and not r.json()["cuenta_nueva"] and r.json()["cuenta"]["acceso"] == "google"
             and api.post("/cuenta/sesion", json={"correo": "eva@gmail.com", "clave": CLAVE}).status_code == 401
             and api.get("/cuenta", headers={"Authorization": f"Bearer {eva['token']}"}).status_code == 401, r.text[:200])
        eva = {"Authorization": f"Bearer {r.json()['token']}"}

        # --- Guardar: sin PDF, cifrado, con fecha de borrado a 14 días ---
        subida = api.post("/polizas", files=[("archivos", ("mi_poliza.pdf", pdf, "application/pdf"))], headers=anonimo).json()
        caso("guardar sin sesión: 401", api.post(f"/polizas/{subida['poliza_id']}/guardar").status_code == 401)
        r = api.post(f"/polizas/{subida['poliza_id']}/guardar", headers=ana)
        g = r.json()
        en_14 = (guardado.ahora() + timedelta(days=14)).astimezone(main.LIMA).strftime("%d/%m/%Y")
        caso("guardar (plan gratis): devuelve la fecha exacta de borrado, a 14 días",
             r.status_code == 201 and g["borrado_automatico"] == en_14 and g["aviso"] == f"Guardada · se borra el {en_14}", r.text[:200])
        caso("plan gratis: una sola póliza guardada (la segunda, 409)",
             api.post(f"/polizas/{subida['poliza_id']}/guardar", headers=ana).status_code == 409)
        cuenta = api.get("/cuenta", headers=ana).json()
        caso("mi cuenta: lista la póliza con su fecha de borrado",
             len(cuenta["polizas"]) == 1 and cuenta["polizas"][0]["borrado_automatico"] == en_14 and cuenta["polizas"][0]["paginas"] == 62, cuenta.get("polizas"))
        cruda = Path(_base.name).read_bytes()
        caso("en la base no hay texto de la póliza ni el PDF: el contenido va cifrado",
             b"COMPA" not in cruda and "Tarapoto".encode() not in cruda and b"%PDF" not in cruda and "Gastos Médicos".encode() not in cruda)

        # --- Responder desde lo guardado, sin el PDF ---
        api.delete(f"/polizas/{subida['poliza_id']}", headers=anonimo)  # ya no está en memoria
        main._guardadas.clear()
        r = api.post("/preguntar", json={"poliza_id": g["poliza_id"], "pregunta": P01}, headers=ana)
        caso("preguntar a la póliza guardada: responde (sin red, las cláusulas encontradas) y dice cuántas quedan hoy",
             r.status_code == 200 and len(r.json()["pasajes"]) > 0 and {k: r.json()["limites"][k] for k in (
                 "plan", "limite_dia", "restantes_hoy", "limite_mes", "restantes_mes", "saldo")} == {
                 "plan": "gratis", "limite_dia": 3, "restantes_hoy": 2, "limite_mes": 20, "restantes_mes": 19, "saldo": None},
             (r.status_code, r.text[:300]))
        caso("otra cuenta o nadie no puede usar esa póliza",
             api.post("/preguntar", json={"poliza_id": g["poliza_id"], "pregunta": P01}, headers=anonimo).status_code == 401
             and api.post("/preguntar", json={"poliza_id": g["poliza_id"], "pregunta": P01}, headers=bea).status_code == 404)

        # Con veredicto y citas: una póliza con vectores, guardada y vuelta a cargar sin PDF
        usuario_id = cuentas.de_sesion(motor, ana["Authorization"][7:])["usuario_id"]
        guardado.borrar_poliza(motor, usuario_id, g["poliza_id"])
        original = almacen.precargada(CHUBB)
        g2 = guardado.guardar_poliza(motor, usuario_id, original, 14)
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

        # --- Borrado automático a las 2 semanas: se adelanta el reloj ---
        antes = guardado.purgar(motor)
        caso("limpieza hoy: no borra nada (faltan 14 días)", antes["polizas"] == 0 and guardado.filas(motor, usuario_id)["polizas"] == 1, antes)
        casi = guardado.purgar(motor, guardado.ahora() + timedelta(days=13, hours=23))
        caso("limpieza a los 13 días y 23 horas: todavía no", casi["polizas"] == 0 and guardado.filas(motor, usuario_id)["polizas"] == 1)
        despues = guardado.purgar(motor, guardado.ahora() + timedelta(days=14, minutes=1))
        f = guardado.filas(motor, usuario_id)
        caso("limpieza a los 14 días: se va la póliza con todo su historial y no queda ninguna fila suya",
             despues["polizas"] == 1 and despues["consultas"] == 20 and f["polizas"] == 0 and f["consultas"] == 0 and f["usuarios"] == 1, (despues, f))
        g3 = guardado.guardar_poliza(motor, usuario_id, original, 14)
        with motor.begin() as c:  # vencida pero todavía sin limpiar
            c.execute(guardado.polizas.update().where(guardado.polizas.c.id == g3["poliza_id"]).values(borrar_el=guardado.ahora() - timedelta(minutes=1)))
        caso("una póliza vencida no se entrega aunque la limpieza no haya pasado todavía",
             guardado.cargar_poliza(motor, usuario_id, g3["poliza_id"]) is None and guardado.listar_polizas(motor, usuario_id) == [])
        guardado.purgar(motor)

        # --- Topes por día y por mes: corta el primero que se agote ---
        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers={"X-Dispositivo": "limite-prueba-0002"}).status_code for _ in range(4)]
        caso("sin cuenta: 3 consultas al día, la cuarta 429", codigos == [200, 200, 200, 429], codigos)

        def mes_usado(clave: str, n: int) -> None:  # como si ya hubiera hecho n consultas este mes, en otros días
            lim.tomar(clave, 10**6, lim.mes())
            with motor.begin() as c:
                c.execute(uso_diario.update().where(uso_diario.c.clave == clave, uso_diario.c.dia == lim.mes()).values(cuenta=n))

        clave = main.clave_dispositivo("limite-prueba-0003")
        mes_usado(clave, 9)
        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers={"X-Dispositivo": "limite-prueba-0003"}) for _ in range(2)]
        caso("sin cuenta: 10 al mes; con el día libre, el tope del mes corta y dice cuándo se reinicia",
             lim.limite_dispositivo_mes == 10 and [x.status_code for x in codigos] == [200, 429]
             and codigos[1].json()["detail"]["mensaje"] == f"Llegaste a tus 10 consultas de este mes. Se renuevan el {lim.renueva_el_mes()}."
             and lim.usadas(clave) == 1, [x.text[:150] for x in codigos])
        caso("el mes se reinicia el primer día del mes siguiente",
             dt.datetime.strptime(lim.renueva_el_mes(), "%d/%m/%Y").date().day == 1
             and dt.datetime.strptime(lim.renueva_el_mes(), "%d/%m/%Y").date() > dt.datetime.now(main.LIMA).date())
        registro = api.post("/cuenta/registro", json={"correo": "luisa@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).json()
        luisa_id = cuentas.de_sesion(motor, registro["token"])["usuario_id"]
        luisa = {"Authorization": f"Bearer {registro['token']}"}
        mes_usado("u:" + luisa_id, 19)
        r1 = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=luisa)
        r2 = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=luisa)
        caso("cuenta gratis: 20 al mes; la 20.ª pasa y la 21.ª se corta aunque quede cupo del día",
             lim.limite_gratis_mes == 20 and r1.status_code == 200 and r1.json()["limites"]["restantes_mes"] == 0
             and r1.json()["limites"]["restantes_hoy"] == 2 and r2.status_code == 429 and "de este mes" in r2.json()["detail"]["mensaje"],
             (r1.status_code, r2.text[:150]))
        api.request("DELETE", "/cuenta", json={"clave": CLAVE}, headers=luisa)
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana)
        caso("cuenta gratis: 3 al día (ya hizo 3 hoy) y la cuarta 429", lim.usadas("u:" + usuario_id) == 3 and r.status_code == 429
             and r.json()["detail"]["codigo"] == "limite_cuenta" and "Mañana se renuevan" in r.json()["detail"]["mensaje"], r.text[:200])
        ayer = (dt.datetime.now(main.LIMA) - timedelta(days=1)).strftime("%Y-%m-%d")
        lim.tomar("u:reinicio", 3, ayer), lim.tomar("u:reinicio", 3, ayer), lim.tomar("u:reinicio", 3, ayer)
        caso("el cupo se reinicia cada día (día de Lima): 3 usadas ayer no cuentan hoy",
             not lim.tomar("u:reinicio", 3, ayer) and lim.tomar("u:reinicio", 3))

        # --- Radiografía: una gratis por cuenta, guardada en la base ---
        r = api.get(f"/polizas/{CHUBB}/radiografia", headers=anonimo)
        caso("radiografía sin cuenta: bloqueada (403)", r.status_code == 403 and r.json()["detail"]["codigo"] == "radiografia_sin_cuenta", r.text[:150])
        r = api.get(f"/polizas/{CHUBB}/radiografia", headers=ana)
        completa = radiografia.guardada(CHUBB)
        caso("radiografía gratis: la primera sale completa, sin recortes",
             r.status_code == 200 and r.json()["acceso"] == "muestra" and r.json()["coberturas"] == completa["coberturas"]
             and r.json()["exclusiones"] == completa["exclusiones"] and r.json()["citas"] == completa["citas"], r.text[:200])
        caso("radiografía gratis: se puede volver a abrir la misma", api.get(f"/polizas/{CHUBB}/radiografia", headers=ana).status_code == 200)
        r = api.get(f"/polizas/{PACIFICO}/radiografia", headers=ana)
        caso("radiografía de otra póliza: bloqueada (403 plan_pagado)", r.status_code == 403 and r.json()["detail"]["codigo"] == "plan_pagado", r.text[:150])
        ana2 = {"Authorization": f"Bearer {api.post('/cuenta/sesion', json={'correo': 'ana@ejemplo.pe', 'clave': CLAVE}).json()['token']}"}
        f_ = api.get("/cuenta", headers=ana2).json()["funciones"]
        caso("la cuenta de la radiografía gratis vive en la base: en otra sesión sigue usada, y de qué póliza",
             f_["radiografia"] == "muestra_usada" and f_["radiografia_gratis_de"] == CHUBB
             and api.get(f"/polizas/{PACIFICO}/radiografia", headers=ana2).status_code == 403, f_)
        luis = {"Authorization": f"Bearer {api.post('/cuenta/registro', json={'correo': 'luis@ejemplo.pe', 'clave': CLAVE, 'acepto_privacidad': True}).json()['token']}"}
        propia = api.post("/polizas", files=[("archivos", ("de_luis.pdf", pdf, "application/pdf"))], headers=anonimo).json()
        r = api.get(f"/polizas/{propia['poliza_id']}/radiografia", headers=luis)
        caso("si la radiografía no sale (sin modelo), la gratis no se pierde",
             r.status_code == 200 and r.json()["modo"] != "radiografia"
             and api.get("/cuenta", headers=luis).json()["funciones"]["radiografia"] == "muestra_disponible", r.text[:200])

        # --- ¿Pagas doble?: del plan pagado ---
        for quien, cab in (("sin cuenta", anonimo), ("cuenta gratis", ana2)):
            r = api.post("/superposiciones", json={"poliza_ids": [CHUBB, PACIFICO]}, headers=cab)
            caso(f"¿Pagas doble? {quien}: bloqueada (403 plan_pagado)", r.status_code == 403 and r.json()["detail"]["codigo"] == "plan_pagado", r.text[:150])

        # --- Plan pagado: un solo punto de activación ---
        r = api.post("/cuenta/compra", json={"token_compra": "token-de-play"}, headers=ana2)
        caso("comprar hoy: 501, el cobro llega con Play Billing en la app de Android",
             r.status_code == 501 and r.json()["detail"]["codigo"] == "cobro_no_disponible", r.text[:150])
        caso("no hay activación a mano por comando",
             "__main__" not in (RAIZ / "backend" / "cuentas.py").read_text(encoding="utf-8")
             and "__main__" not in (RAIZ / "backend" / "pagos.py").read_text(encoding="utf-8"))
        caso("acreditar una compra verificada (lo que hará Play Billing): plan pagado con 200 consultas",
             pagos.acreditar(motor, usuario_id, "comprobante-1") and pagos.saldo(motor, usuario_id) == 200
             and api.get("/cuenta", headers=ana2).json()["saldo"] == 200)
        luis_id = cuentas.de_sesion(motor, luis["Authorization"][7:])["usuario_id"]
        caso("la misma compra no se acredita dos veces, ni a otra cuenta",
             not pagos.acreditar(motor, luis_id, "comprobante-1") and not pagos.acreditar(motor, usuario_id, "comprobante-1")
             and pagos.saldo(motor, usuario_id) == 200 and pagos.saldo(motor, luis_id) == 0)
        lim.olvidar("u:" + usuario_id)
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana2)
        caso("cuenta pagada: una consulta descuenta 1 de la bolsa y no del mes",
             r.status_code == 200 and r.json()["limites"]["saldo"] == 199 and r.json()["limites"]["limite_mes"] is None
             and lim.usadas("u:" + usuario_id, lim.mes()) == 0, r.text[:200])
        mes_usado("u:" + usuario_id, 10**6)
        caso("la bolsa no se mide por mes: un mes con 999 999 consultas no la frena",
             api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana2).json()["limites"]["saldo"] == 198)
        r = api.get(f"/polizas/{PACIFICO}/radiografia", headers=ana2)
        caso("cuenta pagada: una radiografía nueva descuenta 5", r.status_code == 200 and r.json()["consultas_descontadas"] == 5
             and pagos.saldo(motor, usuario_id) == 193, r.text[:200])
        r = api.get(f"/polizas/{PACIFICO}/radiografia", headers=ana2)
        caso("volver a abrir esa radiografía no descuenta, ni la gratis que ya tenía",
             r.json()["consultas_descontadas"] == 0 and api.get(f"/polizas/{CHUBB}/radiografia", headers=ana2).json()["consultas_descontadas"] == 0
             and pagos.saldo(motor, usuario_id) == 193)
        usadas = lim.usadas("u:" + usuario_id)
        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana2) for _ in range(21 - usadas)]
        caso("cuenta pagada: freno de 20 al día contra abuso, aunque quede saldo",
             lim.limite_pagado_dia == 20 and [x.status_code for x in codigos] == [200] * (20 - usadas) + [429]
             and "Mañana sigues con tu saldo" in codigos[-1].json()["detail"]["mensaje"] and pagos.saldo(motor, usuario_id) == 193 - (20 - usadas),
             [x.status_code for x in codigos])
        guardado.purgar(motor, guardado.ahora() + timedelta(days=300))
        caso("la bolsa no caduca: 300 días después sigue igual", pagos.saldo(motor, usuario_id) == 193 - (20 - usadas))
        ana2 = {"Authorization": f"Bearer {api.post('/cuenta/sesion', json={'correo': 'ana@ejemplo.pe', 'clave': CLAVE}).json()['token']}"}
        lim.olvidar("u:" + usuario_id)
        with motor.begin() as c:
            c.execute(guardado.usuarios.update().where(guardado.usuarios.c.id == usuario_id).values(saldo=0))
        cuenta = api.get("/cuenta", headers=ana2).json()
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=ana2)
        caso("bolsa agotada: Mi cuenta muestra saldo 0 y ofrece volver a comprar; consulta con los topes del plan gratis",
             cuenta["saldo"] == 0 and cuenta["volver_a_comprar"] and r.status_code == 200
             and (r.json()["limites"]["limite_dia"], r.json()["limites"]["limite_mes"], r.json()["limites"]["saldo"]) == (3, 20, 0), r.text[:300])
        r = api.get(f"/polizas/{almacen_otra()}/radiografia", headers=ana2)
        caso("bolsa agotada: una radiografía nueva no sale (403 saldo_insuficiente)",
             r.status_code == 403 and r.json()["detail"]["codigo"] == "saldo_insuficiente", r.text[:150])
        caso("volver a comprar suma otras 200", pagos.acreditar(motor, usuario_id, "comprobante-2") and pagos.saldo(motor, usuario_id) == 200
             and not api.get("/cuenta", headers=ana2).json()["volver_a_comprar"])
        lim.olvidar("u:" + usuario_id)
        r = api.post("/superposiciones", json={"poliza_ids": [CHUBB, PACIFICO]}, headers=ana2)
        caso("cuenta pagada: ¿Pagas doble? responde", r.status_code == 200 and r.json()["modo"] in ("superposicion", "sin_modelo", "sin_datos"), r.text[:200])
        caso("orden: sin cuenta < gratis < pagada, en consultas y en pólizas guardadas",
             lim.limite_dispositivo_mes < lim.limite_gratis_mes < pagos.consultas_por_pago()
             and 0 < pagos.polizas_permitidas("gratis") < pagos.polizas_permitidas("pagado"))
        guardadas = [guardado.guardar_poliza(motor, usuario_id, original, pagos.dias_de_guardado("pagado")) for _ in range(4)]
        nueva = api.post("/polizas", files=[("archivos", ("otra.pdf", pdf, "application/pdf"))], headers=anonimo).json()
        caso("plan pagado: 4 pólizas, sin fecha de borrado, y la quinta no entra",
             all(x["borrar_el"] is None for x in guardadas) and api.post(f"/polizas/{nueva['poliza_id']}/guardar", headers=ana2).status_code == 409)
        lejos = guardado.purgar(motor, guardado.ahora() + timedelta(days=300))
        caso("plan pagado: la limpieza no las borra ni 300 días después", lejos["polizas"] == 0 and guardado.filas(motor, usuario_id)["polizas"] == 4, lejos)
        caso("la sesión de 30 días sí venció con el reloj adelantado: hay que volver a entrar",
             lejos["sesiones"] >= 1 and api.get("/cuenta", headers=ana2).status_code == 401)
        ana = {"Authorization": f"Bearer {api.post('/cuenta/sesion', json={'correo': 'ana@ejemplo.pe', 'clave': CLAVE}).json()['token']}"}
        luis = {"Authorization": f"Bearer {api.post('/cuenta/sesion', json={'correo': 'luis@ejemplo.pe', 'clave': CLAVE}).json()['token']}"}
        bea, eva = ({"Authorization": f"Bearer {api.post('/cuenta/google', json={'id_token': token_google(c, s)}).json()['token']}"}
                    for c, s in (("bea@gmail.com", "sub-bea"), ("eva@gmail.com", "sub-eva")))

        # --- Borrar una póliza y borrar todo ---
        guardado.guardar_consulta(motor, usuario_id, guardadas[0]["poliza_id"], {"modo": "completo", "pregunta": "x"})
        r = api.delete(f"/polizas/{guardadas[0]['poliza_id']}", headers=ana)
        f = guardado.filas(motor, usuario_id)
        caso("borrar una póliza guardada se lleva su historial", r.json() == {"borrada": True} and f["polizas"] == 3 and f["consultas"] == 0, f)
        guardado.guardar_consulta(motor, usuario_id, guardadas[1]["poliza_id"], {"modo": "completo", "pregunta": "y"})
        r = api.request("DELETE", "/cuenta", json={"clave": "no-es-la-clave"}, headers=ana)
        caso("borrar la cuenta pide la contraseña: con una mala no borra nada", r.status_code == 401 and guardado.filas(motor, usuario_id)["polizas"] == 3)
        r = api.request("DELETE", "/cuenta", json={"clave": CLAVE}, headers=ana)
        f = guardado.filas(motor, usuario_id)
        caso("borrar mi cuenta y todo: no queda ninguna fila suya en ninguna tabla", r.status_code == 200 and all(v == 0 for v in f.values()), f)
        caso("ni sus contadores de uso", lim.usadas("u:" + usuario_id) == 0 and lim.usadas("u:" + usuario_id, lim.mes()) == 0)
        caso("y su sesión deja de servir", api.get("/cuenta", headers=ana).status_code == 401)
        bea_id = cuentas.de_sesion(motor, bea["Authorization"][7:])["usuario_id"]
        r = api.request("DELETE", "/cuenta", json={}, headers=bea)
        caso("una cuenta de Google se borra sin contraseña (con su sesión) y no queda ninguna fila suya",
             r.status_code == 200 and all(v == 0 for v in guardado.filas(motor, bea_id).values()), r.text[:150])
        for cab in (eva, luis):
            api.request("DELETE", "/cuenta", json={"clave": CLAVE}, headers=cab)
        total = guardado.filas(motor)
        caso("borradas todas las cuentas: no queda ninguna fila en ninguna tabla", all(v == 0 for v in total.values()), total)
        caso("ni queda un correo en la base", guardado.filas(motor)["usuarios"] == 0)

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
