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

    primera = md.strip().splitlines()[0] if md.strip() else ""
    if alertas:
        for a in alertas:
            check(a["texto"] in primera, "la alerta de la TRM está en la primera línea del reporte")
            check(a["texto"] in txt, "la alerta está en la versión de texto del correo")
    else:
        check("alerta" not in primera.lower(), "sin alerta: la primera línea no menciona alerta")
        check("Alerta:" not in pagina, "sin alerta: el correo no muestra el aviso rojo")

    try:
        rep = json.loads((d / "reporte.json").read_text(encoding="utf-8"))
        items = [it for s in rep.get("secciones", []) for it in s.get("items", [])]
        validos = {"oficial", "prensa", "sin_verificar"}
        sin_etiqueta = [it.get("nombre", "?") for it in items if it.get("verificacion") not in validos]
        check(not sin_etiqueta, "todas las cifras dicen si su fuente es oficial, vía prensa o sin verificar"
              + (f" (faltan: {', '.join(sin_etiqueta[:4])})" if sin_etiqueta else ""))
        trm_items = [it for it in items if it.get("nombre", "").upper().startswith("TRM")]
        if trm_items:
            check(all(it.get("verificacion") == "oficial" for it in trm_items),
                  "la TRM sale marcada como fuente oficial (viene de datos.gov.co)")
        check(not any(it.get("verificacion") == "oficial" and not it.get("fuente") for it in items),
              "ninguna cifra 'oficial' queda sin nombre de fuente")
        # la etiqueta debe estar respaldada por el registro de páginas que de verdad se abrieron
        reg_ruta = d / "fuentes_abiertas.json"
        registro = json.loads(reg_ruta.read_text(encoding="utf-8")) if reg_ruta.exists() else []
        leidas = {e.get("url") for e in registro if e.get("ok")}
        def norm(u):
            m = re.match(r"https?://(?:www\.)?([^/?#]+)([^?#]*)", u or "")
            return (m.group(1).lower() + m.group(2).rstrip("/")) if m else ""
        respaldadas = [it for it in items if it.get("verificacion") == "oficial" and norm(it.get("url")) in leidas]
        en_correo = pagina.count('color:#2b5f9e;">Fuente oficial</b>')
        check(en_correo == len(respaldadas),
              f"el correo muestra {en_correo} cifra(s) 'Fuente oficial' y el registro respalda {len(respaldadas)}")
        bloqueadas = [e["url"] for e in registro if not e.get("ok")]
        if bloqueadas:
            print("páginas oficiales que no se pudieron leer (informativo): " + ", ".join(sorted(set(bloqueadas))))
        print(f"páginas oficiales abiertas con éxito: {len(leidas)}")
    except json.JSONDecodeError:
        check(False, "reporte.json es JSON válido")

    check("baseline" not in md.lower() and "baseline" not in pagina.lower(), "no queda ninguna mención a baseline.json")
    check(not re.search(r"\b(nan|None|undefined)\b", txt), "la versión de texto no tiene nan/None/undefined")
    check("<script" not in pagina.lower(), "el correo no tiene scripts")
    check(not any(c in pagina for c in "▁▂▃▄▅▆▇█") and "<img" not in pagina.lower() and "<svg" not in pagina.lower(),
          "el correo no tiene gráficas")
    check("no encontrado" not in (pagina + txt).lower() and "no_encontrado" not in (pagina + txt).lower(),
          "el correo no dice 'No encontrado' en ninguna parte")
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
