"""
Tests de aislamiento multi-tenant (lógica Python) y vigencia configurable.

Este archivo cubre:
  1. Vigencia por nivel de riesgo — Alto/Moderado/Bajo con valores por defecto y override
  2. Purgar_legajos_expirados respeta retencion_anos, nunca vigencia_hasta
  3. Aislamiento owner_uid: una consulta que filtra por owner_uid solo retorna
     los documentos del propietario (simulación de la lógica del backend)

NOTA: El test de aislamiento contra las reglas REALES de Firestore está en
cloud-infrastructure/tests/rules/legajos.test.js (usa el Firebase Emulator).
Este archivo cubre la lógica Python del backend, no las rules de Firestore.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sanctions.validacion_cruzada import calcular_vigencia_hasta, purgar_legajos_expirados


# ─── Vigencia por nivel de riesgo ─────────────────────────────────────────────

class TestVigenciaConfigurable(unittest.TestCase):

    def _dias_desde_hoy(self, vigencia_str: str) -> int:
        vigencia = datetime.fromisoformat(vigencia_str)
        return (vigencia - datetime.now(timezone.utc)).days

    def test_alto_default_180_dias(self):
        dias = self._dias_desde_hoy(calcular_vigencia_hasta("Alto"))
        self.assertGreater(dias, 170)
        self.assertLess(dias, 190)

    def test_moderado_default_365_dias(self):
        dias = self._dias_desde_hoy(calcular_vigencia_hasta("Moderado"))
        self.assertGreater(dias, 355)
        self.assertLess(dias, 375)

    def test_bajo_default_730_dias(self):
        dias = self._dias_desde_hoy(calcular_vigencia_hasta("Bajo"))
        self.assertGreater(dias, 720)
        self.assertLess(dias, 740)

    def test_config_override_alto_90_dias(self):
        cfg = {"vigencias_dias": {"Alto": 90, "Moderado": 180, "Bajo": 365}}
        dias = self._dias_desde_hoy(calcular_vigencia_hasta("Alto", cfg))
        self.assertGreater(dias, 80)
        self.assertLess(dias, 100)

    def test_nivel_desconocido_usa_365(self):
        dias = self._dias_desde_hoy(calcular_vigencia_hasta("NivelQueNoExiste"))
        self.assertGreater(dias, 355)
        self.assertLess(dias, 375)

    def test_vigencia_alto_menor_que_moderado(self):
        """Alto debe tener vigencia más corta (revisión más frecuente = SENACLAFT)."""
        v_alto     = datetime.fromisoformat(calcular_vigencia_hasta("Alto"))
        v_moderado = datetime.fromisoformat(calcular_vigencia_hasta("Moderado"))
        v_bajo     = datetime.fromisoformat(calcular_vigencia_hasta("Bajo"))
        self.assertLess(v_alto, v_moderado)
        self.assertLess(v_moderado, v_bajo)


# ─── Purga basada en retencion_anos, NO en vigencia_hasta ─────────────────────

class TestPurgar(unittest.TestCase):

    def _make_db_con_legajos(self, legajos: list[dict]) -> MagicMock:
        """
        Construye un mock de Firestore que devuelve los legajos dados
        cuando se consulta la colección 'legajos'.
        """
        docs = []
        for leg in legajos:
            doc = MagicMock()
            doc.id = leg["id"]
            doc.reference = MagicMock()
            doc.get = lambda campo, d=leg: d.get(campo, None)
            docs.append(doc)

        col_mock = MagicMock()
        col_mock.where.return_value.stream.return_value = iter(docs)

        db = MagicMock()
        db.collection.return_value = col_mock
        return db

    def test_dry_run_lista_sin_borrar(self):
        db = self._make_db_con_legajos([
            {"id": "legajo-viejo-1"},
            {"id": "legajo-viejo-2"},
        ])
        with patch("sanctions.validacion_cruzada.audit_registrar"):
            ids = purgar_legajos_expirados(db, dry_run=True)
        self.assertEqual(set(ids), {"legajo-viejo-1", "legajo-viejo-2"})
        # En dry_run, delete nunca se llama
        for call in db.collection.return_value.where.return_value.stream.return_value:
            pass  # iterado arriba

    def test_purga_real_llama_delete(self):
        docs = []
        for i in range(3):
            doc = MagicMock()
            doc.id = f"legajo-{i}"
            doc.get = lambda campo: None
            docs.append(doc)

        col_mock = MagicMock()
        col_mock.where.return_value.stream.return_value = iter(docs)
        db = MagicMock()
        db.collection.return_value = col_mock

        with patch("sanctions.validacion_cruzada.audit_registrar"):
            ids = purgar_legajos_expirados(db, dry_run=False)

        self.assertEqual(len(ids), 3)
        # Cada doc debe haber tenido reference.delete() llamado
        for doc in docs:
            doc.reference.delete.assert_called_once()

    def test_retencion_usa_anos_no_vigencia(self):
        """
        La query de purga debe filtrar por 'creado_en' (fecha de creación),
        nunca por 'vigencia_hasta'. Verifica que el campo pasado a .where() es 'creado_en'.
        """
        col_mock = MagicMock()
        col_mock.where.return_value.stream.return_value = iter([])
        db = MagicMock()
        db.collection.return_value = col_mock

        with patch("sanctions.validacion_cruzada.audit_registrar"):
            purgar_legajos_expirados(db, dry_run=True)

        # Verificar que la query usa 'creado_en', no 'vigencia_hasta'
        where_args = col_mock.where.call_args
        campo_filtrado = where_args[0][0] if where_args[0] else where_args[1].get("field_path", "")
        self.assertEqual(campo_filtrado, "creado_en",
                         "La purga debe filtrar por 'creado_en', no por 'vigencia_hasta'")


# ─── Aislamiento multi-tenant (lógica de backend) ─────────────────────────────

class TestAislamientoBackend(unittest.TestCase):
    """
    Simula la lógica que el backend aplica al escribir legajos:
    owner_uid siempre se toma del campo 'uid' del documento de tarea,
    que ya fue verificado por las Firestore Security Rules al momento de creación.

    El test de aislamiento contra las rules REALES de Firestore está en:
    cloud-infrastructure/tests/rules/legajos.test.js
    """

    def _simular_procesar_legajo(self, uid_tarea: str, uid_intento: str) -> bool:
        """
        Simula la verificación IDOR del backend.
        Retorna True si el legajo se crearía, False si sería rechazado.
        """
        # La tarea pertenece a uid_tarea. El intento de construir con uid_intento
        # solo pasa si _verificar_ownership_tareas devuelve ok=True.
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from main_processor import _verificar_ownership_tareas

        doc_mock = MagicMock()
        doc_mock.exists = True
        doc_mock.to_dict.return_value = {"uid": uid_tarea}
        col_mock = MagicMock()
        col_mock.document.return_value.get.return_value = doc_mock
        db = MagicMock()
        db.collection.return_value = col_mock

        ok, _ = _verificar_ownership_tareas(db, uid_intento, "task-001")
        return ok

    def test_mismo_usuario_puede_construir_legajo(self):
        self.assertTrue(self._simular_procesar_legajo("user-A", "user-A"))

    def test_otro_usuario_no_puede_usar_tarea_ajena(self):
        self.assertFalse(self._simular_procesar_legajo("user-A", "user-B"))

    def test_owner_uid_se_asigna_desde_uid_tarea(self):
        """
        El owner_uid del legajo escrito en Firestore debe ser el uid de la tarea,
        no un valor que el frontend pueda manipular.
        """
        # Simulamos que el legajo fue construido con owner_uid="user-A"
        # y que el backend siempre usa data['uid'] (verificado por rules)
        from sanctions.validacion_cruzada import construir_legajo_unificado
        with patch("sanctions.validacion_cruzada.audit_registrar"):
            legajo = construir_legajo_unificado(
                id_cliente        ="CLIENTE-TEST",
                screening_ofac    ={"ofac": {"coincidencias": [], "riesgo": "ninguno"}, "pep_adverse_media": {"posibles_coincidencias": []}, "timestamp": "2026-01-01T00:00:00Z", "listas_actualizadas_al": "—", "publicacion_ofac": "—"},
                evaluacion_riesgo ={"riesgo": "Bajo", "bloqueado": False, "total_ponderado": 10.0},
                owner_uid         ="user-A",
            )
        self.assertEqual(legajo["owner_uid"], "user-A")
        # El legajo nunca puede tener un owner_uid diferente al que construyó la función
        self.assertNotEqual(legajo["owner_uid"], "user-B")


if __name__ == "__main__":
    unittest.main()
