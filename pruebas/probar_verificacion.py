"""Pruebas sin LLM de la verificación: qué se acepta y, sobre todo, qué se sigue rechazando.

La garantía del producto es que cada cita está literal en el PDF y que el texto libre no
nombra nada que no esté citado. Estas pruebas fijan los bordes de esa garantía:

- la única tolerancia nueva es UN signo final de la cita (. : ; ,);
- una tilde, una palabra, una coma interna o dos oraciones pegadas siguen rechazándose;
- el texto libre pierde las oraciones que nombran artículos, códigos, documentos o
  cláusulas ausentes de las citas verificadas.

    python pruebas/probar_verificacion.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

from comun import poliza, utf8

from ai.recuperacion import Pasaje
from ai.respuesta import _validar
from ai.verificacion import recortar, ubicar_cita

FALLAS: list[str] = []


def caso(nombre: str, obtenido, esperado) -> None:
    ok = obtenido == esperado
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  (obtenido {obtenido!r}, esperado {esperado!r})"))
    if not ok:
        FALLAS.append(nombre)


def main() -> int:
    utf8()
    pol = poliza("chubb_viajes_jetsmart")
    art3 = next(t for t in pol.indice.trozos
                if "Gastos Médicos por Accidente" in t.seccion and t.articulo.startswith("Artículo 3") and t.parte == 1)
    texto = art3.texto
    frase = ("El reembolso o pago de gastos médicos y hospitalarios efectuados, en caso de Accidentes o "
             "Enfermedades de Carácter Súbito")
    assert frase in texto
    cierre = "en caso se encuentren en el mismo plan adquirido por el ASEGURADO"  # en el PDF sigue ":"
    assert cierre + ":" in texto

    print("Citas:")
    caso("cita exacta se acepta, sin signo ignorado", (r := ubicar_cita(texto, frase)) and r[2], None)
    caso("cita con '.' final donde el PDF tiene ':' se acepta", (r := ubicar_cita(texto, cierre + ".")) and r[2], ".")
    caso("…y se muestra sin el signo", r and r[1], cierre)
    caso("cita con ':' final correcto se acepta tal cual", (r := ubicar_cita(texto, cierre + ":")) and r[2], None)
    corte = "menos cualquier otro monto pagado al ASEGURADO por el mismo accidente o enfermedad bajo esta cobertura"
    assert corte + " y las siguientes" in texto  # en el PDF no hay coma ahí (caso real de P01)
    caso("cita que corta a mitad y cierra con ',' se acepta sin la coma", (r := ubicar_cita(texto, corte + ",")) and r[1:], (corte, ","))
    caso("una tilde distinta se rechaza", ubicar_cita(texto, frase.replace("médicos", "medicos")), None)
    caso("una palabra distinta se rechaza", ubicar_cita(texto, frase.replace("reembolso", "reintegro")), None)
    caso("una coma interna quitada se rechaza", ubicar_cita(texto, frase.replace("efectuados,", "efectuados")), None)
    caso("dos signos finales: solo se ignora uno, y se rechaza", ubicar_cita(texto, cierre + ".."), None)
    caso("'!' final no es tolerado", ubicar_cita(texto, cierre + "!"), None)
    otra = "a)Servicios prestados por el Médico."
    assert otra in texto
    caso("dos oraciones que en el PDF no van juntas se rechazan", ubicar_cita(texto, f"{frase}. {otra}"), None)

    print("Texto libre:")
    citas = [{"seccion": art3.seccion, "articulo": art3.articulo, "texto_literal":
              "hasta el límite establecido en las Condiciones Particulares y/o Certificado de Seguro para pólizas grupales"},
             {"seccion": art3.seccion, "articulo": art3.articulo, "texto_literal": "•B4 - Continuación de Tratamiento en País de Residencia."}]
    clausulas = pol.indice.vocabulario()[0]

    def queda(texto_libre: str) -> str:
        return recortar(texto_libre, citas, clausulas)[0]

    caso("documento citado se mantiene", queda("El monto está en tus Condiciones Particulares."),
         "El monto está en tus Condiciones Particulares.")
    caso("artículo de una cita se mantiene", queda("Según el Artículo 3°, tu póliza cubre gastos médicos."),
         "Según el Artículo 3°, tu póliza cubre gastos médicos.")
    caso("código citado se mantiene", queda("La cobertura B4 no está en este documento."), "La cobertura B4 no está en este documento.")
    caso("artículo no citado se recorta", queda("Tu póliza cubre gastos médicos. Revisa también el Artículo 5° de exclusiones."),
         "Tu póliza cubre gastos médicos.")
    caso("código no citado se recorta", queda("Además aplica la cobertura G2. Tu póliza cubre gastos médicos."),
         "Tu póliza cubre gastos médicos.")
    caso("documento no citado se recorta", queda("Pide el Endoso a tu aseguradora."), "")
    caso("cláusula no citada se recorta",
         queda("La cláusula de Gastos Odontológicos de Emergencia durante el Viaje no aplica. Tu póliza cubre gastos médicos."),
         "Tu póliza cubre gastos médicos.")
    caso("'Art. 3' no parte la oración", queda("Por el Art. 3 tu póliza cubre gastos médicos."), "Por el Art. 3 tu póliza cubre gastos médicos.")

    print("Validación completa (_validar) con un pasaje real:")
    pas = [Pasaje("P1", art3, 0.0, 1)]
    crudo = {
        "citas": [{"n": 1, "pasaje": "P1", "texto_literal": frase + ", hasta el límite establecido en las Condiciones Particulares y/o Certificado de Seguro para pólizas grupales."}],
        "condiciones": [{"descripcion": "El monto máximo está en tus Condiciones Particulares. Mira también el Artículo 7°.", "citas": [1]}],
        "exclusiones_aplicables": [],
        "podrian_aplicar": [{"descripcion": "Si tenías una condición preexistente, podría limitarse.", "citas": [1]},
                            {"descripcion": "Sin cita no entra.", "citas": [9]}],
        "no_incluido_en_documento": [
            {"nombre": "Condiciones Particulares", "por_que_importa": "Ahí está el monto.", "cita": 1},
            {"nombre": "Endoso de Viaje", "por_que_importa": "Inventado.", "cita": 1},
        ],
        "cubre": "con_limites",
        "respuesta": "Tu póliza cubre los gastos médicos por accidente. El límite está en tus Condiciones Particulares. La Solicitud de Seguro también lo dice.",
    }
    final, descartes = _validar(crudo, pas, pol)
    caso("la cita con su texto real se acepta", len(final["citas"]), 1)
    caso("la condición pierde la oración del Artículo 7°", [c["descripcion"] for c in final["condiciones"]],
         ["El monto máximo está en tus Condiciones Particulares."])
    caso("'podrían aplicar' con cita entra y sin cita no", [p["descripcion"] for p in final["podrian_aplicar"]],
         ["Si tenías una condición preexistente, podría limitarse."])
    caso("'no incluido' cuyo nombre no está en su cita se descarta", [m["nombre"] for m in final["no_incluido_en_documento"]],
         ["Condiciones Particulares"])
    caso("la respuesta pierde la oración que nombra la Solicitud de Seguro", final["respuesta"],
         "Tu póliza cubre los gastos médicos por accidente. El límite está en tus Condiciones Particulares.")
    caso("cada recorte queda registrado", sum(d["tipo"] == "texto" for d in descartes), 2)

    print("Bloque determinista de mencionadas pero ausentes:")
    from ai import cache_normalizacion
    from ai.recuperacion import recuperar_normalizada
    from ai.respuesta import mencionadas_ausentes

    def claves_ausentes(doc: str) -> set[str]:
        return {m.clave for lista in poliza(doc).indice.ausentes().values() for m in lista}

    chubb = claves_ausentes("chubb_viajes_jetsmart")
    caso("Chubb: B4 no tiene cláusula en el documento", "B4" in chubb, True)
    caso("Chubb: B1, B2, B3, C2 y G2 sí (por su título, aunque el nombre difiera un poco)",
         sorted(chubb & {"B1", "B2", "B3", "C2", "G2"}), [])
    caso("Chubb: Condiciones Particulares ausente, Condiciones Generales presente",
         ("condiciones particulares" in chubb, "condiciones generales" in chubb), (True, False))
    caso("Rimac: el Anexo A está en el PDF bajo su encabezado 'ANEXO A:'", "anexo a" in claves_ausentes("rimac_viajes"), False)
    caso("Rimac: 'Condicionado General' cuenta como Condiciones Generales",
         "condiciones generales" in claves_ausentes("rimac_viajes"), False)

    p02 = "Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?"
    norm = cache_normalizacion.buscar(p02, pol.sha256)
    assert norm, "P02 no está en la caché de normalizaciones"
    pasajes = recuperar_normalizada(pol.indice, p02, norm)
    bloque = mencionadas_ausentes(pasajes, pol)
    b4 = next((m for m in bloque if m["nombre"].startswith("B4")), None)
    caso("P02: los pasajes recuperados traen B4 al bloque", bool(b4), True)
    caso("P02: la mención es literal del pasaje y su página la calcula el código",
         b4 and (b4["mencion"], b4["paginas"]), ("B4 - Continuación de Tratamiento en País de Residencia", [16]))
    caso("P02: coberturas antes que documentos", bloque[0]["tipo"], "cobertura")
    caso("P02: el aviso", b4 and b4["mensaje"],
         "Tu póliza menciona «B4 - Continuación de Tratamiento en País de Residencia» pero no incluye su texto "
         "en este documento. Pídeselo a tu aseguradora.")
    p4 = next(p for p in pasajes if "B4" in p.trozo.texto)
    i = p4.trozo.texto.index("B4 - Continuación")
    crudo_b4 = {
        "citas": [{"n": 1, "pasaje": p4.id, "texto_literal": p4.trozo.texto[i : p4.trozo.texto.index(".", i)]}],
        "condiciones": [], "exclusiones_aplicables": [], "podrian_aplicar": [],
        "no_incluido_en_documento": [{"nombre": "B4 - Continuación de Tratamiento en País de Residencia",
                                      "por_que_importa": "No está.", "cita": 1}],
        "cubre": "con_limites", "respuesta": "Depende de la cobertura B4.",
    }
    final, descartes = _validar(crudo_b4, pasajes, pol, bloque)
    caso("el 'no incluido' del modelo que repite el bloque se descarta (no sale dos veces)",
         (final["no_incluido_en_documento"], [d["motivo"] for d in descartes if d["tipo"] == "no_incluido"]),
         ([], ["ya está en el bloque de mencionadas pero ausentes"]))
    caso("jerarquía: B4 arriba como cláusula ausente, las remisiones genéricas debajo",
         [(m["nombre"][:2], m["nivel"]) for m in bloque],
         [("B4", "clausula_ausente"), ("Co", "remision"), ("Ce", "remision")])

    print("Apertura del texto contra el veredicto:")

    def abre(respuesta: str, cubre: str) -> tuple[str, str]:
        f, d = _validar({**crudo, "cubre": cubre, "respuesta": respuesta}, pas, pol)
        return f["respuesta"], next((x["motivo"] for x in d if x["tipo"] == "texto" and "abre con" in x["motivo"]), "")

    caso("'Sí, …' con veredicto 'con límites' pierde esa oración (el intento 5 de P02)",
         abre("Sí, la radiografía está cubierta siempre que sea de urgencia. Si fuera de rutina, podría quedar excluida.", "con_limites"),
         ("Si fuera de rutina, podría quedar excluida.", "abre con «Sí» y el veredicto es «con_limites»"))
    caso("'Sí, …' con veredicto 'sí' se mantiene", abre("Sí, tu póliza cubre los gastos médicos.", "si"),
         ("Sí, tu póliza cubre los gastos médicos.", ""))
    caso("'No, …' con veredicto 'con límites' pierde esa oración",
         abre("No, eso no está cubierto. Solo cubre urgencias.", "con_limites"),
         ("Solo cubre urgencias.", "abre con «No» y el veredicto es «con_limites»"))
    caso("'No …' con veredicto 'no' se mantiene", abre("No cubre exámenes de rutina.", "no"), ("No cubre exámenes de rutina.", ""))
    caso("'Si la radiografía…' (condicional, sin tilde) no es un 'Sí'",
         abre("Si la radiografía es de urgencia, tu póliza la cubre.", "con_limites"),
         ("Si la radiografía es de urgencia, tu póliza la cubre.", ""))
    caso("'No obstante, …' no es un 'No'", abre("No obstante, tu póliza cubre urgencias.", "con_limites"),
         ("No obstante, tu póliza cubre urgencias.", ""))
    caso("una sola oración contradictoria deja el texto de respaldo",
         abre("Sí, está cubierta.", "con_limites")[0], "Revisa abajo las condiciones y las citas del documento.")

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())
