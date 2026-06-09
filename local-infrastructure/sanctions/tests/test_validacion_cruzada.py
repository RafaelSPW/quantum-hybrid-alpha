"""
Tests unitarios para validacion_cruzada.py.

Casos cubiertos:
  1. Sin alertas — riesgo Bajo, sin OFAC, dentro de umbral → SIN_ALERTAS_AUTOMATICAS
  2. Con alertas — riesgo Alto + incongruencia de fondos confirmada → ALERTAS_PENDIENTES_REVISION
  3. Sin confirmación humana — fondos no confirmados → analisis_fondos=None en legajo
  4. IDOR en _verificar_ownership_tareas — tarea de otro usuario → rechazada
"""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Los tests no necesitan google-cloud-kms — los fondos de los casos simples
# no tienen montos_confirmados, así que crypto.cifrar no se llama.
from sanctions.validacion_cruzada import (
    construir_legajo_unificado,
    calcular_vigencia_hasta,
    _calcular_estado,
    _evaluar_consistencia_perfil,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _screening_sin_alertas() -> dict:
    return {
        "consulta": "Juan Perez",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ofac": {
            "coincidencias": [],
            "riesgo": "ninguno",
            "fuentes_ok": ["sdn"],
            "fuentes_error": [],
        },
        "pep_adverse_media": {
            "posibles_coincidencias": [],
            "errores_fuente": [],
            "nota": "Sin indicios.",
        },
        "listas_actualizadas_al": "2026-06-09T00:00:00Z",
        "publicacion_ofac": "2026-06-08",
        "decision_oficial_cumplimiento": None,
        "requiere_revision_humana": True,
        "nota_legal": "Nota legal.",
    }


def _screening_con_alerta() -> dict:
    scr = _screening_sin_alertas()
    scr["ofac"]["riesgo"] = "alto"
    scr["ofac"]["coincidencias"] = [{
        "uid": "12345", "nombre": "JUAN PEREZ", "score": 97.0,
        "tipo_match": "nombre_principal", "lista": "SDN",
        "programas": ["SDGT"], "paises": ["CU"], "fuente": "https://ofac.treasury.gov",
    }]
    return scr


def _riesgo_bajo() -> dict:
    return {
        "cliente": {"numero": "001", "nombre": "Juan Perez"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "id_evaluacion": "eval-001",
        "vigencia_hasta": "2028-06-09T00:00:00+00:00",
        "riesgo": "Bajo",
        "total_ponderado": 15.0,
        "bloqueado": False,
        "motivo_bloqueo": None,
        "respuestas_no_encontradas": [],
        "detalle": [],
        "decision_oficial_cumplimiento": None,
        "requiere_revision_humana": True,
        "nota_legal": "Nota legal.",
        "nota": "Ayuda.",
    }


def _riesgo_alto() -> dict:
    r = _riesgo_bajo()
    r["riesgo"] = "Alto"
    r["total_ponderado"] = 82.0
    return r


def _fondos_sin_incongruencia() -> dict:
    return {
        "total_documentado_usd": "45000.00",
        "total_perfil_usd": "50000",
        "ratio_discrepancia": 0.9,
        "bandera_incongruencia": False,
        "umbral_usado": 2.0,
        "descripcion_bandera": "Sin incongruencia.",
        "documentos_analizados": ["/tmp/estado.pdf"],
        "montos_confirmados": [],          # vacío → no llama a cifrar()
        "timestamp_analisis": datetime.now(timezone.utc).isoformat(),
        "nota": "Nota.",
        "confirmado_por_investigador": True,
        "consistencia_perfil_origen": "Sin indicador.",
        "requiere_revision_humana": True,
    }


def _fondos_con_incongruencia() -> dict:
    f = _fondos_sin_incongruencia()
    f["bandera_incongruencia"] = True
    f["ratio_discrepancia"] = 4.5
    f["descripcion_bandera"] = "Posible incongruencia: ratio 4.5×"
    return f


def _fondos_no_confirmados() -> dict:
    f = _fondos_sin_incongruencia()
    f["confirmado_por_investigador"] = False
    return f


# ─── Caso 1: sin alertas ──────────────────────────────────────────────────────

class TestSinAlertas(unittest.TestCase):

    def setUp(self):
        # Parchear audit_registrar para no escribir al filesystem en tests
        patcher = patch("sanctions.validacion_cruzada.audit_registrar")
        self.mock_audit = patcher.start()
        self.addCleanup(patcher.stop)

    def test_estado_sin_alertas(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-001",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            analisis_fondos   =_fondos_sin_incongruencia(),
            owner_uid         ="uid-test-user",
        )
        self.assertEqual(legajo["estado"], "SIN_ALERTAS_AUTOMATICAS")
        self.assertEqual(legajo["alertas_detectadas"], [])

    def test_invariantes_siempre_presentes(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-001",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            owner_uid         ="uid-test-user",
        )
        self.assertIsNone(legajo["decision_oficial_cumplimiento"])
        self.assertTrue(legajo["requiere_revision_humana"])
        self.assertIn("nota_legal", legajo)
        self.assertIn("id_evaluacion", legajo)
        self.assertIn("vigencia_hasta", legajo)
        self.assertEqual(legajo["owner_uid"], "uid-test-user")
        self.assertEqual(legajo["id_cliente"], "CLIENTE-001")

    def test_audit_log_llamado(self):
        construir_legajo_unificado(
            id_cliente        ="CLIENTE-001",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            owner_uid         ="investigador-007",
            usuario_id        ="investigador-007",
        )
        self.mock_audit.assert_called_once()
        call_kwargs = self.mock_audit.call_args
        self.assertEqual(call_kwargs.kwargs.get("accion") or call_kwargs[1].get("accion", call_kwargs[0][0] if call_kwargs[0] else ""), "construir_legajo")

    def test_vigencia_bajo_es_730_dias(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-001",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            owner_uid         ="uid-test-user",
        )
        # vigencia_hasta debe ser aprox. 730 días en el futuro
        from datetime import timedelta
        vigencia = datetime.fromisoformat(legajo["vigencia_hasta"])
        ahora = datetime.now(timezone.utc)
        delta = vigencia - ahora
        self.assertGreater(delta.days, 720)
        self.assertLess(delta.days, 740)


# ─── Caso 2: con alertas ──────────────────────────────────────────────────────

class TestConAlertas(unittest.TestCase):

    def setUp(self):
        patcher = patch("sanctions.validacion_cruzada.audit_registrar")
        self.mock_audit = patcher.start()
        self.addCleanup(patcher.stop)

    def test_estado_alertas_por_riesgo_alto(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-002",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_alto(),
            owner_uid         ="uid-test-user",
        )
        self.assertEqual(legajo["estado"], "ALERTAS_PENDIENTES_REVISION")
        self.assertTrue(len(legajo["alertas_detectadas"]) >= 1)
        self.assertTrue(any("Alto" in a for a in legajo["alertas_detectadas"]))

    def test_estado_alertas_por_ofac(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-002",
            screening_ofac    =_screening_con_alerta(),
            evaluacion_riesgo =_riesgo_bajo(),
            owner_uid         ="uid-test-user",
        )
        self.assertEqual(legajo["estado"], "ALERTAS_PENDIENTES_REVISION")
        self.assertTrue(any("OFAC" in a for a in legajo["alertas_detectadas"]))

    def test_estado_alertas_por_fondos_confirmados(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-002",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_alto(),
            analisis_fondos   =_fondos_con_incongruencia(),
            owner_uid         ="uid-test-user",
        )
        self.assertEqual(legajo["estado"], "ALERTAS_PENDIENTES_REVISION")
        # Debe haber al menos alerta por fondos Y por riesgo alto
        self.assertGreaterEqual(len(legajo["alertas_detectadas"]), 2)

    def test_consistencia_perfil_evaluada(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-002",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_alto(),
            analisis_fondos   =_fondos_con_incongruencia(),
            owner_uid         ="uid-test-user",
        )
        cons = legajo["consistencia_perfil_origen"]
        self.assertTrue(cons["evaluado"])
        self.assertTrue(len(cons["indicadores"]) > 0)
        # Verificar que la nota de no-licitud está presente
        self.assertIn("no constituye prueba de licitud", cons["nota"])

    def test_vigencia_alto_es_180_dias(self):
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-002",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_alto(),
            owner_uid         ="uid-test-user",
        )
        from datetime import timedelta
        vigencia = datetime.fromisoformat(legajo["vigencia_hasta"])
        ahora = datetime.now(timezone.utc)
        delta = vigencia - ahora
        self.assertGreater(delta.days, 170)
        self.assertLess(delta.days, 190)


# ─── Caso 3: fondos no confirmados ───────────────────────────────────────────

class TestFondosNoConfirmados(unittest.TestCase):

    def setUp(self):
        patcher = patch("sanctions.validacion_cruzada.audit_registrar")
        self.mock_audit = patcher.start()
        self.addCleanup(patcher.stop)

    def test_fondos_no_confirmados_excluidos_del_legajo(self):
        """
        Si la extracción no fue confirmada por el investigador, analisis_fondos
        debe pasarse como None — los montos sin confirmar no participan en el cruce.
        """
        # El llamador (main_processor) es el que verifica la confirmación.
        # El test simula que el llamador ya filtró correctamente.
        legajo_sin_fondos = construir_legajo_unificado(
            id_cliente        ="CLIENTE-003",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            analisis_fondos   =None,   # no confirmado → no se pasa
            owner_uid         ="uid-test-user",
        )
        self.assertIsNone(legajo_sin_fondos["analisis_fondos"])
        cons = legajo_sin_fondos["consistencia_perfil_origen"]
        self.assertFalse(cons["evaluado"])
        self.assertIn("no disponible o no confirmado", cons["nota"])

    def test_fondos_con_incongruencia_no_confirmada_no_dispara_alerta(self):
        """
        Si fondos_task tiene bandera_incongruencia=True pero no fue confirmado,
        la alerta de fondos NO debe aparecer (se pasó None).
        """
        legajo = construir_legajo_unificado(
            id_cliente        ="CLIENTE-003",
            screening_ofac    =_screening_sin_alertas(),
            evaluacion_riesgo =_riesgo_bajo(),
            analisis_fondos   =None,
            owner_uid         ="uid-test-user",
        )
        self.assertEqual(legajo["estado"], "SIN_ALERTAS_AUTOMATICAS")
        fondos_alertas = [a for a in legajo["alertas_detectadas"] if "fondos" in a.lower()]
        self.assertEqual(fondos_alertas, [])


# ─── Caso 4: IDOR en _verificar_ownership_tareas ─────────────────────────────

class TestIDOR(unittest.TestCase):

    def _make_db(self, uid_propietario: str, task_id: str = "task-001"):
        """Mock de Firestore con una tarea que pertenece a uid_propietario."""
        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"uid": uid_propietario, "status": "COMPLETADO"}

        col_mock = MagicMock()
        col_mock.document.return_value.get.return_value = doc_mock

        db = MagicMock()
        db.collection.return_value = col_mock
        return db

    def test_misma_uid_aprobado(self):
        from main_processor import _verificar_ownership_tareas
        db = self._make_db("user-A")
        ok, motivo = _verificar_ownership_tareas(db, "user-A", "task-001", "task-002")
        self.assertTrue(ok)
        self.assertEqual(motivo, "")

    def test_uid_diferente_rechazado(self):
        from main_processor import _verificar_ownership_tareas
        db = self._make_db("user-B")   # tarea pertenece a user-B
        ok, motivo = _verificar_ownership_tareas(db, "user-A", "task-001")  # user-A intenta usarla
        self.assertFalse(ok)
        self.assertIn("IDOR", motivo)

    def test_task_id_vacio_ignorado(self):
        from main_processor import _verificar_ownership_tareas
        db = MagicMock()  # nunca debería consultarse
        ok, motivo = _verificar_ownership_tareas(db, "user-A", "", None, "")
        self.assertTrue(ok)
        db.collection.assert_not_called()

    def test_tarea_no_encontrada_rechazada(self):
        from main_processor import _verificar_ownership_tareas
        doc_mock = MagicMock()
        doc_mock.exists = False
        col_mock = MagicMock()
        col_mock.document.return_value.get.return_value = doc_mock
        db = MagicMock()
        db.collection.return_value = col_mock

        ok, motivo = _verificar_ownership_tareas(db, "user-A", "task-inexistente")
        self.assertFalse(ok)
        self.assertIn("no encontrada", motivo)


# ─── Vigencia configurable ────────────────────────────────────────────────────

class TestVigencia(unittest.TestCase):

    def test_alto_180_dias(self):
        from datetime import timedelta
        vigencia = datetime.fromisoformat(calcular_vigencia_hasta("Alto"))
        delta = vigencia - datetime.now(timezone.utc)
        self.assertGreater(delta.days, 170)
        self.assertLess(delta.days, 190)

    def test_moderado_365_dias(self):
        from datetime import timedelta
        vigencia = datetime.fromisoformat(calcular_vigencia_hasta("Moderado"))
        delta = vigencia - datetime.now(timezone.utc)
        self.assertGreater(delta.days, 355)
        self.assertLess(delta.days, 375)

    def test_bajo_730_dias(self):
        from datetime import timedelta
        vigencia = datetime.fromisoformat(calcular_vigencia_hasta("Bajo"))
        delta = vigencia - datetime.now(timezone.utc)
        self.assertGreater(delta.days, 720)
        self.assertLess(delta.days, 740)

    def test_config_override(self):
        cfg = {"vigencias_dias": {"Alto": 90, "Moderado": 180, "Bajo": 365}}
        from datetime import timedelta
        vigencia = datetime.fromisoformat(calcular_vigencia_hasta("Alto", cfg))
        delta = vigencia - datetime.now(timezone.utc)
        self.assertGreater(delta.days, 80)
        self.assertLess(delta.days, 100)


if __name__ == "__main__":
    unittest.main()
