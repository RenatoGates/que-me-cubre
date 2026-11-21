"""Genera docs/privacidad.html (y docs/index.html) desde docs/privacidad.md, con el diseño de la app.

GitHub Pages publica la carpeta docs/ de main en https://renatogates.github.io/que-me-cubre/.
La página es la URL de la política para Google Cloud (pantalla de consentimiento de OAuth) y para
la ficha de Google Play. El texto sale solo del .md: si la política cambia, se edita el .md y se
vuelve a correr esto.

    python pruebas/generar_privacidad.py          # escribe las páginas
    python pruebas/generar_privacidad.py --revisar # código 1 si las páginas no están al día con el .md
"""

from __future__ import annotations

import html
import re
import sys

from comun import RAIZ, utf8

DOCS = RAIZ / "docs"
URL = "https://renatogates.github.io/que-me-cubre/privacidad.html"


def en_linea(t: str) -> str:
    """Negritas, enlaces [texto](url) y <url> del markdown de la política."""
    t = html.escape(t, quote=False)
    t = re.sub(r"&lt;(https?://[^&]+)&gt;", r'<a href="\1">\1</a>', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t


def a_html(md: str) -> tuple[str, str]:
    """El subconjunto de markdown que usa la política: títulos, párrafos y listas de un nivel."""
    titulo, partes, parrafo, lista = "", [], [], []

    def cerrar() -> None:
        if parrafo:
            partes.append(f"<p>{en_linea(' '.join(parrafo))}</p>")
            parrafo.clear()
        if lista:
            partes.append("<ul>" + "".join(f"<li>{en_linea(i)}</li>" for i in lista) + "</ul>")
            lista.clear()

    for linea in md.splitlines():
        s = linea.strip()
        if not s:
            cerrar()
        elif s.startswith("# "):
            cerrar()
            titulo = s[2:]
        elif m := re.match(r"(#{2,3}) (.+)", s):
            cerrar()
            n = len(m.group(1))
            partes.append(f"<h{n}>{en_linea(m.group(2))}</h{n}>")
        elif s.startswith("- "):
            if parrafo:
                cerrar()
            lista.append(s[2:])
        elif lista and linea.startswith("  "):
            lista[-1] += " " + s
        else:
            parrafo.append(s)
    cerrar()
    return titulo, "\n".join(partes)


ESTILO = """
:root { --fondo:#FBF7F2; --tarjeta:#FFFFFF; --borde:#E8DFD4; --texto:#2E2620; --secundario:#7A6E62;
        --primario:#2D6BE5; --cita:#F3EDE4; }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--fondo); color: var(--texto);
       font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
header { background: var(--primario); color: #FFFFFF; padding: 28px 16px; }
header .ancho { display: flex; gap: 16px; align-items: center; }
header img { width: 64px; height: 64px; border-radius: 16px; background: #FFFFFF; flex: none; }
header h1 { margin: 0; font-size: 1.7rem; line-height: 1.2; }
header p { margin: 4px 0 0; font-weight: 600; }
.ancho { max-width: 760px; margin: 0 auto; }
main { padding: 24px 16px 48px; }
article { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 20px; padding: 8px 28px 24px; }
h2 { font-size: 1.3rem; margin: 28px 0 8px; }
h3 { font-size: 1.1rem; margin: 22px 0 6px; }
p, li { margin: 0 0 10px; }
ul { padding-left: 1.3rem; margin: 0 0 12px; }
a { color: var(--primario); font-weight: 600; text-underline-offset: 2px; overflow-wrap: anywhere; }
strong { font-weight: 700; }
article > p:first-of-type { background: var(--cita); border-left: 4px solid var(--primario); padding: 10px 14px; }
footer { color: var(--secundario); font-size: .95rem; text-align: center; padding: 0 16px 32px; }
@media (max-width: 520px) { article { padding: 4px 16px 16px; border-radius: 16px; } header h1 { font-size: 1.4rem; } }
"""


def pagina(titulo: str, cuerpo: str, descripcion: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(descripcion)}">
<link rel="icon" href="icono.png">
<style>{ESTILO}</style>
</head>
<body>
<header><div class="ancho"><img src="icono.png" alt=""><div><h1>{html.escape(titulo)}</h1>
<p>Tu póliza, en tus palabras, con la cláusula exacta.</p></div></div></header>
<main><div class="ancho"><article>
{cuerpo}
</article></div></main>
<footer>Generado desde <a href="https://github.com/RenatoGates/que-me-cubre/blob/main/docs/privacidad.md">docs/privacidad.md</a>.</footer>
</body>
</html>
"""


def generar() -> dict[str, str]:
    titulo, cuerpo = a_html((DOCS / "privacidad.md").read_text(encoding="utf-8"))
    inicio = (
        "<h2>¿Qué Cubre?</h2>\n"
        "<p>Una app para entender tu póliza de seguro: preguntas en tus palabras y te responde con la cláusula exacta "
        "de tu documento y su página.</p>\n"
        f'<ul><li><a href="privacidad.html">Política de privacidad</a></li>\n'
        '<li><a href="https://github.com/RenatoGates/que-me-cubre">Código y documentación</a></li></ul>'
    )
    return {
        "privacidad.html": pagina(titulo, cuerpo, "Qué datos guarda ¿Qué Cubre?, dónde, cuánto tiempo y cómo borrarlos."),
        "index.html": pagina("¿Qué Cubre?", inicio, "¿Qué Cubre?: entiende tu póliza de seguro con la cláusula exacta."),
        ".nojekyll": "",  # que Pages sirva los archivos tal cual, sin convertir los .md
    }


def main() -> int:
    utf8()
    paginas = generar()
    if "--revisar" in sys.argv:
        viejas = [n for n, t in paginas.items() if not (DOCS / n).exists() or (DOCS / n).read_text(encoding="utf-8") != t]
        print("al día" if not viejas else f"desactualizadas: {viejas}")
        return 1 if viejas else 0
    for nombre, texto in paginas.items():
        (DOCS / nombre).write_text(texto, encoding="utf-8", newline="\n")
    print(f"escrito docs/privacidad.html, docs/index.html y docs/.nojekyll → {URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
