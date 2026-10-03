"""Obtiene la tasa oficial del BCV y actualiza docs/latest.json y docs/history/<año>.json.

Fuente principal: https://www.bcv.org.ve/ (incluye la "fecha valor" publicada).
Respaldo:         https://ve.dolarapi.com (solo USD y EUR).

Solo usa la librería estándar de Python.

Códigos de salida:
  0  sin cambios o datos actualizados
  1  ninguna fuente respondió, o la tasa nueva no pasó la validación
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
HISTORIAL = DOCS / "history"
LATEST = DOCS / "latest.json"

# bcv.org.ve envía una cadena de certificados incompleta. Se añaden los
# intermedios correctos de Sectigo en lugar de desactivar la verificación.
INTERMEDIOS = Path(__file__).resolve().parent / "sectigo-intermedios.pem"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

# id del bloque en bcv.org.ve -> clave en el JSON
MONEDAS_BCV = {"dolar": "usd", "euro": "eur", "yuan": "cny", "lira": "try", "rublo": "rub"}

# Variación máxima aceptada frente a la última tasa publicada (FORCE=1 la omite)
VARIACION_MAXIMA = 0.20


def _get(url: str, ctx: ssl.SSLContext | None = None) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-VE,es;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30, context=ctx) as res:
        return res.read().decode("utf-8", errors="replace")


def _numero(texto: str) -> float:
    # "871,36890000" -> 871.3689 ; "1.234,56" -> 1234.56
    return float(texto.strip().replace(".", "").replace(",", "."))


def desde_bcv() -> dict:
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(INTERMEDIOS)
    html = _get("https://www.bcv.org.ve/", ctx)

    tasas = {}
    for id_html, clave in MONEDAS_BCV.items():
        m = re.search(rf'id="{id_html}"[\s\S]*?<strong[^>]*>\s*([\d.,]+)\s*</strong>', html, re.I)
        if m:
            tasas[clave] = _numero(m.group(1))

    fecha = re.search(r'Fecha Valor:\s*<span[^>]*content="(\d{4}-\d{2}-\d{2})', html, re.I)
    if "usd" not in tasas or not fecha:
        raise ValueError("No se encontró la tasa USD o la fecha valor en bcv.org.ve")

    return {"fecha_valor": fecha.group(1), **tasas, "fuente": "bcv.org.ve"}


def desde_dolarapi() -> dict:
    resultado = {}
    for clave, ruta in (("usd", "dolares"), ("eur", "euros")):
        data = json.loads(_get(f"https://ve.dolarapi.com/v1/{ruta}/oficial"))
        resultado[clave] = float(data["promedio"])
        resultado["fecha_valor"] = data["fechaActualizacion"][:10]
    return {**resultado, "fuente": "ve.dolarapi.com"}


def obtener() -> dict:
    errores = []
    for fuente in (desde_bcv, desde_dolarapi):
        try:
            return fuente()
        except Exception as e:  # noqa: BLE001 - se intenta la siguiente fuente
            errores.append(f"{fuente.__name__}: {e}")
    raise RuntimeError("Todas las fuentes fallaron:\n  " + "\n  ".join(errores))


def _leer(path: Path, defecto):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else defecto


def _escribir(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _historial_completo() -> dict:
    todo = {}
    for f in sorted(HISTORIAL.glob("*.json")):
        todo.update(_leer(f, {}))
    return todo


def main() -> int:
    try:
        nueva = obtener()
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1

    fecha = nueva["fecha_valor"]
    historial = _historial_completo()
    anteriores = sorted(f for f in historial if f < fecha)

    if anteriores and os.environ.get("FORCE") != "1":
        previa = historial[anteriores[-1]]["usd"]
        variacion = abs(nueva["usd"] - previa) / previa
        if variacion > VARIACION_MAXIMA:
            print(f"Rechazada: USD {nueva['usd']} varía {variacion:.0%} frente a {previa} "
                  f"({anteriores[-1]}). Ejecuta con FORCE=1 si es correcta.", file=sys.stderr)
            return 1

    entrada = {k: v for k, v in nueva.items() if k != "fecha_valor"}
    if historial.get(fecha) == entrada:
        print(f"Sin cambios ({fecha}: USD {nueva['usd']})")
        return 0

    HISTORIAL.mkdir(parents=True, exist_ok=True)
    archivo_anio = HISTORIAL / f"{fecha[:4]}.json"
    anio = _leer(archivo_anio, {})
    anio[fecha] = entrada
    _escribir(archivo_anio, dict(sorted(anio.items())))

    anterior = None
    if anteriores:
        anterior = {"fecha_valor": anteriores[-1], **historial[anteriores[-1]]}

    _escribir(LATEST, {
        **nueva,
        "anterior": anterior,
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    print(f"Actualizado {fecha}: USD {nueva['usd']} ({nueva['fuente']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
