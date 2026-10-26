"""Pruebas del correo HTML (render_email.py). No usan internet.

Correr desde la raíz del proyecto:
  python -m unittest tests.unit.test_render -v
"""

import importlib.util
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / "skills" / "reporte-correo-html"


def cargar(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r = cargar("render_email", SKILL / "scripts" / "render_email.py")
REPORTE = json.loads((SKILL / "ejemplo.json").read_text(encoding="utf-8"))

SUFICIENTE = {
    "clave": "trm_usd", "etiqueta": "TRM", "n_dias": 21, "suficiente": True,
    "ultimo": {"fecha": "2026-10-26", "valor": 3158.43, "texto": "$3.158,43"},
    "variacion": {"dias": 5, "abs": -16.24, "pct": -0.51, "direccion": "baja", "texto_corto": "-0,51 %"},
    "sparkline": "▇▅▃▁", "spark_dias": 4,
    "frase": "TRM baja $16,24 (-0,51 %) en 5 días hábiles.",
}
INSUFICIENTE = {
    "clave": "euro_cop", "etiqueta": "Euro", "n_dias": 1, "suficiente": False,
    "ultimo": {"fecha": "2026-10-23", "valor": 3553.1, "texto": "$3.553,10"},
    "variacion": None, "sparkline": "", "spark_dias": 0,
    "frase": "Euro: historial insuficiente (1 de 5 días hábiles). Último valor: $3.553,10.",
}


class Tendencia(unittest.TestCase):
    def test_sin_tendencia_el_correo_no_cambia(self):
        html = r.render_html(REPORTE)
        self.assertNotIn("Tendencia de la semana", html)
        self.assertNotIn("Alerta", html)

    def test_con_tendencia_aparece_la_seccion(self):
        html = r.render_html(REPORTE, {"indicadores": [SUFICIENTE, INSUFICIENTE], "alertas": []})
        self.assertIn("Tendencia de la semana", html)
        self.assertIn("▇▅▃▁", html)
        self.assertIn("-0,51 %", html)

    def test_historial_insuficiente_no_dibuja_grafica_ni_flecha(self):
        bloque = r.tendencia_block({"indicadores": [INSUFICIENTE], "alertas": []})  # solo la sección
        self.assertIn("Historial insuficiente", bloque)
        self.assertNotIn("&#9650;", bloque)
        self.assertNotIn("&#9660;", bloque)
        self.assertNotIn("monospace", bloque)

    def test_alerta_aparece_arriba_del_resumen(self):
        a = {"texto": "Alerta: TRM sube 1,57 % en un día (de $3.185,01 a $3.235,00)."}
        html = r.render_html(REPORTE, {"indicadores": [], "alertas": [a]})
        self.assertIn("Alerta: TRM sube 1,57 %", html)
        # el resumen sale dos veces: oculto (vista previa en la bandeja) y visible; la alerta va antes del visible
        self.assertLess(html.index("Alerta: TRM"), html.rindex(REPORTE["resumen"][:30]))

    def test_texto_plano_incluye_alerta_y_tendencia(self):
        a = {"texto": "Alerta: TRM sube 1,57 % en un día."}
        txt = r.render_text(REPORTE, {"indicadores": [SUFICIENTE], "alertas": [a]})
        self.assertIn("!! Alerta: TRM sube 1,57 %", txt)
        self.assertIn("TENDENCIA DE LA SEMANA", txt)

    def test_etiqueta_de_verificacion(self):
        def con(v):
            item = {"nombre": "X", "valor": "1", "fuente": "Fuente X", "verificacion": v}
            return r.item_block(item)
        self.assertIn("Fuente oficial", con("oficial"))
        self.assertIn("V&iacute;a prensa", con("prensa"))
        self.assertIn("Sin verificar", con("sin_verificar"))
        sin = r.item_block({"nombre": "X", "valor": "1", "fuente": "Fuente X"})
        self.assertNotIn("Fuente oficial", sin)  # sin el campo no se afirma nada
        self.assertIn("Fuente:", sin)

    def test_verificacion_en_texto_plano(self):
        d = {"titulo": "T", "fecha": "F", "resumen": "R", "secciones": [
            {"titulo": "S", "items": [{"nombre": "TRM", "valor": "1", "fuente": "Superfinanciera", "verificacion": "oficial"}]}]}
        self.assertIn("Fuente: Fuente oficial · Superfinanciera", r.render_text(d))

    def test_el_diseno_no_usa_la_paleta_anterior(self):
        html = r.render_html(REPORTE, {"indicadores": [SUFICIENTE], "alertas": []}).lower()
        for viejo in ("#12263f", "#c8922a", "border-radius"):  # azul marino, dorado, esquinas redondeadas
            self.assertNotIn(viejo, html)

    def test_el_texto_se_escapa(self):
        malo = dict(SUFICIENTE, frase="<script>alert(1)</script>")
        html = r.render_html(REPORTE, {"indicadores": [malo], "alertas": []})
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_la_grafica_no_ensancha_el_correo(self):
        """Un nowrap sin límite fue lo que rompió el diseño en pantallas angostas."""
        html = r.render_html(REPORTE, {"indicadores": [SUFICIENTE], "alertas": []})
        self.assertIn("font-size:16px", html)
        self.assertIn("overflow:hidden", html)


if __name__ == "__main__":
    unittest.main()
