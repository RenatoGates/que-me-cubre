"""Establecimientos de salud registrados en SUSALUD (RENIPRESS), para el mapa de la app.

No usa el modelo: es un filtro por departamento y distrito sobre datos abiertos, así que
funciona aunque no haya cuota. Son establecimientos registrados en SUSALUD, no la red de
ninguna aseguradora. Sin GPS ni ubicación de la persona: ella elige la zona.

Fuente: datosabiertos.gob.pe, "Registro Nacional de Entidades Prestadoras de Servicios de
Salud - RENIPRESS" (SUSALUD), licencia ODC-BY (hay que citar la fuente: la app lo hace).
En el repositorio va una versión reducida: solo los establecimientos en estado ACTIVO y las
columnas que muestra la app. Las columnas NORTE y ESTE del original son latitud y longitud
en grados; las que caen fuera del Perú se dejan vacías (el establecimiento sale en la
lista, no en el mapa).

    python -m ai.renipress --csv RENIPRESS_30-10-2026.csv --corte 2026-10-30 \\
        --url https://www.datosabiertos.gob.pe/sites/default/files/RENIPRESS_30-10-2026.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "data" / "renipress"
RUTA = CARPETA / "renipress_activos.csv.gz"
FUENTE = CARPETA / "fuente.json"

COLUMNAS = {
    "COD_IPRESS": "codigo",
    "NOMBRE": "nombre",
    "INSTITUCION": "institucion",
    "CLASIFICACION": "clasificacion",
    "TIPO_ESTABLECIMIENTO": "tipo",
    "CATEGORIA": "categoria",
    "DEPARTAMENTO": "departamento",
    "PROVINCIA": "provincia",
    "DISTRITO": "distrito",
    "DIRECCION": "direccion",
    "TELEFONO": "telefono",
    "HORARIO": "horario",
    "NORTE": "lat",
    "ESTE": "lon",
}
# Caja del Perú, con margen: lo que cae fuera es un error de registro
LATITUD, LONGITUD = (-18.6, 0.2), (-81.6, -68.4)
_MINUSCULAS = {"de", "del", "la", "las", "los", "y", "e", "el"}


def preparar(csv: Path, corte: str, url: str) -> dict:
    datos = csv.read_bytes()
    df = pd.read_csv(csv, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    total = len(df)
    df = df[df["ESTADO"].str.strip() == "ACTIVO"][list(COLUMNAS)].rename(columns=COLUMNAS)
    for c in df.columns:
        df[c] = df[c].str.strip()
    for c, (lo, hi) in (("lat", LATITUD), ("lon", LONGITUD)):
        v = pd.to_numeric(df[c], errors="coerce")
        df[c] = v.where(v.between(lo, hi)).round(6)
    df.loc[df["lat"].isna() | df["lon"].isna(), ["lat", "lon"]] = None
    df["categoria"] = df["categoria"].replace({"0": "", "0.0": ""})
    df = df.sort_values(["departamento", "provincia", "distrito", "nombre"], kind="stable")
    CARPETA.mkdir(parents=True, exist_ok=True)
    df.to_csv(RUTA, index=False, encoding="utf-8", lineterminator="\n", compression={"method": "gzip", "mtime": 0})
    fuente = {
        "dataset": "Registro Nacional de Entidades Prestadoras de Servicios de Salud - RENIPRESS",
        "publica": "SUSALUD, en la Plataforma Nacional de Datos Abiertos (datosabiertos.gob.pe)",
        "pagina": "https://www.datosabiertos.gob.pe/dataset/registro-nacional-de-entidades-prestadoras-de-servicios-de-salud-renipress",
        "archivo_original": url,
        "sha256_original": hashlib.sha256(datos).hexdigest(),
        "corte": corte,
        "licencia": "ODC-BY (Open Data Commons Attribution)",
        "filas_original": total,
        "filas_activas": len(df),
        "con_coordenadas": int(df["lat"].notna().sum()),
    }
    FUENTE.write_text(json.dumps(fuente, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return fuente


def cargar() -> pd.DataFrame:
    df = pd.read_csv(RUTA, dtype=str, keep_default_na=False)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return df


def fuente() -> dict:
    return json.loads(FUENTE.read_text(encoding="utf-8"))


def nombre_propio(texto: str) -> str:
    """"SAN MARTIN" -> "San Martin", "MADRE DE DIOS" -> "Madre de Dios" (el registro no lleva tildes)."""
    palabras = texto.lower().split()
    return " ".join(p if i and p in _MINUSCULAS else p.capitalize() for i, p in enumerate(palabras))


def distritos(df: pd.DataFrame, departamento: str) -> list[tuple[str, str]]:
    """(provincia, distrito) del departamento, en orden. Un mismo nombre de distrito puede
    repetirse en dos provincias: por eso va siempre con su provincia."""
    d = df[df["departamento"] == departamento][["provincia", "distrito"]].drop_duplicates()
    return sorted(d.itertuples(index=False, name=None), key=lambda x: (x[1], x[0]))


def establecimientos(df: pd.DataFrame, departamento: str, provincia: str, distrito: str) -> pd.DataFrame:
    sel = df[(df["departamento"] == departamento) & (df["provincia"] == provincia) & (df["distrito"] == distrito)]
    return sel.sort_values(["tipo", "nombre"], key=lambda s: s.map(_orden_tipo) if s.name == "tipo" else s, kind="stable")


def _orden_tipo(tipo: str) -> int:
    """Primero los que tienen internamiento (hospitales y clínicas), después el resto."""
    return 0 if "CON INTERNAMIENTO" in tipo else 1 if "SIN INTERNAMIENTO" in tipo else 2


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Prepara la versión reducida de RENIPRESS para la app.")
    p.add_argument("--csv", type=Path, required=True, help="CSV original de datosabiertos.gob.pe")
    p.add_argument("--corte", required=True, help="fecha de corte del archivo (AAAA-MM-DD)")
    p.add_argument("--url", required=True, help="URL de descarga del archivo original")
    a = p.parse_args(argv)
    f = preparar(a.csv, a.corte, a.url)
    print(f"{f['filas_activas']} establecimientos activos de {f['filas_original']}; {f['con_coordenadas']} con coordenadas")
    print(f"{RUTA.relative_to(RAIZ)}: {RUTA.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
