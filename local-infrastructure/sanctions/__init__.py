from .ofac_loader import actualizar_listas, OFACDatabase, OFACEntry
from .matcher import buscar_en_ofac, Coincidencia, UMBRAL_DEFECTO
from .pep_screener import screening_pep_adverse
from .report_builder import construir_reporte, reporte_a_json
from .audit_log import registrar as audit_registrar, verificar_integridad, buscar_registros
from .risk_matrix import MatrizRiesgo, version_activa
from .suspicious_activity import analizar_señales, Transaccion, AlertaInterna
from .funds_analyzer import extraer_documento, analizar_fondos, PerfilCliente, ExtraccionDocumento
from .legajo_exporter import exportar_legajo, LegajoDatos, ResultadoExportacion
from .validacion_cruzada import construir_legajo_unificado, calcular_vigencia_hasta, purgar_legajos_expirados
from .crypto import cifrar, descifrar, KMSNotConfiguredError

__all__ = [
    # Módulos 1 y 2 — OFAC + PEP
    "actualizar_listas", "OFACDatabase", "OFACEntry",
    "buscar_en_ofac", "Coincidencia", "UMBRAL_DEFECTO",
    "screening_pep_adverse",
    "construir_reporte", "reporte_a_json",
    # Módulo 3 — Origen de fondos
    "extraer_documento", "analizar_fondos", "PerfilCliente", "ExtraccionDocumento",
    # Módulo 5 — Matriz de riesgo
    "MatrizRiesgo", "version_activa",
    # Módulo 6 — Señales de alerta
    "analizar_señales", "Transaccion", "AlertaInterna",
    # Módulo 7 — Legajo PDF
    "exportar_legajo", "LegajoDatos", "ResultadoExportacion",
    # Módulo 8 — Legajo unificado + cruce KYC/AML
    "construir_legajo_unificado", "calcular_vigencia_hasta", "purgar_legajos_expirados",
    # Cifrado (Ley 18.331)
    "cifrar", "descifrar", "KMSNotConfiguredError",
    # Audit log (transversal)
    "audit_registrar", "verificar_integridad", "buscar_registros",
]
