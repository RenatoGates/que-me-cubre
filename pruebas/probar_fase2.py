"""Prueba, sin red y sin gasto, las funciones de la Fase 2.

- Fechas: leer la fecha del hecho del texto, comprobar que un número está en su cita y
  calcular la fecha límite (días calendario, hábiles y horas).
- Repregunta y varias preguntas (ai/consulta.py), con un modelo de mentira para el triage y
  las respuestas grabadas para lo demás.
- Pasos (ai/pasos.py): un plazo cuyo número no está en su cita se descarta; lo que no tiene
  cita válida, también.
- Radiografías versionadas: cada cita está literal en su página del PDF.
- Superposiciones: se descartan pares inventados o de la misma póliza.
- Los endpoints nuevos de la API.

    python pruebas/probar_fase2.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date

from comun import poliza, preguntas, utf8

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
                   "QMC_LIMITE_DISPOSITIVO_DIA": "4", "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "VOYAGE_API_KEY": ""})

from fastapi.testclient import TestClient  # noqa: E402

from ai import consulta, pasos, radiografia  # noqa: E402
from ai.fechas import fecha_en_texto, fecha_limite, numero_en_texto  # noqa: E402
from ai.llm import ProveedorGrabado, ProveedorNoDisponible, Uso  # noqa: E402
from ai.verificacion import verificar_en_pdf  # noqa: E402
from backend import almacen, main  # noqa: E402

FALLAS: list[str] = []
CHUBB = "chubb_viajes_jetsmart"
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
P03 = next(q["pregunta"] for q in preguntas() if q["id"] == "P03")
VAGA = "Me lesioné, ¿qué puedo hacer?"


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


class Falso:
    """Modelo de mentira: devuelve lo que se le indique por tarea; lo demás, las grabaciones."""

    nombre, reutiliza_datos, aviso = "falso", False, "modelo de prueba"
    modelos = {"normalizacion": "falso", "respuesta": "falso"}

    def __init__(self, **por_tarea) -> None:
        self.por_tarea, self.grabado, self.llamadas = por_tarea, ProveedorGrabado(), []

    def json(self, tarea, sistema, usuario, esquema):
        self.llamadas.append(tarea)
        if tarea in self.por_tarea:
            salida = self.por_tarea[tarea]
            return (salida(usuario) if callable(salida) else salida), Uso("falso", "falso", 100, 20, 0.1)
        if tarea == "respuesta":
            return self.grabado.json(tarea, sistema, usuario, esquema)
        raise ProveedorNoDisponible("sin respuesta de prueba")


def main_() -> int:
    utf8()
    ref = date(2026, 11, 15)  # domingo

    # --- Fechas ---
    lee = lambda t: (fecha_en_texto(t, ref) or (None,))[0]  # noqa: E731
    caso("fecha: 'ayer', 'anteayer' y 'hace 3 días'",
         (lee("me caí ayer"), lee("fue anteayer"), lee("hace 3 días me robaron"), lee("hace una semana")) ==
         (date(2026, 11, 14), date(2026, 11, 13), date(2026, 11, 12), date(2026, 11, 8)))
    caso("fecha: '12 de noviembre', '3/11/2026' y sin año no puede ser futura",
         (lee("el 12 de noviembre me accidenté"), lee("pasó el 3/11/2026"), lee("el 20 de diciembre")) ==
         (date(2026, 11, 12), date(2026, 11, 3), date(2025, 12, 20)))
    caso("fecha: sin fecha en el texto, nada; 'hoy' no se toma",
         lee("me torcí el dedo en Tarapoto") is None and lee("¿qué puedo hacer hoy?") is None)
    caso("número en la cita: en cifras, en palabras y no confunde 7 con 17 ni con 7.5",
         numero_en_texto(7, "dentro de los siete (7) días") and numero_en_texto(48, "cuarenta y ocho horas")
         and numero_en_texto(30, "plazo de 30 días") and not numero_en_texto(7, "dentro de los 17 días")
         and not numero_en_texto(3, "dentro de los treinta días"))
    c = fecha_limite(date(2026, 11, 14), 7, "dias", "calendario", ref)
    caso("fecha límite: 7 días calendario desde el 14 → 21, quedan 6", (c["fecha_limite"], c["dias_restantes"], c["vencido"], c["notas"]) == ("2026-11-21", 6, False, []))
    c = fecha_limite(date(2026, 11, 13), 3, "dias", "habiles", ref)  # viernes 13 → lun 16, mar 17, mié 18
    caso("fecha límite: 3 días hábiles desde el viernes 13 → miércoles 18, con la nota de feriados",
         c["fecha_limite"] == "2026-11-18" and "feriados" in c["notas"][0], c)
    c = fecha_limite(date(2026, 11, 1), 48, "horas", "no_dice", ref)
    caso("fecha límite: 48 horas → 2 días completos, y ya vencido", c["fecha_limite"] == "2026-11-03" and c["vencido"] and "horas" in c["notas"][0], c)
    c = fecha_limite(date(2026, 11, 14), 7, "dias", "no_dice", ref)
    caso("fecha límite: si la póliza no dice el tipo de día, cuenta calendario y lo avisa", c["fecha_limite"] == "2026-11-21" and "calendario" in c["notas"][0])

    # --- Repregunta y varias preguntas ---
    pol = poliza(CHUBB)
    vago = Falso(triage={"preguntas": [VAGA], "falta_informacion": True, "repreguntas": ["¿Qué pasó exactamente?", "¿Dónde ocurrió?", "¿Cuándo ocurrió?"]})
    r = consulta.atender(VAGA, pol, vago)
    caso("pregunta vaga: no busca ni responde, devuelve las repreguntas",
         r["modo"] == "aclaracion" and len(r["repreguntas"]) == 3 and vago.llamadas == ["triage"], (r["modo"], vago.llamadas))
    r = consulta.atender(VAGA, pol, vago, [{"pregunta": "¿Qué pasó exactamente?", "respuesta": "Me torcí el dedo ayer en Tarapoto"}])
    caso("con las aclaraciones ya no vuelve a repreguntar: busca con todo el texto",
         r["modo"] in ("completo", "solo_clausulas") and "Datos que agregó la persona" not in r["pregunta"] and len(r["pasajes"]) > 0, r["modo"])
    claro = Falso(triage={"preguntas": ["reescrita por el modelo"], "falta_informacion": False, "repreguntas": []})
    r = consulta.atender(P01, pol, claro)
    caso("una sola pregunta: se responde con el texto original, no con la reescritura del modelo",
         r["modo"] == "completo" and r["pregunta"] == P01 and len(r["citas"]) > 0 and r["uso"]["llamadas"] == 2, (r["modo"], r["uso"]["llamadas"]))
    caido = Falso()
    r = consulta.atender(P01, pol, caido)
    caso("si el triage falla, la consulta sigue como una sola pregunta", r["modo"] == "completo" and r["triage_error"] == "ProveedorNoDisponible", r.get("triage_error"))
    dos = Falso(triage={"preguntas": [P01, P03], "falta_informacion": False, "repreguntas": []})
    r = consulta.atender(f"{P01} {P03}", pol, dos)
    caso("dos preguntas: una respuesta por cada una, con sus propias citas",
         r["modo"] == "varias" and [x["pregunta"] for x in r["respuestas"]] == [P01, P03]
         and all(x["modo"] == "completo" and x["citas"] for x in r["respuestas"])
         and r["respuestas"][0]["citas"][0]["texto_literal"] != r["respuestas"][1]["citas"][0]["texto_literal"], r["modo"])
    r = consulta.atender(f"{P01} {P03}", pol, dos, permitir_otra=lambda: False)
    caso("dos preguntas sin cupo para la segunda: responde la primera y dice cuál quedó", len(r["respuestas"]) == 1 and r["sin_responder"] == [P03])
    r = consulta.atender("Me torcí el dedo ayer, ¿me cubre?", pol, caido)
    caso("la fecha del hecho escrita en la pregunta viaja en la respuesta", (r["fecha_hecho"] or {}).get("de") == "ayer", r.get("fecha_hecho"))

    # --- Pasos: validación por código ---
    pasajes = pasos.buscar(pol)
    plazo = re.compile(r"[^.]*?\(?(\d{1,3})\)?\s*d[íi]as[^.]*\.")
    hallado = next(((p, m) for p in pasajes for m in [plazo.search(p.trozo.texto)] if m), None)
    caso("pasos: la búsqueda trae un pasaje con un plazo en días", hallado is not None)
    if hallado:
        p, m = hallado
        n, frase = int(m.group(1)), m.group(0).strip()
        crudo = {"citas": [{"n": 1, "pasaje": p.id, "texto_literal": frase}, {"n": 2, "pasaje": p.id, "texto_literal": "Esta frase no está en la póliza."}],
                 "plazos": [{"para": "avisar", "cantidad": n, "unidad": "dias", "tipo_dias": "no_dice", "desde": "el hecho", "cita": 1},
                            {"para": "inventado", "cantidad": n + 1, "unidad": "dias", "tipo_dias": "no_dice", "desde": "", "cita": 1},
                            {"para": "sin cita", "cantidad": 5, "unidad": "dias", "tipo_dias": "no_dice", "desde": "", "cita": 2}],
                 "a_quien_avisar": [{"descripcion": "A la compañía", "citas": [1]}], "documentos": [{"descripcion": "Inventado", "citas": [2]}],
                 "pasos": [{"descripcion": "Sin cita", "citas": []}]}
        v = pasos.validar(crudo, pasajes, pol, date(2026, 11, 14))
        caso("pasos: se acepta el plazo cuyo número está escrito en su cita, con su fecha límite calculada",
             len(v["plazos"]) == 1 and v["plazos"][0]["cantidad"] == n and v["plazos"][0]["calculo"]["fecha_hecho"] == "2026-11-14"
             and v["citas"][0]["pagina"] >= 1, v["plazos"])
        motivos = sorted(d["motivo"] for d in v["descartes"] if d["tipo"] == "plazo")
        caso("pasos: se descartan el plazo con otro número y el que cita una frase que no existe",
             motivos == ["el número no está escrito en su cita", "sin cita válida"], motivos)
        caso("pasos: lo que no tiene cita válida no se muestra", len(v["a_quien_avisar"]) == 1 and v["documentos"] == [] and v["pasos"] == [])
        caso("pasos: sin fecha del hecho no se calcula nada", pasos.validar(crudo, pasajes, pol, None)["plazos"][0]["calculo"] is None)
    r = pasos.que_hacer(pol, "me accidenté ayer", proveedor=Falso())
    caso("pasos: si el modelo falla, muestra las cláusulas del aviso del siniestro y no inventa pasos",
         r["modo"] == "sin_modelo" and len(r["pasajes"]) > 0 and r["plazos"] == [] and r["fecha_hecho"] is not None, r["modo"])

    # --- Radiografías versionadas ---
    for doc_id in almacen.fuentes():
        rg = radiografia.guardada(doc_id)
        if rg is None:
            caso(f"radiografía de {doc_id}: existe", False)
            continue
        pdf = almacen.precargada(doc_id).pdf_bytes
        malas = [c["n"] for c in rg["citas"] if not any(verificar_en_pdf(pdf, [(c["pagina"], c["texto_literal"])]).values())
                 and not any(verificar_en_pdf(pdf, [(pg, c["texto_literal"])]).values() for pg in c["paginas"])]
        cruzan = sum(1 for c in rg["citas"] if len(c["paginas"]) > 1)
        usadas = {n for campo in ("coberturas", "exclusiones", "deducibles", "carencias") for x in rg[campo] for n in x["citas"]}
        caso(f"radiografía de {doc_id}: {len(rg['coberturas'])} coberturas y sus {len(rg['citas'])} citas están en su página del PDF",
             len(rg["coberturas"]) > 0 and len(malas) <= cruzan and usadas <= {c["n"] for c in rg["citas"]}, (malas, cruzan))

    # --- Superposiciones ---
    a, b = radiografia.guardada(CHUBB), radiografia.guardada("pacifico_viajes")
    falso = Falso(superposicion={"pares": [{"a": "A1", "b": "B1", "por_que": "Las dos cubren lo mismo."},
                                           {"a": "A1", "b": "A2", "por_que": "misma póliza"}, {"a": "A1", "b": "B99", "por_que": "inventada"},
                                           {"a": "B1", "b": "A1", "por_que": "repetida"}]})
    r = radiografia.superposiciones([("Chubb", a), ("Pacífico", b)], falso)
    caso("superposiciones: queda solo el par válido, con las citas verificadas de cada póliza",
         r["modo"] == "superposicion" and len(r["pares"]) == 1 and r["pares"][0]["a"]["poliza"] == "Chubb"
         and r["pares"][0]["a"]["citas"] and r["pares"][0]["b"]["citas"], r.get("pares"))
    caso("superposiciones: con una sola póliza con coberturas no compara", radiografia.superposiciones([("Chubb", a)], falso)["modo"] == "sin_datos")

    # --- API ---
    with TestClient(main.app) as api:
        d1 = {"X-Dispositivo": "fase2-prueba-0001"}
        r = api.get(f"/polizas/{CHUBB}/radiografia", headers=d1).json()
        caso("API: la radiografía de un condicionado de ejemplo sale de la versionada, con citas", r["modo"] == "radiografia" and len(r["citas"]) > 0)
        r = api.post("/pasos", json={"poliza_id": CHUBB, "situacion": "me accidenté ayer"}, headers=d1)
        caso("API: /pasos sin modelo responde 200 con las cláusulas, sin pasos inventados",
             r.status_code == 200 and r.json()["modo"] == "sin_modelo" and r.json()["limites"]["restantes_hoy"] == 3, r.text[:200])
        r = api.post("/pasos", json={"poliza_id": CHUBB, "fecha_hecho": "2999-01-01"}, headers=d1)
        caso("API: una fecha del hecho futura se rechaza", r.status_code == 400 and r.json()["detail"]["codigo"] == "fecha_futura")
        main.proveedor = lambda: vago
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": VAGA}, headers=d1).json()
        caso("API: una pregunta vaga devuelve repreguntas y no gasta una consulta del día",
             r["modo"] == "aclaracion" and r["limites"]["restantes_hoy"] == 3, (r["modo"], r["limites"]))
        main.proveedor = lambda: dos
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": f"{P01} {P03}"}, headers=d1).json()
        caso("API: dos preguntas gastan dos consultas y no llega la salida cruda del modelo",
             r["modo"] == "varias" and r["limites"]["restantes_hoy"] == 1 and all("modelo_crudo" not in x for x in r["respuestas"]), r.get("limites"))
        main.proveedor = lambda: falso
        r = api.post("/superposiciones", json={"poliza_ids": [CHUBB, "pacifico_viajes"]}, headers=d1)
        caso("API: /superposiciones compara dos condicionados", r.status_code == 200 and len(r.json()["pares"]) == 1, r.text[:200])
        r = api.post("/superposiciones", json={"poliza_ids": [CHUBB, CHUBB]}, headers=d1)
        caso("API: comparar una póliza consigo misma se rechaza", r.status_code == 400)

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main_())
