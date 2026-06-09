"""
Ensambla el reporte JSON final de screening KYC/AML.
El reporte es el único output del módulo hacia sistemas externos.
Sin claims legales categóricos. Toda afirmación incluye score y fuente.
"""

import json
from datetime import datetime
from typing import Any

from .matcher import Coincidencia
from .ofac_loader import OFACDatabase

_NOTA_LEGAL_OFAC = (
    "Screening automatizado de apoyo. Los resultados son indicadores de priorización "
    "y no constituyen determinación legal de ningún tipo. "
    "La determinación final es exclusiva del oficial de cumplimiento humano. "
    "AHC Intelligence — SENACLAFT / Ley 19.574."
)


# ─── Nivel de riesgo OFAC ─────────────────────────────────────────────────────

def _riesgo_ofac(coincidencias: list[Coincidencia]) -> str:
    """
    Determina el nivel de riesgo basado en score y tipo de coincidencia OFAC.

    - "alto":    score >= 95 en nombre principal, o score >= 90 en nombre principal
                 combinado con programa de alto riesgo (SDGT, SDNTK, etc.)
    - "revisar": cualquier coincidencia sobre umbral que no llegue a "alto"
    - "ninguno": sin coincidencias por encima del umbral configurado

    Esta función no toma decisiones legales; solo categoriza para que el
    oficial de cumplimiento priorice la revisión.
    """
    if not coincidencias:
        return "ninguno"

    mejor = coincidencias[0]  # ya vienen ordenadas por score desc

    programas_alto_riesgo = {"SDGT", "SDNTK", "DPRK", "IRAN", "RUSSIA-EO14024"}
    es_programa_critico = bool(set(mejor.programas) & programas_alto_riesgo)

    if mejor.score >= 95:
        return "alto"
    if mejor.tipo_match == "nombre_principal" and mejor.score >= 90 and es_programa_critico:
        return "alto"
    return "revisar"


# ─── API pública ──────────────────────────────────────────────────────────────

def construir_reporte(
    nombre_consultado: str,
    coincidencias_ofac: list[Coincidencia],
    resultado_pep: dict[str, Any],
    db: OFACDatabase,
) -> dict[str, Any]:
    """
    Construye el reporte estructurado completo de screening.
    Formato diseñado para ser guardado en Firestore y mostrado en el frontend AHC.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    items_ofac = [
        {
            "uid":             c.uid,
            "nombre":          c.nombre_en_lista,
            "nombre_buscado":  c.nombre_consultado,
            "score":           round(c.score, 2),
            "tipo_match":      c.tipo_match,
            "categoria_alias": c.categoria_alias,
            "lista":           c.lista_origen,
            "programas":       c.programas,
            "paises":          c.paises,
            "fuente":          c.fuente_url,
        }
        for c in coincidencias_ofac
    ]

    return {
        "consulta":   nombre_consultado,
        "timestamp":  timestamp,
        "ofac": {
            "coincidencias":   items_ofac,
            "riesgo":          _riesgo_ofac(coincidencias_ofac),
            "fuentes_ok":      db.fuentes_ok,
            "fuentes_error":   db.fuentes_error,
        },
        "pep_adverse_media":             resultado_pep,
        "listas_actualizadas_al":        db.descargado_el or "desconocido",
        "publicacion_ofac":              db.publicado_el  or "desconocido",
        "decision_oficial_cumplimiento": None,
        "requiere_revision_humana":      True,
        "nota_legal":                    _NOTA_LEGAL_OFAC,
    }


def reporte_a_json(reporte: dict[str, Any], indent: int = 2) -> str:
    """Serializa el reporte a JSON legible con soporte de caracteres UTF-8."""
    return json.dumps(reporte, indent=indent, ensure_ascii=False, default=str)
