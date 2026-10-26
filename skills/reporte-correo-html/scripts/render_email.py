#!/usr/bin/env python3
"""Render reporte.json into an email-safe HTML file and a plain-text twin.

Usage:
  python3 render_email.py reporte.json --tendencia tendencias.json --out /mnt/session/outputs

Writes <out>/reporte.html and <out>/reporte.txt. Standard library only.
All text in the JSON is plain text: this script escapes it, so never put HTML in it.

Design: a sober economic bulletin. White paper, graphite text, one steel-blue accent, thin rules and
tables instead of boxed cards, no charts. Tables and inline styles only, so Gmail and Outlook keep it.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import abrir_fuente  # mismo directorio: registro de páginas oficiales abiertas

FONDO = "#eef1f4"   # fuera del papel
PAPEL = "#ffffff"
TINTA = "#1f2933"   # grafito
AZUL = "#2b5f9e"    # único acento
AMBAR = "#b45309"   # alza, alerta, avisos
GRIS = "#6b7785"
REGLA = "#d5dbe1"
SERIF = "Georgia,'Times New Roman',serif"
SANS = "Helvetica,Arial,sans-serif"

TREND = {  # colores neutros a propósito: que un número suba no es bueno ni malo por sí solo
    "sube": ("&#9650;", AMBAR),
    "baja": ("&#9660;", AZUL),
    "igual": ("&#9632;", GRIS),
}
STATE = {
    "desactualizado": ("desactualizado", AMBAR),
}
VERIF = {
    "oficial": ("Fuente oficial", AZUL),
    "prensa": ("V&iacute;a prensa", GRIS),
    "sin_verificar": ("Sin verificar", AMBAR),
}
VERIF_TXT = {"oficial": "Fuente oficial", "prensa": "Vía prensa", "sin_verificar": "Sin verificar"}


def sin_faltantes(d: dict) -> dict:
    """Quita las cifras que no se encontraron. Una tarjeta vacía que dice 'No encontrado' no le sirve
    al lector: el nombre pasa a la lista 'Por confirmar hoy' y la sección vacía se omite."""
    d = json.loads(json.dumps(d))
    faltan = []
    for sec in d.get("secciones", []):
        quedan = []
        for it in sec.get("items", []):
            vacio = str(it.get("estado", "")).lower() == "no_encontrado" or                 str(it.get("valor", "")).strip().lower().rstrip(".") == "no encontrado"
            (faltan if vacio else quedan).append(it.get("nombre", "") if vacio else it)
        sec["items"] = quedan
    d["secciones"] = [sec for sec in d.get("secciones", []) if sec.get("items")]
    previos = [str(x) for x in d.get("limitaciones", [])]
    d["limitaciones"] = previos + [f for f in faltan if f and not any(f.lower() in p.lower() for p in previos)]
    return d


def ajustar_verificacion(d: dict, registro: list) -> tuple[dict, list]:
    """'Fuente oficial' solo si la página de la cifra está en el registro como leída.

    El modelo escribe la etiqueta, pero no puede darse a sí mismo la prueba: el registro lo escriben
    abrir_fuente.py y tendencia.py cuando abren de verdad la página. Si falta, la cifra baja a
    'sin_verificar'. Devuelve el reporte ajustado y los nombres de las cifras que bajaron.
    """
    d = json.loads(json.dumps(d))
    leidas = {e.get("url") for e in registro if e.get("ok")}
    bajaron = []
    for sec in d.get("secciones", []):
        for it in sec.get("items", []):
            if str(it.get("verificacion", "")).lower() != "oficial":
                continue
            url = it.get("url")
            if not url or abrir_fuente.normalizar(url) not in leidas:
                it["verificacion"] = "sin_verificar"
                bajaron.append(it.get("nombre", "?"))
    return d, bajaron


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def safe_url(url) -> str:
    url = str(url or "").strip()
    return url if url.startswith(("https://", "http://")) else ""


def trend_of(item: dict):
    return TREND.get(str(item.get("tendencia", "")).lower())


def etiqueta_chica(texto: str, color: str = GRIS) -> str:
    return (f'<span style="font-family:{SANS};font-size:11px;letter-spacing:.12em;text-transform:uppercase;'
            f'color:{color};">{texto}</span>')


def titulo_seccion(texto: str) -> str:
    return (
        f'<tr><td style="padding:26px 24px 2px 24px;"><div style="font-family:{SERIF};font-size:21px;color:{AZUL};'
        f'border-bottom:1px solid {REGLA};padding-bottom:5px;">{texto}</div></td></tr>'
    )


# ---------- resumen en una mirada ----------

def kpi_row(k: dict) -> str:
    t = trend_of(k)
    cambio = esc(k.get("cambio", ""))
    if cambio:
        color = t[1] if t else GRIS
        flecha = f"{t[0]} " if t else ""
        cambio_html = f'<span style="font-family:{SANS};font-size:13px;color:{color};">{flecha}{cambio}</span>'
    else:
        cambio_html = ""
    nota = esc(k.get("nota", ""))
    nota_html = f'<div style="font-family:{SANS};font-size:11px;color:{GRIS};margin-top:2px;">{nota}</div>' if nota else ""
    return (
        f'<tr><td style="padding:9px 0;border-bottom:1px solid {REGLA};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="34%" valign="top">{etiqueta_chica(esc(k.get("etiqueta", "")))}{nota_html}</td>'
        f'<td width="30%" valign="top" align="right" style="font-family:{SERIF};font-size:19px;color:{TINTA};">{esc(k.get("valor", ""))}</td>'
        f'<td width="36%" valign="top" align="right" style="padding-left:6px;">{cambio_html}</td>'
        f"</tr></table></td></tr>"
    )


def kpi_block(kpis: list) -> str:
    kpis = kpis[:4]
    if not kpis:
        return ""
    rows = "".join(kpi_row(k) for k in kpis)
    return (
        titulo_seccion("En una mirada")
        + f'<tr><td style="padding:0 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table></td></tr>'
    )


# ---------- secciones e indicadores ----------

def item_block(it: dict) -> str:
    parts = []
    estado = STATE.get(str(it.get("estado", "")).lower())
    marca = ""
    if estado:
        marca = (f' <span style="font-family:{SANS};font-size:10px;font-weight:normal;letter-spacing:.1em;'
                 f'text-transform:uppercase;color:{estado[1]};border:1px solid {estado[1]};padding:1px 5px;'
                 f'white-space:nowrap;">{estado[0]}</span>')
    parts.append(f'<div style="font-family:{SANS};font-size:14px;font-weight:bold;color:{TINTA};">{esc(it.get("nombre", ""))}{marca}</div>')
    valor = esc(it.get("valor", ""))
    if valor:
        parts.append(f'<div style="font-family:{SERIF};font-size:21px;color:{TINTA};margin-top:3px;">{valor}</div>')
    cambio = esc(it.get("cambio", ""))
    t = trend_of(it)
    if cambio:
        color = t[1] if t else GRIS
        flecha = f"{t[0]} " if t else ""
        parts.append(f'<div style="font-family:{SANS};font-size:13px;color:{color};margin-top:2px;">{flecha}{cambio}</div>')
    detalle = esc(it.get("detalle", ""))
    if detalle:
        parts.append(f'<div style="font-family:{SERIF};font-size:15px;color:{TINTA};margin-top:8px;line-height:1.55;">{detalle}</div>')
    efecto = esc(it.get("efecto", ""))
    if efecto:
        parts.append(
            f'<div style="font-family:{SERIF};font-size:15px;color:{TINTA};margin-top:8px;line-height:1.55;'
            f'border-left:2px solid {AZUL};padding-left:10px;"><i>Impacto.</i> {efecto}</div>'
        )
    fuente = esc(it.get("fuente", ""))
    fecha = esc(it.get("fecha", ""))
    url = safe_url(it.get("url"))
    verif = VERIF.get(str(it.get("verificacion", "")).lower())
    if fuente or fecha or verif:
        src = fuente
        if url and fuente:
            src = f'<a href="{esc(url)}" style="color:{GRIS};text-decoration:underline;">{fuente}</a>'
        bits = []
        if verif:
            bits.append(f'<b style="color:{verif[1]};">{verif[0]}</b>')
        elif src:
            bits.append("Fuente:")
        if src:
            bits.append(src)
        if fecha:
            bits.append(fecha)
        parts.append(f'<div style="font-family:{SANS};font-size:12px;color:{GRIS};margin-top:8px;">{" &middot; ".join(bits)}</div>')
    return f'<tr><td style="padding:14px 24px;border-bottom:1px solid {REGLA};">{"".join(parts)}</td></tr>'


def section_block(sec: dict) -> str:
    out = [titulo_seccion(esc(sec.get("titulo", "")))]
    out += [item_block(it) for it in sec.get("items", [])]
    notas = [n for n in sec.get("notas", []) if str(n).strip()]
    if notas:
        lis = "".join(f'<li style="margin:4px 0;">{esc(n)}</li>' for n in notas)
        out.append(
            f'<tr><td style="padding:10px 24px 0 24px;font-family:{SERIF};font-size:14px;color:{GRIS};line-height:1.5;">'
            f'<ul style="margin:0;padding-left:20px;">{lis}</ul></td></tr>'
        )
    return "".join(out)


# ---------- alerta y tendencia ----------

def alerta_block(t: dict | None) -> str:
    alertas = (t or {}).get("alertas") or []
    if not alertas:
        return ""
    lines = "".join(f'<div style="margin:2px 0;">{esc(a.get("texto", ""))}</div>' for a in alertas)
    return (
        f'<tr><td style="padding:16px 24px 0 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-top:3px solid {AMBAR};border-bottom:1px solid {AMBAR};"><tr>'
        f'<td style="padding:10px 0;font-family:{SANS};font-size:14px;font-weight:bold;color:{AMBAR};line-height:1.5;">{lines}</td>'
        f"</tr></table></td></tr>"
    )


def tendencia_card(i: dict) -> str:
    etiqueta = esc(i.get("etiqueta", ""))
    valor = esc((i.get("ultimo") or {}).get("texto", ""))
    frase = esc(i.get("frase", ""))
    if i.get("suficiente") and i.get("variacion"):
        v = i["variacion"]
        t = TREND.get(v.get("direccion", ""), TREND["igual"])
        chip = (
            f' <span style="font-family:{SANS};font-size:13px;color:{t[1]};white-space:nowrap;">{t[0]} {esc(v.get("texto_corto", ""))}'
            f' <span style="color:{GRIS};">en {esc(v.get("dias", ""))} d</span></span>'
        )
        aviso = ""
    else:
        chip = ""
        aviso = (
            f'<div style="margin-top:6px;font-family:{SANS};font-size:12px;color:{GRIS};">'
            f'<b style="text-transform:uppercase;letter-spacing:.1em;font-size:10px;border:1px solid {GRIS};padding:1px 5px;">Historial insuficiente</b>'
            f' &nbsp;{esc(i.get("n_dias", 0))} de 5 d&iacute;as h&aacute;biles</div>'
        )
    return (
        f'<tr><td style="padding:14px 24px;border-bottom:1px solid {REGLA};">'
        f'<div>{etiqueta_chica(etiqueta)}</div>'
        f'<div style="margin-top:2px;"><span style="font-family:{SERIF};font-size:20px;color:{TINTA};">{valor}</span>{chip}</div>'
        f'{aviso}'
        f'<div style="margin-top:8px;font-family:{SERIF};font-size:14px;color:{TINTA};line-height:1.55;">{frase}</div></td></tr>'
    )


def tendencia_block(t: dict | None) -> str:
    inds = (t or {}).get("indicadores") or []
    if not inds:
        return ""
    nota = (f'<tr><td style="padding:6px 24px 0 24px;font-family:{SERIF};font-size:13px;font-style:italic;color:{GRIS};line-height:1.5;">'
            f'Calculada con el historial guardado, no estimada. Con menos de 5 d&iacute;as h&aacute;biles no se calcula.</td></tr>')
    return titulo_seccion("Tendencia de la semana") + nota + "".join(tendencia_card(i) for i in inds)


# ---------- documento ----------

def render_html(d: dict, t: dict | None = None, registro: list | None = None) -> str:
    d = sin_faltantes(d)
    if registro is not None:  # sin registro (pruebas del diseño) no se ajusta nada
        d, _ = ajustar_verificacion(d, registro)
    kpis = kpi_block(d.get("titulares", [])) + tendencia_block(t)
    alerta = alerta_block(t)
    sections = "".join(section_block(s) for s in d.get("secciones", []))
    lim = [x for x in d.get("limitaciones", []) if str(x).strip()]
    lim_html = ""
    if lim:
        lis = "".join(f'<li style="margin:4px 0;">{esc(x)}</li>' for x in lim)
        lim_html = (
            titulo_seccion("Por confirmar hoy")
            + f'<tr><td style="padding:8px 24px 0 24px;font-family:{SERIF};font-size:14px;color:{GRIS};line-height:1.5;">'
            f'<ul style="margin:0;padding-left:20px;">{lis}</ul></td></tr>'
        )
    resumen = esc(d.get("resumen", ""))
    pie = esc(d.get("pie", "Reporte generado automáticamente. Verifique las cifras en la fuente antes de decidir. No es asesoría financiera."))
    leyenda = ("<b>Fuente oficial</b>: la p&aacute;gina o los datos abiertos del organismo, abiertos hoy. "
               "<b>V&iacute;a prensa</b>: un medio que cita al organismo. <b>Sin verificar</b>: solo un resultado de b&uacute;squeda.")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{esc(d.get("titulo", "Reporte"))}</title></head>
<body style="margin:0;padding:0;background:{FONDO};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{resumen}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};"><tr><td align="center" style="padding:16px 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:{PAPEL};border-top:5px solid {AZUL};">
<tr><td style="padding:22px 24px 14px 24px;border-bottom:3px double #b8c2cc;">
<div>{etiqueta_chica("Bolet&iacute;n econ&oacute;mico &middot; Colombia", AZUL)}</div>
<div style="font-family:{SERIF};font-size:29px;line-height:1.15;color:{TINTA};margin-top:8px;">{esc(d.get("titulo", "Reporte económico"))}</div>
<div style="font-family:{SERIF};font-size:14px;font-style:italic;color:{GRIS};margin-top:6px;">{esc(d.get("fecha", ""))}</div></td></tr>
{alerta}
<tr><td style="padding:18px 24px 0 24px;font-family:{SERIF};font-size:17px;color:{TINTA};line-height:1.6;">{resumen}</td></tr>
{kpis}
{sections}
{lim_html}
<tr><td style="padding:28px 24px 6px 24px;font-family:{SANS};font-size:11px;color:{GRIS};line-height:1.6;border-top:1px solid {REGLA};">
<div>{leyenda}</div><div style="margin-top:8px;">{pie}</div></td></tr>
<tr><td style="height:12px;line-height:12px;">&nbsp;</td></tr>
</table></td></tr></table></body></html>"""


def render_text(d: dict, t: dict | None = None, registro: list | None = None) -> str:
    d = sin_faltantes(d)
    if registro is not None:
        d, _ = ajustar_verificacion(d, registro)
    lines = [str(d.get("titulo", "Reporte")), str(d.get("fecha", "")), ""]
    for a in (t or {}).get("alertas") or []:
        lines.append(f'!! {a.get("texto", "")}')
    lines += ["", str(d.get("resumen", "")), ""]
    for k in d.get("titulares", [])[:4]:
        lines.append(f'* {k.get("etiqueta", "")}: {k.get("valor", "")} {k.get("cambio", "")}'.rstrip())
    if (t or {}).get("indicadores"):
        lines += ["", "TENDENCIA DE LA SEMANA", "-" * 30]
        for i in t["indicadores"]:
            lines.append(str(i.get("frase", "")))
    for s in d.get("secciones", []):
        lines += ["", str(s.get("titulo", "")).upper(), "-" * 30]
        for it in s.get("items", []):
            head = f'{it.get("nombre", "")}: {it.get("valor", "")}'.rstrip(": ")
            if it.get("cambio"):
                head += f' ({it["cambio"]})'
            if it.get("estado") in STATE:
                head += f' [{STATE[it["estado"]][0]}]'
            lines.append(head)
            for key, label in (("detalle", ""), ("efecto", "Impacto: ")):
                if it.get(key):
                    lines.append(f"  {label}{it[key]}")
            src = " · ".join(x for x in (VERIF_TXT.get(it.get("verificacion", "")), it.get("fuente"), it.get("fecha")) if x)
            if src:
                lines.append(f"  Fuente: {src}")
        for n in s.get("notas", []):
            lines.append(f"  - {n}")
    if d.get("limitaciones"):
        lines += ["", "POR CONFIRMAR HOY"]
        lines += [f"  - {x}" for x in d["limitaciones"]]
    lines += ["", str(d.get("pie", "Reporte generado automáticamente. No es asesoría financiera."))]
    return "\n".join(lines) + "\n"


def validate(d: dict) -> list[str]:
    problems = []
    for key in ("titulo", "fecha", "resumen"):
        if not str(d.get(key, "")).strip():
            problems.append(f"falta '{key}'")
    if not d.get("secciones"):
        problems.append("falta 'secciones' (lista con al menos una sección)")
    for i, s in enumerate(d.get("secciones", [])):
        if not s.get("items"):
            problems.append(f"la sección {i} ('{s.get('titulo', '')}') no tiene 'items'")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("--out", default=".")
    ap.add_argument("--fuentes", default=abrir_fuente.REGISTRO,
                    help="fuentes_abiertas.json: las páginas oficiales que de verdad se abrieron")
    ap.add_argument("--tendencia", help="tendencias.json de tendencia.py: agrega la alerta y la sección de tendencia")
    args = ap.parse_args()
    try:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: no pude leer {args.json_file} como JSON válido: {e}", file=sys.stderr)
        return 2
    problems = validate(data)
    if problems:
        print("ERROR: reporte.json incompleto: " + "; ".join(problems), file=sys.stderr)
        return 2
    tend = None
    if args.tendencia:
        try:
            tend = json.loads(Path(args.tendencia).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERROR: no pude leer {args.tendencia} como JSON válido: {e}", file=sys.stderr)
            return 2
    registro = abrir_fuente.leer_registro(args.fuentes)  # si no existe: lista vacía, nada es 'oficial'
    _, bajaron = ajustar_verificacion(sin_faltantes(data), registro)
    if bajaron:
        print("aviso: bajé a 'Sin verificar' estas cifras, porque no hay registro de que se abrió su página "
              "oficial: " + "; ".join(bajaron) + ". Ábrelas con abrir_fuente.py o márcalas 'prensa'.", file=sys.stderr)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reporte.html").write_text(render_html(data, tend, registro), encoding="utf-8")
    (out / "reporte.txt").write_text(render_text(data, tend, registro), encoding="utf-8")
    print(f"ok: {out / 'reporte.html'} y {out / 'reporte.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
