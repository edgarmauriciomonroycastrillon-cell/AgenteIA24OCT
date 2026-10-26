"""Pruebas de abrir_fuente.py y de la regla "oficial solo si se abrió". No usan internet.

Correr desde la raíz del proyecto:
  python -m unittest tests.unit.test_abrir_fuente -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "skills" / "reporte-correo-html" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import abrir_fuente as a  # noqa: E402
import render_email as r  # noqa: E402


class Direcciones(unittest.TestCase):
    def test_normalizar_ignora_www_consulta_y_barra_final(self):
        self.assertEqual(a.normalizar("https://www.dane.gov.co/ipc/?x=1#y"), "dane.gov.co/ipc")
        self.assertEqual(a.normalizar("https://dane.gov.co/ipc"), "dane.gov.co/ipc")

    def test_solo_https_y_gov_co_son_oficiales(self):
        self.assertTrue(a.es_oficial("https://www.dane.gov.co/x"))
        self.assertTrue(a.es_oficial("https://www.datos.gov.co/resource/32sa-8pi3.json"))
        self.assertFalse(a.es_oficial("http://www.dane.gov.co/x"))          # sin https
        self.assertFalse(a.es_oficial("https://portafolio.co/x"))           # prensa
        self.assertFalse(a.es_oficial("https://dane.gov.co.evil.com/x"))    # truco de dominio
        self.assertFalse(a.es_oficial("https://evilgov.co/x"))


class Lectura(unittest.TestCase):
    def test_texto_sin_etiquetas_ni_scripts(self):
        t = a.texto_de("<html><script>var x=1</script><style>p{}</style><p>IPC  <b>6,29 %</b></p></html>")
        self.assertEqual(t, "IPC 6,29 %")

    def test_una_pagina_de_bloqueo_no_cuenta_como_leida(self):
        self.assertTrue(a.bloqueada("Radware Bot Manager Block window.SSJSInternal", 200))
        self.assertTrue(a.bloqueada("contenido normal", 403))
        self.assertFalse(a.bloqueada("La inflación anual fue 6,29 %", 200))


class Registro(unittest.TestCase):
    def test_registrar_y_leer(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / "fuentes.json")
            self.assertEqual(a.leer_registro(ruta), [])
            a.registrar(ruta, "https://www.dane.gov.co/ipc/", 200, True, 5000)
            a.registrar(ruta, "https://www.banrep.gov.co/tasas", 403, False, 300, "bloqueada")
            reg = a.leer_registro(ruta)
            self.assertEqual([e["url"] for e in reg], ["dane.gov.co/ipc", "banrep.gov.co/tasas"])
            self.assertEqual([e["ok"] for e in reg], [True, False])

    def test_registro_dañado_se_trata_como_vacio(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "f.json"
            ruta.write_text("{no es json", encoding="utf-8")
            self.assertEqual(a.leer_registro(str(ruta)), [])


class OficialSoloSiSeAbrio(unittest.TestCase):
    def reporte(self, **item):
        base = {"nombre": "Tasa Banrep", "valor": "12,25 %", "fuente": "Banco de la República",
                "verificacion": "oficial", "url": "https://www.banrep.gov.co/es/estadisticas/tasas-interes"}
        base.update(item)
        return {"titulo": "T", "fecha": "F", "resumen": "R", "secciones": [{"titulo": "S", "items": [base]}]}

    def test_sin_registro_baja_a_sin_verificar(self):
        d, bajaron = r.ajustar_verificacion(self.reporte(), [])
        self.assertEqual(d["secciones"][0]["items"][0]["verificacion"], "sin_verificar")
        self.assertEqual(bajaron, ["Tasa Banrep"])

    def test_pagina_bloqueada_baja_aunque_este_en_el_registro(self):
        reg = [{"url": "banrep.gov.co/es/estadisticas/tasas-interes", "ok": False}]
        _, bajaron = r.ajustar_verificacion(self.reporte(), reg)
        self.assertEqual(bajaron, ["Tasa Banrep"])

    def test_pagina_leida_se_queda_oficial(self):
        reg = [{"url": "banrep.gov.co/es/estadisticas/tasas-interes", "ok": True}]
        d, bajaron = r.ajustar_verificacion(self.reporte(), reg)
        self.assertEqual(bajaron, [])
        self.assertEqual(d["secciones"][0]["items"][0]["verificacion"], "oficial")

    def test_oficial_sin_url_baja(self):
        _, bajaron = r.ajustar_verificacion(self.reporte(url=""), [{"url": "x", "ok": True}])
        self.assertEqual(bajaron, ["Tasa Banrep"])

    def test_prensa_no_se_toca(self):
        d, bajaron = r.ajustar_verificacion(self.reporte(verificacion="prensa"), [])
        self.assertEqual(bajaron, [])
        self.assertEqual(d["secciones"][0]["items"][0]["verificacion"], "prensa")

    def test_el_correo_no_dice_fuente_oficial_sin_respaldo(self):
        etiqueta = 'color:#2b5f9e;">Fuente oficial</b>'  # la de la cifra; el pie también explica la frase
        html = r.render_html(self.reporte(), None, registro=[])
        self.assertNotIn(etiqueta, html)
        self.assertIn('color:#b45309;">Sin verificar</b>', html)
        txt = r.render_text(self.reporte(), None, registro=[])
        self.assertNotIn("Fuente oficial", txt)

    def test_el_correo_dice_fuente_oficial_con_respaldo(self):
        reg = [{"url": "banrep.gov.co/es/estadisticas/tasas-interes", "ok": True}]
        self.assertIn('color:#2b5f9e;">Fuente oficial</b>', r.render_html(self.reporte(), None, registro=reg))

    def test_la_url_del_registro_puede_traer_consulta_o_www(self):
        reg = [{"url": a.normalizar("https://www.datos.gov.co/resource/32sa-8pi3.json?$limit=2"), "ok": True}]
        item = self.reporte(url="https://www.datos.gov.co/resource/32sa-8pi3.json")
        _, bajaron = r.ajustar_verificacion(item, reg)
        self.assertEqual(bajaron, [])


if __name__ == "__main__":
    unittest.main()
