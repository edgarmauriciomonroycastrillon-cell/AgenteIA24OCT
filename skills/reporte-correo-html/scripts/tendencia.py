#!/usr/bin/env python3
"""Historial de indicadores y cálculo de tendencias. Solo librería estándar.

El modelo NO calcula tendencias ni escribe en la memoria a mano: este script lo hace, porque
(1) las cuentas de un script son siempre iguales y (2) valida cada fila que entra a la memoria.

Subcomandos:
  sembrar-trm [--dias 30]
      Rellena la TRM de los últimos N días desde datos.gov.co (sin clave) y muestra la vigente.
  agregar --indicador K --valor V --fuente "Nombre" [--fecha AAAA-MM-DD]
  agregar --lote ruta.json
      Agrega o reemplaza filas (una por fecha e indicador). El lote es una lista de objetos
      con indicador, valor, fuente y, opcional, fecha.
  calcular [--salida ruta.json]
      Calcula por indicador: variación de 5 días hábiles, mínimo, máximo, racha y alertas.

El archivo es un CSV con las columnas fecha,indicador,valor,fuente y guarda los últimos 90 días.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HISTORIAL = os.environ.get("HISTORIAL_CSV", "/mnt/memory/colombia-indicadores/historial.csv")
CAMPOS = ["fecha", "indicador", "valor", "fuente"]
MAX_DIAS = 90  # cuánto historial se guarda
MIN_PUNTOS = 5  # con menos días hábiles no se calcula tendencia
VENTANA = 5  # días hábiles para la variación
SPARK_PUNTOS = 20  # cuántos días caben en la mini gráfica
BLOQUES = "▁▂▃▄▅▆▇█"
TRM_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"
TRM_FUENTE = "Superfinanciera (datos.gov.co)"

# etiqueta para mostrar, unidad y decimales. Un indicador nuevo también funciona (usa su clave).
INDICADORES = {
    "trm_usd": {"etiqueta": "TRM", "unidad": "COP", "dec": 2, "orden": 1},
    "euro_cop": {"etiqueta": "Euro", "unidad": "COP", "dec": 2, "orden": 2},
    "tasa_politica_banrep": {"etiqueta": "Tasa Banrep", "unidad": "%", "dec": 2, "orden": 3},
    "ipc_anual": {"etiqueta": "IPC anual", "unidad": "%", "dec": 2, "orden": 4},
    "ipp": {"etiqueta": "IPP mensual", "unidad": "%", "dec": 2, "orden": 5},
    "acpm_promedio_13_ciudades": {"etiqueta": "ACPM", "unidad": "COP", "dec": 0, "orden": 6},
    "gasolina_promedio_13_ciudades": {"etiqueta": "Gasolina", "unidad": "COP", "dec": 0, "orden": 7},
}
# cambio diario (%) que dispara una alerta
ALERTAS = {"trm_usd": 1.0}

RE_INDICADOR = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
RE_FUENTE = re.compile(r"^[\w .()/&+\-]{3,60}$")


def meta(clave: str) -> dict:
    return INDICADORES.get(clave, {"etiqueta": clave, "unidad": "", "dec": 2, "orden": 99})


def fmt_es(x: float, dec: int) -> str:
    """3158.43 -> '3.158,43' (formato colombiano)."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_valor(clave: str, v: float) -> str:
    m = meta(clave)
    return f"{fmt_es(v, m['dec'])} %" if m["unidad"] == "%" else f"${fmt_es(v, m['dec'])}"


# ---------- archivo ----------

def leer(ruta: str) -> dict:
    """Devuelve {(fecha, indicador): (valor, fuente)}. Ignora filas dañadas."""
    filas: dict = {}
    p = Path(ruta)
    if not p.exists():
        return filas
    with p.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                fecha = dt.date.fromisoformat(r["fecha"])
                valor = float(r["valor"])
                if not (RE_INDICADOR.match(r["indicador"]) and math.isfinite(valor)):
                    raise ValueError
                filas[(fecha, r["indicador"])] = (valor, r["fuente"])
            except (KeyError, ValueError, TypeError):
                print(f"aviso: ignoré una fila dañada del historial: {r}", file=sys.stderr)
    return filas


def escribir(ruta: str, filas: dict) -> None:
    p = Path(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CAMPOS)
        for (fecha, ind), (valor, fuente) in sorted(filas.items()):
            w.writerow([fecha.isoformat(), ind, format(valor, ".10g"), fuente])


def podar(filas: dict, hoy: dt.date) -> dict:
    limite = hoy - dt.timedelta(days=MAX_DIAS)
    return {k: v for k, v in filas.items() if k[0] >= limite}


def validar(fecha, indicador, valor, fuente, hoy: dt.date):
    """Devuelve (date, str, float, str) o lanza ValueError con un mensaje que explica el arreglo."""
    try:
        d = dt.date.fromisoformat(str(fecha))
    except ValueError:
        raise ValueError(f"fecha inválida '{fecha}': usa AAAA-MM-DD")
    if d > hoy + dt.timedelta(days=1):
        raise ValueError(f"la fecha {d} está en el futuro")
    ind = str(indicador)
    if not RE_INDICADOR.match(ind):
        raise ValueError(f"indicador '{ind}' inválido: minúsculas, números y guion bajo (ej. trm_usd)")
    try:
        v = float(str(valor).strip())
    except ValueError:
        raise ValueError(f"valor '{valor}' no es un número: usa punto decimal y sin separador de miles")
    if not math.isfinite(v) or abs(v) >= 1e9:
        raise ValueError(f"valor '{valor}' fuera de rango")
    src = str(fuente).strip()
    if not RE_FUENTE.match(src):
        raise ValueError("fuente inválida: 3 a 60 caracteres, solo letras, números, espacio y . ( ) / & + -")
    return d, ind, v, src


# ---------- TRM desde datos.gov.co ----------

def dias_habiles(desde: dt.date, hasta: dt.date) -> list:
    n = (hasta - desde).days
    return [desde + dt.timedelta(days=i) for i in range(n + 1) if (desde + dt.timedelta(days=i)).weekday() < 5]


def cubrir_trm(filas_api: list, fechas: list) -> dict:
    """Para cada fecha, la fila de la TRM que rige ese día: {fecha: (valor, desde, hasta)}.

    Cada fila vale DESDE una fecha HASTA otra. El fin de semana comparte valor: la fila del
    sábado 17 rige hasta el lunes 19. Por eso cada día hábil se llena con la fila que lo cubre.
    """
    parsed = []
    for r in filas_api:
        try:
            parsed.append((float(r["valor"]), dt.date.fromisoformat(r["vigenciadesde"][:10]),
                           dt.date.fromisoformat(r["vigenciahasta"][:10])))
        except (KeyError, ValueError, TypeError):
            continue
    out = {}
    for d in fechas:
        for valor, desde, hasta in parsed:
            if desde <= d <= hasta:
                out[d] = (valor, desde, hasta)
                break
    return out


def pedir_trm(inicio: dt.date) -> list:
    params = {
        "$where": f"vigenciahasta >= '{(inicio - dt.timedelta(days=7)).isoformat()}T00:00:00.000'",
        "$order": "vigenciadesde DESC",
        "$limit": "300",
    }
    req = urllib.request.Request(f"{TRM_URL}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": "analista-colombia/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_sembrar_trm(args, hoy: dt.date) -> int:
    inicio = hoy - dt.timedelta(days=args.dias - 1)
    try:
        api = pedir_trm(inicio)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"ERROR: no pude leer la TRM de datos.gov.co: {e}", file=sys.stderr)
        return 1
    cubierto = cubrir_trm(api, dias_habiles(inicio, hoy))
    if not cubierto:
        print("ERROR: datos.gov.co no devolvió ninguna TRM para el período", file=sys.stderr)
        return 1
    filas = leer(args.archivo)
    for d, (valor, _, _) in cubierto.items():
        filas[(d, "trm_usd")] = (valor, TRM_FUENTE)
    escribir(args.archivo, podar(filas, hoy))
    ultima = max(cubierto)
    valor, desde, hasta = cubierto[ultima]
    print(f"ok: {len(cubierto)} días de TRM en el historial. TRM vigente al {ultima}: "
          f"{valor} COP, rige del {desde} al {hasta} (Superfinanciera, datos.gov.co)")
    return 0


# ---------- agregar ----------

def cmd_agregar(args, hoy: dt.date) -> int:
    if args.lote:
        try:
            lote = json.loads(Path(args.lote).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: no pude leer el lote {args.lote}: {e}", file=sys.stderr)
            return 2
    else:
        if not (args.indicador and args.valor is not None and args.fuente):
            print("ERROR: usa --lote ruta.json, o --indicador, --valor y --fuente", file=sys.stderr)
            return 2
        lote = [{"indicador": args.indicador, "valor": args.valor, "fuente": args.fuente,
                 "fecha": args.fecha or hoy.isoformat()}]
    nuevas, errores = [], []
    for i, item in enumerate(lote):
        try:
            nuevas.append(validar(item.get("fecha", hoy.isoformat()), item.get("indicador", ""),
                                  item.get("valor", ""), item.get("fuente", ""), hoy))
        except (ValueError, AttributeError) as e:
            errores.append(f"fila {i}: {e}")
    if errores:  # todo o nada: una fila mala no deja la memoria a medias
        print("ERROR: no escribí nada. " + "; ".join(errores), file=sys.stderr)
        return 2
    filas = leer(args.archivo)
    for d, ind, v, src in nuevas:
        filas[(d, ind)] = (v, src)
    filas = podar(filas, hoy)
    escribir(args.archivo, filas)
    print(f"ok: {len(nuevas)} fila(s) escritas; el historial tiene {len(filas)} filas")
    return 0


# ---------- calcular ----------

def spark(valores: list) -> str:
    lo, hi = min(valores), max(valores)
    if hi - lo < 1e-12:
        return BLOQUES[3] * len(valores)
    return "".join(BLOQUES[min(7, int((v - lo) / (hi - lo) * 8))] for v in valores)


def signo(x: float, dec: int) -> int:
    r = round(x, dec)
    return 0 if r == 0 else (1 if r > 0 else -1)


def analizar(clave: str, puntos: list) -> dict:
    """puntos: [(fecha, valor)] de días hábiles, ordenados. Devuelve el análisis de un indicador."""
    m = meta(clave)
    n = len(puntos)
    fechas = [p[0] for p in puntos]
    vals = [p[1] for p in puntos]
    ultimo = {"fecha": fechas[-1].isoformat(), "valor": vals[-1], "texto": fmt_valor(clave, vals[-1])}
    base = {"clave": clave, "etiqueta": m["etiqueta"], "n_dias": n, "suficiente": n >= MIN_PUNTOS,
            "ultimo": ultimo, "variacion": None, "minimo": None, "maximo": None, "racha": None,
            "sparkline": "", "spark_dias": 0}
    if n < MIN_PUNTOS:
        base["frase"] = (f"{m['etiqueta']}: historial insuficiente ({n} de {MIN_PUNTOS} días hábiles). "
                         f"Último valor: {ultimo['texto']}.")
        return base

    pasos = min(VENTANA, n - 1)
    ref = vals[-1 - pasos]
    d = vals[-1] - ref
    pct = d / ref * 100 if ref else 0.0
    i_min, i_max = vals.index(min(vals)), vals.index(max(vals))
    cambios = [vals[i] - vals[i - 1] for i in range(1, n)]
    dir_ult = signo(cambios[-1], m["dec"])
    k = 0
    for c in reversed(cambios):
        if signo(c, m["dec"]) == dir_ult:
            k += 1
        else:
            break
    nombre_dir = {1: "sube", -1: "baja", 0: "igual"}[dir_ult]
    palabra = {1: "al alza", -1: "a la baja", 0: "sin cambio"}[dir_ult]

    es_tasa = m["unidad"] == "%"
    sd = signo(d, m["dec"])
    if sd == 0:
        cambio_txt = f"{m['etiqueta']} sin cambio en {pasos} días hábiles."
    else:
        verbo = "sube" if sd > 0 else "baja"
        if es_tasa:
            cambio_txt = f"{m['etiqueta']} {verbo} {fmt_es(abs(d), m['dec'])} pp en {pasos} días hábiles."
        else:
            cambio_txt = (f"{m['etiqueta']} {verbo} ${fmt_es(abs(d), m['dec'])} "
                          f"({'+' if pct > 0 else ''}{fmt_es(pct, 2)} %) en {pasos} días hábiles.")
    minimo = {"fecha": fechas[i_min].isoformat(), "valor": vals[i_min], "texto": fmt_valor(clave, vals[i_min])}
    maximo = {"fecha": fechas[i_max].isoformat(), "valor": vals[i_max], "texto": fmt_valor(clave, vals[i_max])}
    if sd == 0:
        corto = "sin cambio"
    elif es_tasa:
        corto = f"{'+' if d > 0 else '-'}{fmt_es(abs(d), m['dec'])} pp"
    else:
        corto = f"{'+' if pct > 0 else ''}{fmt_es(pct, 2)} %"
    base.update({
        "variacion": {"dias": pasos, "abs": round(d, 6), "pct": round(pct, 4),
                      "direccion": {1: "sube", -1: "baja", 0: "igual"}[sd], "texto_corto": corto},
        "minimo": minimo, "maximo": maximo,
        "racha": {"direccion": nombre_dir, "dias": k},
        "sparkline": spark(vals[-SPARK_PUNTOS:]), "spark_dias": len(vals[-SPARK_PUNTOS:]),
        "frase": (f"{cambio_txt} Rango del período: {minimo['texto']} a {maximo['texto']}. "
                  f"Racha: {k} {'día' if k == 1 else 'días'} {palabra}."),
    })
    return base


def alerta_de(clave: str, puntos: list, hoy: dt.date):
    umbral = ALERTAS.get(clave)
    if umbral is None or len(puntos) < 2:
        return None
    (f_prev, prev), (f_ult, ult) = puntos[-2], puntos[-1]
    if prev == 0 or (hoy - f_ult).days > 4:  # una alerta vieja no sirve
        return None
    pct = (ult - prev) / prev * 100
    if abs(pct) <= umbral:
        return None
    m = meta(clave)
    texto = (f"Alerta: {m['etiqueta']} {'sube' if pct > 0 else 'baja'} {fmt_es(abs(pct), 2)} % en un día "
             f"(de {fmt_valor(clave, prev)} a {fmt_valor(clave, ult)}).")
    return {"indicador": clave, "etiqueta": m["etiqueta"], "cambio_pct": round(pct, 4), "texto": texto}


def calcular(filas: dict, hoy: dt.date) -> dict:
    por_ind: dict = {}
    for (fecha, ind), (valor, _fuente) in filas.items():
        if fecha <= hoy and fecha.weekday() < 5:  # solo días hábiles ya ocurridos
            por_ind.setdefault(ind, []).append((fecha, valor))
    indicadores, alertas = [], []
    for clave in sorted(por_ind, key=lambda k: (meta(k)["orden"], k)):
        puntos = sorted(por_ind[clave])
        indicadores.append(analizar(clave, puntos))
        a = alerta_de(clave, puntos, hoy)
        if a:
            alertas.append(a)
    return {"hoy": hoy.isoformat(), "dias_guardados": MAX_DIAS, "minimo_dias": MIN_PUNTOS,
            "indicadores": indicadores, "alertas": alertas}


def cmd_calcular(args, hoy: dt.date) -> int:
    filas = leer(args.archivo)
    if not filas:
        print("ERROR: el historial está vacío; corre primero sembrar-trm y agregar", file=sys.stderr)
        return 1
    res = calcular(filas, hoy)
    texto = json.dumps(res, ensure_ascii=False, indent=2)
    if args.salida:
        Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(args.salida).write_text(texto, encoding="utf-8")
        resumen = "; ".join(f"{i['etiqueta']}: {i['n_dias']} días" + ("" if i["suficiente"] else " (insuficiente)")
                            for i in res["indicadores"])
        print(f"ok: {args.salida} · {resumen} · alertas: {len(res['alertas'])}")
    else:
        print(texto)
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivo", default=HISTORIAL, help="ruta del historial.csv")
    ap.add_argument("--hoy", help="AAAA-MM-DD; solo para pruebas")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sembrar-trm")
    s.add_argument("--dias", type=int, default=30)
    a = sub.add_parser("agregar")
    a.add_argument("--indicador")
    a.add_argument("--valor")
    a.add_argument("--fuente")
    a.add_argument("--fecha")
    a.add_argument("--lote")
    c = sub.add_parser("calcular")
    c.add_argument("--salida")
    args = ap.parse_args(argv)
    hoy = dt.date.fromisoformat(args.hoy) if args.hoy else dt.date.today()
    return {"sembrar-trm": cmd_sembrar_trm, "agregar": cmd_agregar, "calcular": cmd_calcular}[args.cmd](args, hoy)


if __name__ == "__main__":
    sys.exit(main())
