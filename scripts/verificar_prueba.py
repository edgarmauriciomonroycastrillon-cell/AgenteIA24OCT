#!/usr/bin/env python3
"""Revisa la salida de una prueba (carpeta tests/out/<agente>/<sesion>/) contra lo que se espera.

Uso:
  python scripts/verificar_prueba.py tests/out/analista-colombia/sesn_XXXX

Imprime una lista de comprobaciones con OK o FALLA y termina con código 1 si alguna falla.
Solo usa la librería estándar.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ARCHIVOS = ["reporte.md", "reporte.json", "reporte.html", "reporte.txt", "tendencias.json", "result.json"]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    d = Path(sys.argv[1])
    resultados: list[tuple[bool, str]] = []

    def check(ok: bool, texto: str) -> None:
        resultados.append((bool(ok), texto))

    for nombre in ARCHIVOS:
        check((d / nombre).exists(), f"existe {nombre}")
    if not all(ok for ok, _ in resultados):
        return mostrar(resultados)

    md = (d / "reporte.md").read_text(encoding="utf-8")
    pagina = (d / "reporte.html").read_text(encoding="utf-8")
    txt = (d / "reporte.txt").read_text(encoding="utf-8")
    res = json.loads((d / "result.json").read_text(encoding="utf-8"))
    try:
        tend = json.loads((d / "tendencias.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        check(False, "tendencias.json es JSON válido")
        return mostrar(resultados)
    check(True, "tendencias.json es JSON válido")

    check(res.get("stop_reason") == "end_turn", f"la sesión terminó sola (stop_reason={res.get('stop_reason')})")
    inds = tend.get("indicadores", [])
    alertas = tend.get("alertas", [])
    claves = {i["clave"] for i in inds}
    check("trm_usd" in claves, "la TRM está en el historial")
    trm = next((i for i in inds if i["clave"] == "trm_usd"), None)
    if trm:
        check(trm["suficiente"], f"la TRM tiene historial suficiente ({trm['n_dias']} días)")

    check("Tendencia de la semana" in pagina, "el correo tiene la sección 'Tendencia de la semana'")
    for i in inds:
        check(html.escape(i["frase"]) in pagina or i["frase"] in pagina,
              f"el correo trae la frase de {i['etiqueta']} sin cambios")
        check(i["frase"] in md, f"reporte.md copia la frase de {i['etiqueta']} palabra por palabra")
        if not i["suficiente"]:
            check("Historial insuficiente" in pagina and "historial insuficiente" in i["frase"],
                  f"{i['etiqueta']}: dice 'historial insuficiente' en vez de inventar tendencia")
            check(not i["sparkline"], f"{i['etiqueta']}: no dibuja gráfica con pocos datos")

    primera = md.strip().splitlines()[0] if md.strip() else ""
    if alertas:
        for a in alertas:
            check(a["texto"] in primera, "la alerta de la TRM está en la primera línea del reporte")
            check(a["texto"] in txt, "la alerta está en la versión de texto del correo")
    else:
        check("alerta" not in primera.lower(), "sin alerta: la primera línea no menciona alerta")
        check("Alerta:" not in pagina, "sin alerta: el correo no muestra el aviso rojo")

    check("baseline" not in md.lower() and "baseline" not in pagina.lower(), "no queda ninguna mención a baseline.json")
    check(not re.search(r"\b(nan|None|undefined)\b", txt), "la versión de texto no tiene nan/None/undefined")
    check("<script" not in pagina.lower(), "el correo no tiene scripts")
    check(len(pagina.encode("utf-8")) < 100_000, f"el HTML pesa menos de 100 KB ({len(pagina.encode('utf-8')) // 1000} KB)")
    print(f"costo de la prueba: USD {res.get('cost_usd')}")
    return mostrar(resultados)


def mostrar(resultados) -> int:
    for ok, texto in resultados:
        print(("OK     " if ok else "FALLA  ") + texto)
    fallas = sum(1 for ok, _ in resultados if not ok)
    print(f"\n{len(resultados) - fallas} de {len(resultados)} comprobaciones pasan")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
