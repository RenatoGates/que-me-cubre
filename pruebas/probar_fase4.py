"""Prueba, sin red real y sin gasto, el backend de la Fase 4.

1. Seguridad: la cuenta B no puede leer, modificar ni borrar pólizas, consultas ni historial de
   la cuenta A en ningún endpoint, ni pidiendo por id directo. Al final, lo de A sigue intacto.
2. Caché: la misma pregunta sobre el mismo documento no se paga dos veces.
3. Langfuse recibe solo métricas: un servidor local hace de Langfuse, recibe lo que el SDK
   envía de verdad y se busca ahí el texto de la póliza, la pregunta, la respuesta y el correo.
4. Google Play Billing: verificación contra la API de Google (simulada aquí), una compra se
   acredita una sola vez, nunca de otra cuenta y nunca sin sesión.
5. Versionado: todo bajo /v1, con la versión mínima de la app.
6. Lo que va al cliente: ni proveedor, ni modelo, ni tokens, ni costo; los topes, sin números.

    python pruebas/probar_fase4.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import gzip
import json
import os
import re
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from comun import PRUEBAS, RAIZ, utf8

# --- Un "Langfuse" local que guarda todo lo que le llega ---
RECIBIDO: list[bytes] = []


class _Langfuse(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        cuerpo = self.rfile.read(int(self.headers.get("content-length") or 0))
        if self.headers.get("content-encoding") == "gzip":
            cuerpo = gzip.decompress(cuerpo)
        RECIBIDO.append(self.path.encode() + b"\n" + cuerpo)
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    do_PUT = do_POST

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):  # noqa: D102
        pass


with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    PUERTO = _s.getsockname()[1]
threading.Thread(target=HTTPServer(("127.0.0.1", PUERTO), _Langfuse).serve_forever, daemon=True).start()

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
                   "VOYAGE_API_KEY": "", "QMC_LIMITE_SUBIDAS_DIA": "50", "QMC_LIMITE_IP_DIA": "500", "QMC_LIMITE_DISPOSITIVO_DIA": "50",
                   "QMC_LIMITE_DISPOSITIVO_MES": "500", "QMC_LIMITE_GRATIS_DIA": "50", "QMC_LIMITE_GRATIS_MES": "500",
                   "LANGFUSE_PUBLIC_KEY": "pk-lf-prueba", "LANGFUSE_SECRET_KEY": "sk-lf-prueba",
                   "LANGFUSE_BASE_URL": f"http://127.0.0.1:{PUERTO}", "LANGFUSE_HOST": f"http://127.0.0.1:{PUERTO}",
                   "QMC_APP_VERSION_MINIMA": "7", "QMC_GOOGLE_CLIENT_IDS": "web.apps.googleusercontent.com,android.apps.googleusercontent.com"})

from fastapi.testclient import TestClient  # noqa: E402

from ai.llm import Proveedor, ProveedorNoDisponible  # noqa: E402
from ai.cache_normalizacion import texto_clave  # noqa: E402
from backend import guardado, main, observabilidad, pagos  # noqa: E402

os.environ["QMC_CLAVE_DATOS"] = guardado.nueva_llave()  # llave de prueba, solo de este proceso

FALLAS: list[str] = []
CHUBB, PACIFICO = "chubb_viajes_jetsmart", "pacifico_viajes"
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
CLAVE = "una-clave-de-prueba"


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


class ProveedorPrueba(Proveedor):
    """Pasa por el mismo envoltorio que Claude (el que mide y avisa a Langfuse), con las
    respuestas grabadas y sus tokens reales. Sus fallas traen texto de la póliza en el detalle,
    para comprobar que ese detalle no sale."""

    nombre, reutiliza_datos, aviso = "prueba", False, ""
    precios = (0.10, 0.50)  # los de Claude Haiku: el costo sale igual al medido
    modelos = {"normalizacion": "claude-haiku-5-5", "respuesta": "claude-haiku-5-5"}
    FUGA = "TEXTO-DE-POLIZA-EN-UN-ERROR Tarapoto"

    def __init__(self) -> None:  # noqa: D107
        self.grabadas = {}
        for ruta in sorted((PRUEBAS / "salidas").glob("P*.json")):
            r = json.loads(ruta.read_text(encoding="utf-8"))
            d = r["uso"]["detalle"][-1]
            self.grabadas[texto_clave(r["pregunta"])] = (r["modelo_crudo"], d["tokens_entrada"], d["tokens_salida"])

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):
        if tarea == "respuesta" and "<pregunta>" in usuario:
            pregunta = usuario.rsplit("<pregunta>", 1)[1].split("</pregunta>")[0].strip()
            if texto_clave(pregunta) in self.grabadas:
                crudo, t_in, t_out = self.grabadas[texto_clave(pregunta)]
                return json.dumps(crudo), t_in, t_out, 0
        raise ProveedorNoDisponible(self.FUGA)


def main_() -> int:
    utf8()
    prueba = ProveedorPrueba()
    main.proveedor = lambda: prueba
    pdf = (RAIZ / "data" / "polizas" / f"{CHUBB}.pdf").read_bytes()
    with TestClient(main.app) as api:
        motor = main.limites().motor
        caso("Langfuse se activa contra el servidor local", observabilidad.activo())
        dA, dB = {"X-Dispositivo": "dispositivo-de-a-01"}, {"X-Dispositivo": "dispositivo-de-b-01"}
        ta = api.post("/v1/cuenta/registro", json={"correo": "ana.secreta@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).json()["token"]
        tb = api.post("/v1/cuenta/registro", json={"correo": "beto@ejemplo.pe", "clave": CLAVE, "acepto_privacidad": True}).json()["token"]
        A, B = {"Authorization": f"Bearer {ta}"} | dA, {"Authorization": f"Bearer {tb}"} | dB
        id_a = main.cuentas.de_sesion(motor, ta)["usuario_id"]
        id_b = main.cuentas.de_sesion(motor, tb)["usuario_id"]

        # --- 5. Versionado ---
        app_ = api.get("/v1/app").json()
        caso("versionado: /v1/app da la versión mínima de la app y el cliente de Google del servidor",
             app_["version_minima"] == 7 and app_["google_server_client_id"] == "web.apps.googleusercontent.com" and app_["api"] == "v1", app_)
        rutas = list(main.app.openapi()["paths"])
        caso("versionado: la documentación expone solo rutas /v1, y las viejas siguen respondiendo (la web)",
             all(r.startswith("/v1/") for r in rutas) and api.get("/salud").status_code == 200 and api.get("/v1/salud").status_code == 200, rutas[:3])

        # --- Lo de A: una póliza subida (sA), la misma guardada (gA) y una consulta (cA) ---
        sA = api.post("/v1/polizas", files=[("archivos", ("mi_poliza.pdf", pdf, "application/pdf"))], headers=dA).json()["poliza_id"]
        gA = api.post(f"/v1/polizas/{sA}/guardar", headers=A).json()["poliza_id"]
        rA = api.post("/v1/preguntar", json={"poliza_id": gA, "pregunta": P01}, headers=A).json()
        cA = rA["consulta_id"]
        antes = guardado.filas(motor, id_a)
        historial_antes = api.get(f"/v1/polizas/{gA}/consultas", headers=A).json()

        # --- 1. B contra lo de A, endpoint por endpoint ---
        pagos.acreditar(motor, id_b, "compra-de-b")  # B pagado: así ¿Pagas doble? llega a revisar de quién es cada póliza
        intentos = {
            "GET /v1/polizas/{id} (guardada)": api.get(f"/v1/polizas/{gA}", headers=B),
            "GET /v1/polizas/{id} (subida)": api.get(f"/v1/polizas/{sA}", headers=B),
            "POST /v1/preguntar (guardada)": api.post("/v1/preguntar", json={"poliza_id": gA, "pregunta": P01}, headers=B),
            "POST /v1/preguntar (subida)": api.post("/v1/preguntar", json={"poliza_id": sA, "pregunta": P01}, headers=B),
            "POST /v1/pasos (guardada)": api.post("/v1/pasos", json={"poliza_id": gA, "situacion": "ayer"}, headers=B),
            "POST /v1/pasos (subida)": api.post("/v1/pasos", json={"poliza_id": sA, "situacion": "ayer"}, headers=B),
            "GET /v1/polizas/{id}/radiografia (guardada)": api.get(f"/v1/polizas/{gA}/radiografia", headers=B),
            "GET /v1/polizas/{id}/radiografia (subida)": api.get(f"/v1/polizas/{sA}/radiografia", headers=B),
            "GET /v1/polizas/{id}/clinicas (guardada)": api.get(f"/v1/polizas/{gA}/clinicas", headers=B),
            "GET /v1/polizas/{id}/clinicas (subida)": api.get(f"/v1/polizas/{sA}/clinicas", headers=B),
            "POST /v1/superposiciones": api.post("/v1/superposiciones", json={"poliza_ids": [gA, CHUBB]}, headers=B),
            "GET /v1/polizas/{id}/consultas": api.get(f"/v1/polizas/{gA}/consultas", headers=B),
            "POST /v1/polizas/{id}/guardar (subida de A)": api.post(f"/v1/polizas/{sA}/guardar", headers=B),
            "GET /v1/polizas/{id} (subida, sin cuenta desde otro dispositivo)": api.get(f"/v1/polizas/{sA}", headers=dB),
        }
        rechazos = {k: r.status_code for k, r in intentos.items() if r.status_code != 404}
        caso("B no puede leer ni usar las pólizas de A, ni por id directo: 404 en todos (como si no existieran)", not rechazos, rechazos)
        borrar_c = api.delete(f"/v1/consultas/{cA}", headers=B).json()
        borrar_g = api.delete(f"/v1/polizas/{gA}", headers=B).json()
        borrar_s = api.delete(f"/v1/polizas/{sA}", headers=B).json()
        caso("B no puede borrar una consulta, la póliza guardada ni la subida de A",
             borrar_c == borrar_g == borrar_s == {"borrada": False}, (borrar_c, borrar_g, borrar_s))
        cuenta_b = api.get("/v1/cuenta", headers=B).json()
        caso("GET /v1/cuenta de B no trae nada de A", cuenta_b["correo"] == "beto@ejemplo.pe" and cuenta_b["polizas"] == []
             and "ana.secreta" not in json.dumps(cuenta_b))
        api.delete("/v1/cuenta/sesion", headers=B)
        caso("B cierra su sesión y la de A sigue", api.get("/v1/cuenta", headers=A).status_code == 200)
        tb = api.post("/v1/cuenta/sesion", json={"correo": "beto@ejemplo.pe", "clave": CLAVE}).json()["token"]
        B = {"Authorization": f"Bearer {tb}"} | dB
        pagos._consultar_play = lambda producto, token: {"purchaseState": 0, "consumptionState": 0,
                                                         "obfuscatedExternalAccountId": pagos.id_ofuscado(id_a)}
        os.environ["QMC_PLAY_CUENTA_SERVICIO"] = "{}"
        r = api.post("/v1/cuenta/compra", json={"token_compra": "token-comprado-por-a"}, headers=B)
        caso("B no puede acreditarse una compra hecha por A (Play la ata a la cuenta de A)",
             r.status_code == 402 and pagos.saldo(motor, id_b) == 200, r.text[:150])
        r = api.request("DELETE", "/v1/cuenta", json={"clave": CLAVE}, headers=B)
        caso("B borra su cuenta y solo la suya", r.status_code == 200 and all(v == 0 for v in guardado.filas(motor, id_b).values()))
        despues = guardado.filas(motor, id_a)
        historial = api.get(f"/v1/polizas/{gA}/consultas", headers=A).json()
        caso("después de todo, lo de A sigue intacto: mismas filas, mismo historial, y A lo usa",
             despues == antes and historial == historial_antes and api.get(f"/v1/polizas/{sA}", headers=A).status_code == 200
             and api.get(f"/v1/polizas/{gA}", headers=A).status_code == 200, (antes, despues))
        endpoints = {re.sub(r" \(.*\)", "", k) for k in intentos} | {"DELETE /v1/consultas/{id}", "DELETE /v1/polizas/{id}", "GET /v1/cuenta",
                                                                      "DELETE /v1/cuenta/sesion", "POST /v1/cuenta/compra", "DELETE /v1/cuenta"}
        caso(f"seguridad: {len(endpoints)} endpoints cubiertos", len(endpoints) >= 14, sorted(endpoints))

        # --- 2. Caché ---
        main.respuestas = main.cache_respuestas.Cache()
        lim = main.limites()
        lim.olvidar(main.clave_dispositivo("cache-prueba-01"))
        d = {"X-Dispositivo": "cache-prueba-01"}
        gasto0 = lim.gasto_del_mes()["usd"]
        t0 = time.perf_counter()
        r1 = api.post("/v1/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=d).json()
        t1 = time.perf_counter()
        gasto1 = lim.gasto_del_mes()["usd"]
        r2 = api.post("/v1/preguntar", json={"poliza_id": CHUBB, "pregunta": "  me TORCI el dedo en tarapoto y fui a un centro medico me cubre los gastos  "},
                      headers=d).json()
        t2 = time.perf_counter()
        caso("caché: la misma pregunta (con otras mayúsculas, tildes y signos) no se paga dos veces",
             gasto1 - gasto0 > 0.001 and lim.gasto_del_mes()["usd"] == gasto1 and r2["cubre"] == r1["cubre"] and r2["citas"] == r1["citas"],
             (gasto0, gasto1, lim.gasto_del_mes()["usd"]))
        caso("caché: la respuesta repetida no descuenta del plan", r2["limites"]["restantes_hoy"] == r1["limites"]["restantes_hoy"])
        caso(f"caché: la repetida tarda {t2 - t1:.2f} s contra {t1 - t0:.2f} s", t2 - t1 < t1 - t0)
        r3 = api.post("/v1/preguntar", json={"poliza_id": PACIFICO, "pregunta": P01}, headers=d).json()
        caso("caché: la misma pregunta sobre otro documento no reusa la respuesta", r3["documento"] != r1["documento"])
        sB = api.post("/v1/polizas", files=[("archivos", ("otra.pdf", pdf, "application/pdf"))], headers=d).json()["poliza_id"]
        huella = api.get(f"/v1/polizas/{sB}", headers=d).json()["documento_sha256"]
        n0 = len(main.respuestas)
        main.respuestas.guardar("respuesta-de-prueba", {"modo": "completo"}, huella, 3600)  # una respuesta de ese documento
        api.delete(f"/v1/polizas/{sB}", headers=d)
        caso("caché: al borrar una póliza subida, sus respuestas salen de la memoria",
             len(main.respuestas) == n0 and main.respuestas.obtener("respuesta-de-prueba") is None)
        caso("caché: una respuesta sin veredicto (sin modelo) no se guarda para reusar",
             api.post("/v1/preguntar", json={"poliza_id": CHUBB, "pregunta": "¿Cubre el robo de mi celular en la playa?"}, headers=d).json()["modo"]
             == "solo_clausulas" and len(main.respuestas) == n0)

        # --- 6. Lo que va al cliente ---
        prohibido = re.compile(r"claude|haiku|anthropic|voyage|groq|gemini|tokens|costo_usd|\"proveedor\"|\"uso\"", re.I)
        salidas = {"preguntar": r1, "pasos": api.post("/v1/pasos", json={"poliza_id": CHUBB, "situacion": "me caí ayer"}, headers=d).json(),
                   "radiografia": api.get(f"/v1/polizas/{CHUBB}/radiografia", headers=A).json()}
        fugas = {k: prohibido.findall(json.dumps(v, ensure_ascii=False)) for k, v in salidas.items()}
        caso("al cliente no le llega proveedor, modelo, tokens ni costo", not any(fugas.values()), fugas)
        lim.olvidar(main.clave_dispositivo("tope-prueba-01"))
        os.environ["QMC_LIMITE_DISPOSITIVO_DIA"] = "1"
        main.respuestas = main.cache_respuestas.Cache()
        api.post("/v1/preguntar", json={"poliza_id": CHUBB, "pregunta": "¿Me cubren si pierdo el pasaporte?"}, headers={"X-Dispositivo": "tope-prueba-01"})
        r = api.post("/v1/preguntar", json={"poliza_id": CHUBB, "pregunta": "¿Y si pierdo la maleta?"}, headers={"X-Dispositivo": "tope-prueba-01"})
        mensaje = r.json()["detail"]["mensaje"]
        caso("al tope: «Alcanzaste el límite de consultas de tu plan. Se renuevan el DD/MM/AAAA.», sin otros números",
             re.fullmatch(r"Alcanzaste el límite de consultas de tu plan\. Se renuevan el \d\d/\d\d/\d{4}\.", mensaje) is not None, mensaje)
        os.environ["QMC_LIMITE_DISPOSITIVO_DIA"] = "50"

        # --- 4. Google Play Billing ---
        os.environ.pop("QMC_PLAY_CUENTA_SERVICIO")
        caso("sin cuenta de servicio de Play, comprar responde 501",
             api.post("/v1/cuenta/compra", json={"token_compra": "x"}, headers=A).status_code == 501)
        caso("sin sesión no se puede pagar (401)", api.post("/v1/cuenta/compra", json={"token_compra": "x"}).status_code == 401)
        os.environ["QMC_PLAY_CUENTA_SERVICIO"] = "{}"
        llamadas = []
        estado = {"purchaseState": 0, "consumptionState": 0, "obfuscatedExternalAccountId": pagos.id_ofuscado(id_a)}
        pagos._consultar_play = lambda producto, token: llamadas.append(token) or dict(estado)
        reconocidas = []
        pagos.reconocer = lambda producto, token: reconocidas.append(token)
        saldo0 = pagos.saldo(motor, id_a)
        r = api.post("/v1/cuenta/compra", json={"token_compra": "token-1"}, headers=A)
        caso("compra verificada contra Google: se acredita, se reconoce en Play y la cuenta queda pagada",
             r.status_code == 200 and r.json()["acreditada"] and pagos.saldo(motor, id_a) == saldo0 + 200 and reconocidas == ["token-1"]
             and r.json()["plan"] == "pagado", r.text[:200])
        r = api.post("/v1/cuenta/compra", json={"token_compra": "token-1"}, headers=A)
        caso("la app reenvía la misma compra (no alcanzó a consumirla): 200, sin acreditar dos veces ni volver a llamar a Play",
             r.status_code == 200 and pagos.saldo(motor, id_a) == saldo0 + 200 and llamadas == ["token-1"], (r.status_code, llamadas))
        for nombre_, cambio in (("sin pagar", {"purchaseState": 1}), ("ya consumida", {"consumptionState": 1}),
                                ("de otra cuenta", {"obfuscatedExternalAccountId": "otra"})):
            estado.update({"purchaseState": 0, "consumptionState": 0, "obfuscatedExternalAccountId": pagos.id_ofuscado(id_a)} | cambio)
            r = api.post("/v1/cuenta/compra", json={"token_compra": f"token-{nombre_}"}, headers=A)
            caso(f"compra {nombre_}: rechazada (402) y no suma", r.status_code == 402 and pagos.saldo(motor, id_a) == saldo0 + 200, r.text[:120])
        caso("Mi cuenta da el id ofuscado que la app pasa a Play (no el correo ni el id)",
             api.get("/v1/cuenta", headers=A).json()["id_compra"] == pagos.id_ofuscado(id_a) and id_a not in pagos.id_ofuscado(id_a))

        # --- 3. Langfuse: solo métricas ---
        api.post("/v1/preguntar", json={"poliza_id": gA, "pregunta": "Me robaron la mochila en Cusco, ¿me cubre?"}, headers=A)
        observabilidad.cerrar()
        time.sleep(1)
        enviado = b"\n".join(RECIBIDO)
        texto_poliza = [c["texto_literal"][:60] for c in rA.get("citas", [])] + [p["texto"][:60] for p in rA.get("pasajes", [])]
        buscar = {"pregunta": P01, "otra pregunta": "Me robaron la mochila", "respuesta": (rA.get("respuesta") or "")[:60],
                  "correo": "ana.secreta@ejemplo.pe", "detalle de un error": ProveedorPrueba.FUGA, "nombre del archivo": "mi_poliza.pdf",
                  **{f"texto de la póliza {i}": t for i, t in enumerate(texto_poliza[:6])}}
        filtrado = {k: v[:40] for k, v in buscar.items() if v and v.encode() in enviado}
        caso("Langfuse recibió trazas de verdad (preguntar, costo y tokens)",
             len(RECIBIDO) > 0 and b"preguntar" in enviado and b"claude-haiku" in enviado, f"{len(RECIBIDO)} envíos")
        caso(f"Langfuse no recibió ningún texto: {len(buscar)} textos buscados en {len(enviado)} bytes enviados", not filtrado, filtrado)
        caso("solo_metricas descarta frases, correos y textos largos y deja números y palabras clave",
             observabilidad.solo_metricas({"modo": "completo", "costo_usd": 0.001, "pregunta": "¿me cubre?", "correo": "a@b.pe",
                                           "cache": True, "veredicto": ["con_limites", "texto con espacios"]})
             == {"modo": "completo", "costo_usd": 0.001, "cache": True, "veredicto": ["con_limites"]})

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main_())
