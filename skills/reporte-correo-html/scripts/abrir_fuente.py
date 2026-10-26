#!/usr/bin/env python3
"""Abre una página OFICIAL (.gov.co) desde el sandbox y deja constancia de que de verdad se abrió.

Uso:
  python3 abrir_fuente.py https://www.dane.gov.co/... [--max-chars 8000]

Imprime el texto de la página, sin etiquetas HTML. Cada intento queda en el registro
(/mnt/session/outputs/fuentes_abiertas.json): la dirección, el estado HTTP y si la página se
pudo leer o la bloqueó el sitio. El renderizador del correo SOLO deja decir "Fuente oficial"
a una cifra cuya página aparece en ese registro como leída. Así la etiqueta no depende de que
el modelo diga la verdad: depende de que la página se abrió.

Para páginas de prensa usa web_fetch; esas cifras son "Vía prensa", nunca "oficial".
Solo librería estándar.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REGISTRO = os.environ.get("FUENTES_LOG", "/mnt/session/outputs/fuentes_abiertas.json")
# frases típicas de una página que bloquea robots en vez de mostrar su contenido
BLOQUEOS = ("radware bot manager", "access denied", "request blocked", "are you a robot",
            "attention required", "verify you are human", "captcha")
MIN_TEXTO = 100  # menos que esto no es una página con contenido


def normalizar(url: str) -> str:
    """'https://www.dane.gov.co/a/b/?x=1#y' -> 'dane.gov.co/a/b'. Sirve para comparar direcciones."""
    p = urllib.parse.urlparse(str(url).strip())
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    return f"{host}{p.path.rstrip('/')}"


def es_oficial(url: str) -> bool:
    p = urllib.parse.urlparse(str(url).strip())
    host = p.netloc.lower().split(":")[0]
    return p.scheme == "https" and (host == "gov.co" or host.endswith(".gov.co"))


def texto_de(contenido: str) -> str:
    sin = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", contenido)
    sin = re.sub(r"(?s)<[^>]+>", " ", sin)
    return re.sub(r"\s+", " ", html.unescape(sin)).strip()


def bloqueada(texto: str, estado: int) -> bool:
    return estado in (401, 403, 429) or any(b in texto.lower()[:4000] for b in BLOQUEOS)


def leer_registro(ruta: str) -> list:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return datos if isinstance(datos, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def registrar(ruta: str, url: str, estado: int, leida: bool, nbytes: int, nota: str = "") -> None:
    datos = leer_registro(ruta)
    datos.append({"url": normalizar(url), "url_original": str(url), "estado": estado, "ok": bool(leida),
                  "bytes": nbytes, "nota": nota, "hora": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def abrir(url: str, ruta: str, max_chars: int):
    """Devuelve (leida, estado, texto). Siempre deja una línea en el registro."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; analista-colombia/1.0)",
                                               "Accept-Language": "es-CO,es;q=0.9"})
    estado, cuerpo = 0, ""
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            estado = resp.status
            cuerpo = resp.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        estado = e.code
        cuerpo = e.read(200_000).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as e:
        registrar(ruta, url, 0, False, 0, f"sin conexión: {e}")
        return False, 0, ""
    texto = texto_de(cuerpo)
    leida = estado == 200 and not bloqueada(texto, estado) and len(texto) >= MIN_TEXTO
    registrar(ruta, url, estado, leida, len(cuerpo), "" if leida else "bloqueada o sin contenido")
    return leida, estado, texto[:max_chars]


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--max-chars", type=int, default=8000)
    ap.add_argument("--registro", default=REGISTRO)
    args = ap.parse_args(argv)
    if not es_oficial(args.url):
        print("ERROR: solo abro páginas https de dominios .gov.co. Para prensa usa web_fetch "
              "(esas cifras son 'Vía prensa').", file=sys.stderr)
        return 2
    leida, estado, texto = abrir(args.url, args.registro, args.max_chars)
    if not leida:
        print(f"BLOQUEADA estado={estado}: no pude leer {normalizar(args.url)}. Esta cifra no puede ser "
              f"'oficial'; usa una página de prensa que la cite y márcala 'prensa'.")
        return 1
    print(f"OK estado={estado} {normalizar(args.url)}\n---\n{texto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
