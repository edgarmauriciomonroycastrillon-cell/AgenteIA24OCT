#!/usr/bin/env python3
"""Render reporte.json into an email-safe HTML file and a plain-text twin.

Usage:
  python3 render_email.py reporte.json --out /mnt/session/outputs

Writes <out>/reporte.html and <out>/reporte.txt. Standard library only.
All text in the JSON is plain text: this script escapes it, so never put HTML in it.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

NAVY = "#12263f"
ACCENT = "#c8922a"
INK = "#1f2937"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BG = "#f3f4f6"
CARD = "#ffffff"
FONT = "Segoe UI,Helvetica,Arial,sans-serif"

TREND = {
    "sube": ("&#9650;", "#b45309"),
    "baja": ("&#9660;", "#1d4ed8"),
    "igual": ("&#9632;", "#6b7280"),
}
STATE = {
    "desactualizado": ("Desactualizado", "#fef3c7", "#92400e"),
    "no_encontrado": ("No encontrado", "#e5e7eb", "#374151"),
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def safe_url(url) -> str:
    url = str(url or "").strip()
    return url if url.startswith(("https://", "http://")) else ""


def trend_of(item: dict):
    return TREND.get(str(item.get("tendencia", "")).lower())


def kpi_cell(k: dict) -> str:
    arrow = ""
    t = trend_of(k)
    cambio = esc(k.get("cambio", ""))
    if t and cambio:
        arrow = f'<div style="font-size:13px;color:{t[1]};margin-top:2px;">{t[0]} {cambio}</div>'
    elif cambio:
        arrow = f'<div style="font-size:13px;color:{MUTED};margin-top:2px;">{cambio}</div>'
    nota = esc(k.get("nota", ""))
    nota_html = f'<div style="font-size:11px;color:{MUTED};margin-top:4px;">{nota}</div>' if nota else ""
    return (
        f'<td width="50%" valign="top" style="padding:6px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{CARD};border:1px solid {LINE};border-top:3px solid {ACCENT};border-radius:8px;">'
        f'<tr><td style="padding:12px 14px;font-family:{FONT};">'
        f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};">{esc(k.get("etiqueta", ""))}</div>'
        f'<div style="font-size:22px;font-weight:700;color:{NAVY};margin-top:4px;">{esc(k.get("valor", ""))}</div>'
        f"{arrow}{nota_html}</td></tr></table></td>"
    )


def kpi_block(kpis: list) -> str:
    kpis = kpis[:4]
    if not kpis:
        return ""
    rows = []
    for i in range(0, len(kpis), 2):
        pair = kpis[i : i + 2]
        cells = "".join(kpi_cell(k) for k in pair)
        if len(pair) == 1:
            cells += '<td width="50%" style="padding:6px;">&nbsp;</td>'
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<tr><td style="padding:14px 18px 0 18px;"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0">{"".join(rows)}</table></td></tr>'
    )


def item_block(it: dict) -> str:
    parts = []
    estado = STATE.get(str(it.get("estado", "")).lower())
    badge = ""
    if estado:
        badge = (
            f' <span style="display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;'
            f'border-radius:10px;background:{estado[1]};color:{estado[2]};vertical-align:middle;">{estado[0]}</span>'
        )
    parts.append(
        f'<div style="font-size:15px;font-weight:700;color:{NAVY};">{esc(it.get("nombre", ""))}{badge}</div>'
    )
    valor = esc(it.get("valor", ""))
    if valor:
        parts.append(f'<div style="font-size:20px;font-weight:700;color:{INK};margin-top:4px;">{valor}</div>')
    cambio = esc(it.get("cambio", ""))
    t = trend_of(it)
    if cambio:
        color = t[1] if t else MUTED
        arrow = f"{t[0]} " if t else ""
        parts.append(f'<div style="font-size:13px;color:{color};margin-top:2px;">{arrow}{cambio}</div>')
    detalle = esc(it.get("detalle", ""))
    if detalle:
        parts.append(f'<div style="font-size:14px;color:{INK};margin-top:8px;line-height:1.5;">{detalle}</div>')
    efecto = esc(it.get("efecto", ""))
    if efecto:
        parts.append(
            f'<div style="font-size:14px;color:{INK};margin-top:8px;line-height:1.5;background:#f9fafb;'
            f'border-left:3px solid {ACCENT};padding:8px 10px;"><strong>Impacto:</strong> {efecto}</div>'
        )
    fuente = esc(it.get("fuente", ""))
    fecha = esc(it.get("fecha", ""))
    url = safe_url(it.get("url"))
    if fuente or fecha:
        src = fuente
        if url and fuente:
            src = f'<a href="{esc(url)}" style="color:{MUTED};text-decoration:underline;">{fuente}</a>'
        bits = [b for b in (src, fecha) if b]
        parts.append(
            f'<div style="font-size:12px;color:{MUTED};margin-top:8px;">Fuente: {" &middot; ".join(bits)}</div>'
        )
    return (
        f'<tr><td style="padding:6px 18px;"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" style="background:{CARD};border:1px solid {LINE};border-radius:8px;">'
        f'<tr><td style="padding:14px 16px;font-family:{FONT};">{"".join(parts)}</td></tr></table></td></tr>'
    )


def section_block(sec: dict) -> str:
    out = [
        f'<tr><td style="padding:22px 18px 4px 18px;font-family:{FONT};">'
        f'<div style="font-size:19px;font-weight:700;color:{NAVY};border-left:4px solid {ACCENT};'
        f'padding:2px 0 2px 10px;">{esc(sec.get("titulo", ""))}</div></td></tr>'
    ]
    out += [item_block(it) for it in sec.get("items", [])]
    notas = [n for n in sec.get("notas", []) if str(n).strip()]
    if notas:
        lis = "".join(f'<li style="margin:4px 0;">{esc(n)}</li>' for n in notas)
        out.append(
            f'<tr><td style="padding:6px 18px 0 18px;font-family:{FONT};font-size:14px;color:{INK};line-height:1.5;">'
            f'<ul style="margin:0;padding-left:20px;">{lis}</ul></td></tr>'
        )
    return "".join(out)


def alerta_block(t: dict | None) -> str:
    alertas = (t or {}).get("alertas") or []
    if not alertas:
        return ""
    lines = "".join(f'<div style="margin:2px 0;">{esc(a.get("texto", ""))}</div>' for a in alertas)
    return (
        f'<tr><td style="padding:14px 18px 0 18px;"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" style="background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #dc2626;'
        f'border-radius:8px;"><tr><td style="padding:12px 16px;font-family:{FONT};font-size:14px;'
        f'font-weight:600;color:#7f1d1d;line-height:1.5;">&#9888; {lines}</td></tr></table></td></tr>'
    )


def tendencia_card(i: dict) -> str:
    etiqueta = esc(i.get("etiqueta", ""))
    valor = esc((i.get("ultimo") or {}).get("texto", ""))
    frase = esc(i.get("frase", ""))
    if i.get("suficiente") and i.get("variacion"):
        v = i["variacion"]
        t = TREND.get(v.get("direccion", ""), TREND["igual"])
        # 16 px y una columna: 20 bloques miden ~210 px y caben en un celular de 320 px.
        spark = (
            f'<div style="font-family:Consolas,Menlo,\'Courier New\',monospace;font-size:16px;line-height:1.1;'
            f'letter-spacing:1px;color:{NAVY};white-space:nowrap;overflow:hidden;">{esc(i.get("sparkline", ""))}</div>'
            f'<div style="font-size:11px;color:{MUTED};margin-top:3px;">&uacute;ltimos {esc(i.get("spark_dias", ""))} d&iacute;as h&aacute;biles</div>'
        )
        chip = (
            f' <span style="font-size:13px;font-weight:600;color:{t[1]};white-space:nowrap;">{t[0]} {esc(v.get("texto_corto", ""))}'
            f' <span style="font-weight:400;color:{MUTED};">en {esc(v.get("dias", ""))} d</span></span>'
        )
    else:
        spark = (
            f'<span style="display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;'
            f'background:#e5e7eb;color:#374151;">Historial insuficiente</span>'
            f'<div style="font-size:11px;color:{MUTED};margin-top:4px;">{esc(i.get("n_dias", 0))} de 5 d&iacute;as h&aacute;biles</div>'
        )
        chip = ""
    return (
        f'<tr><td style="padding:6px 18px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{CARD};border:1px solid {LINE};border-radius:8px;"><tr>'
        f'<td style="padding:12px 14px;font-family:{FONT};">'
        f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};">{etiqueta}</div>'
        f'<div style="margin-top:2px;"><span style="font-size:18px;font-weight:700;color:{NAVY};">{valor}</span>{chip}</div>'
        f'<div style="margin-top:8px;">{spark}</div>'
        f'<div style="margin-top:8px;font-size:13px;color:{INK};line-height:1.5;">{frase}</div></td></tr>'
        f"</table></td></tr>"
    )


def tendencia_block(t: dict | None) -> str:
    inds = (t or {}).get("indicadores") or []
    if not inds:
        return ""
    head = (
        f'<tr><td style="padding:22px 18px 4px 18px;font-family:{FONT};">'
        f'<div style="font-size:19px;font-weight:700;color:{NAVY};border-left:4px solid {ACCENT};'
        f'padding:2px 0 2px 10px;">Tendencia de la semana</div>'
        f'<div style="font-size:12px;color:{MUTED};margin:6px 0 0 14px;">Calculada con el historial guardado, no estimada. '
        f'Con menos de 5 d&iacute;as h&aacute;biles no se calcula.</div></td></tr>'
    )
    return head + "".join(tendencia_card(i) for i in inds)


def render_html(d: dict, t: dict | None = None) -> str:
    kpis = kpi_block(d.get("titulares", [])) + tendencia_block(t)
    alerta = alerta_block(t)
    sections = "".join(section_block(s) for s in d.get("secciones", []))
    lim = [x for x in d.get("limitaciones", []) if str(x).strip()]
    lim_html = ""
    if lim:
        lis = "".join(f'<li style="margin:4px 0;">{esc(x)}</li>' for x in lim)
        lim_html = (
            f'<tr><td style="padding:22px 18px 0 18px;"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;"><tr>'
            f'<td style="padding:12px 16px;font-family:{FONT};font-size:13px;color:#78350f;line-height:1.5;">'
            f"<strong>Lo que no pude verificar hoy</strong>"
            f'<ul style="margin:6px 0 0 0;padding-left:20px;">{lis}</ul></td></tr></table></td></tr>'
        )
    resumen = esc(d.get("resumen", ""))
    pie = esc(d.get("pie", "Reporte generado automáticamente. Verifique las cifras en la fuente antes de decidir. No es asesoría financiera."))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(d.get("titulo", "Reporte"))}</title></head>
<body style="margin:0;padding:0;background:{BG};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{resumen}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center" style="padding:16px 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:{BG};">
<tr><td bgcolor="{NAVY}" style="background:{NAVY};border-radius:10px 10px 0 0;padding:22px 22px 18px 22px;font-family:{FONT};">
<div style="font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:{ACCENT};font-weight:700;">Analista económico &middot; Colombia</div>
<div style="font-size:24px;font-weight:700;color:#ffffff;margin-top:6px;">{esc(d.get("titulo", "Reporte económico"))}</div>
<div style="font-size:13px;color:#cbd5e1;margin-top:4px;">{esc(d.get("fecha", ""))}</div></td></tr>
{alerta}
<tr><td style="padding:16px 22px 0 22px;font-family:{FONT};font-size:15px;color:{INK};line-height:1.55;background:{BG};">{resumen}</td></tr>
{kpis}
{sections}
{lim_html}
<tr><td style="padding:24px 22px 8px 22px;font-family:{FONT};font-size:11px;color:{MUTED};line-height:1.5;text-align:center;">{pie}</td></tr>
</table></td></tr></table></body></html>"""


def render_text(d: dict, t: dict | None = None) -> str:
    lines = [str(d.get("titulo", "Reporte")), str(d.get("fecha", "")), ""]
    for a in (t or {}).get("alertas") or []:
        lines.append(f'!! {a.get("texto", "")}')
    lines += ["", str(d.get("resumen", "")), ""]
    for k in d.get("titulares", [])[:4]:
        lines.append(f'* {k.get("etiqueta", "")}: {k.get("valor", "")} {k.get("cambio", "")}'.rstrip())
    if (t or {}).get("indicadores"):
        lines += ["", "TENDENCIA DE LA SEMANA", "-" * 30]
        for i in t["indicadores"]:
            spark = f' {i["sparkline"]}' if i.get("sparkline") else ""
            lines.append(f'{i.get("frase", "")}{spark}')
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
            src = " · ".join(x for x in (it.get("fuente"), it.get("fecha")) if x)
            if src:
                lines.append(f"  Fuente: {src}")
        for n in s.get("notas", []):
            lines.append(f"  - {n}")
    if d.get("limitaciones"):
        lines += ["", "LO QUE NO PUDE VERIFICAR HOY"]
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
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reporte.html").write_text(render_html(data, tend), encoding="utf-8")
    (out / "reporte.txt").write_text(render_text(data, tend), encoding="utf-8")
    print(f"ok: {out / 'reporte.html'} y {out / 'reporte.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
