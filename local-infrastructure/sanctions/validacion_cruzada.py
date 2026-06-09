"""
Motor de cruce KYC/AML — Legajo de Cumplimiento unificado.

Combina screening OFAC/PEP + evaluación de riesgo + análisis de fondos (si confirmado)
en un único documento estructurado con identidad duradera del cliente separada de la
evaluación puntual.

INVARIANTES (no negociables):
  - decision_oficial_cumplimiento: siempre None. El sistema no decide.
  - requiere_revision_humana:      siempre True.
  - consistencia_perfil_origen:    es un indicador, nunca un veredicto.
  - Montos no confirmados (confirmado_por_investigador=False) nunca participan en el cruce.
  - Cada construcción se registra en el audit_log append-only.

Datos sensibles:
  Si analisis_fondos contiene montos_confirmados, se cifran con AES-256-GCM vía
  envelope encryption (KMS). Si KMS no está configurado y hay datos sensibles,
  construir_legajo_unificado() lanza KMSNotConfiguredError — nunca cae silenciosamente
  a texto plano.

Marco legal: SENACLAFT, Ley 19.574, Ley 18.331 (protección de datos).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .audit_log import registrar as audit_registrar

VIGENCIA_CONFIG_PATH = Path(__file__).parent / "vigencia_config.json"

_NOTA_LEGAL = (
    "Este legajo es un instrumento de apoyo para el oficial de cumplimiento. "
    "No constituye determinación legal, habilitación de operación, ni decisión de ningún tipo. "
    "La determinación final es exclusiva y responsabilidad del oficial de cumplimiento humano. "
    "AHC Intelligence — SENACLAFT / Ley 19.574 / Ley 18.331."
)

_DEFAULTS_VIGENCIA = {"Alto": 180, "Moderado": 365, "Bajo": 730}


# ─── Vigencia ─────────────────────────────────────────────────────────────────

def _cargar_vigencia_config() -> dict:
    try:
        return json.loads(VIGENCIA_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"vigencias_dias": _DEFAULTS_VIGENCIA, "retencion_anos": 5}


def calcular_vigencia_hasta(nivel_riesgo: str, cfg: dict | None = None) -> str:
    """
    Calcula vigencia_hasta según el nivel de riesgo.
    Configurable vía vigencia_config.json.
    Alto=180d, Moderado=365d, Bajo=730d (valores por defecto).
    """
    if cfg is None:
        cfg = _cargar_vigencia_config()
    dias_map = cfg.get("vigencias_dias", _DEFAULTS_VIGENCIA)
    dias = dias_map.get(nivel_riesgo, 365)
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


# ─── Estado y alertas ─────────────────────────────────────────────────────────

def _calcular_estado(
    evaluacion_riesgo: dict,
    screening_ofac: dict,
    analisis_fondos: dict | None,
) -> tuple[str, list[str]]:
    """
    Determina estado e indicadores de alerta.

    Estado es "ALERTAS_PENDIENTES_REVISION" si al menos una condición se activa.
    Estado es "SIN_ALERTAS_AUTOMATICAS" si ninguna condición se activa.
    Ninguno de los dos es un veredicto — ambos requieren revisión humana.
    """
    alertas: list[str] = []

    # Bloqueo automático por jurisdicción o parámetro prohibido
    if evaluacion_riesgo.get("bloqueado"):
        motivo = evaluacion_riesgo.get("motivo_bloqueo", "Motivo no especificado")
        alertas.append(f"Bloqueo automático en matriz de riesgo: {motivo}")

    # Puntaje en tramo Alto (sin bloqueo)
    elif evaluacion_riesgo.get("riesgo") == "Alto":
        puntaje = evaluacion_riesgo.get("total_ponderado", "—")
        alertas.append(f"Puntaje de riesgo en tramo Alto (ponderado: {puntaje})")

    # Indicador OFAC
    indicador_ofac = screening_ofac.get("ofac", {}).get("riesgo", "ninguno")
    if indicador_ofac in ("alto", "revisar"):
        n = len(screening_ofac.get("ofac", {}).get("coincidencias", []))
        alertas.append(
            f"Indicador OFAC: {indicador_ofac} — {n} coincidencia(s) sobre umbral configurado"
        )

    # PEP con confianza alta
    pep = screening_ofac.get("pep_adverse_media", {})
    posibles_pep = pep.get("posibles_coincidencias", [])
    alta_confianza = [p for p in posibles_pep if p.get("confianza") == "alto"]
    if alta_confianza:
        alertas.append(
            f"Indicador PEP/adverse media: {len(alta_confianza)} indicio(s) de confianza alta en fuentes abiertas"
        )

    # Fondos — solo si fase 2 confirmada (analisis_fondos no None)
    if analisis_fondos and analisis_fondos.get("bandera_incongruencia"):
        desc = analisis_fondos.get("descripcion_bandera", "")[:150]
        alertas.append(f"Indicador de fondos: {desc}")

    estado = "ALERTAS_PENDIENTES_REVISION" if alertas else "SIN_ALERTAS_AUTOMATICAS"
    return estado, alertas


# ─── Consistencia perfil/origen ───────────────────────────────────────────────

def _evaluar_consistencia_perfil(
    evaluacion_riesgo: dict,
    analisis_fondos: dict | None,
) -> dict:
    """
    Indicador de consistencia numérica entre fondos documentados y actividad declarada.

    Este es un INDICADOR para el investigador, nunca un veredicto.
    La nota explícita advierte que coincidir números no constituye prueba de licitud.
    """
    nota_no_licitud = (
        "IMPORTANTE: la coincidencia entre el volumen documentado y la actividad declarada "
        "no constituye prueba de licitud de los fondos. "
        "La determinación de congruencia o incongruencia es responsabilidad exclusiva "
        "del oficial de cumplimiento, quien debe considerar el contexto completo del cliente."
    )

    if not analisis_fondos:
        return {
            "evaluado": False,
            "indicadores": [],
            "nota": (
                "Análisis de fondos no disponible o no confirmado por el investigador. "
                + nota_no_licitud
            ),
        }

    indicadores = []

    # Congruencia numérica volumétrica
    if analisis_fondos.get("bandera_incongruencia"):
        indicadores.append({
            "tipo":      "CONGRUENCIA_NUMERICA",
            "resultado": "VOLUMEN_DOCUMENTADO_SUPERA_UMBRAL",
            "detalle":   (analisis_fondos.get("descripcion_bandera", "") or "")[:250],
        })
    else:
        ratio = analisis_fondos.get("ratio_discrepancia", 0)
        umbral = analisis_fondos.get("umbral_usado", "—")
        indicadores.append({
            "tipo":      "CONGRUENCIA_NUMERICA",
            "resultado": "SIN_INDICADOR_DE_INCONGRUENCIA_AUTOMATICA",
            "detalle":   f"Ratio volumen/perfil: {ratio:.2f}× (umbral: {umbral}×). "
                         "La ausencia de este indicador no implica conformidad.",
        })

    # Nivel de riesgo del perfil declarado
    nivel = evaluacion_riesgo.get("riesgo", "Desconocido")
    indicadores.append({
        "tipo":      "NIVEL_RIESGO_PERFIL_DECLARADO",
        "resultado": nivel,
        "detalle":   f"El perfil declarado calificó como riesgo {nivel} en la matriz SENACLAFT.",
    })

    return {
        "evaluado":    True,
        "indicadores": indicadores,
        "nota":        nota_no_licitud,
    }


# ─── API pública ──────────────────────────────────────────────────────────────

def construir_legajo_unificado(
    id_cliente: str,
    screening_ofac: dict,
    evaluacion_riesgo: dict,
    analisis_fondos: dict | None = None,
    *,
    owner_uid: str,
    usuario_id: str = "sistema",
    ip_addr: str | None = None,
    kms_client: Any = None,
) -> dict[str, Any]:
    """
    Construye el Legajo de Cumplimiento unificado.

    Args:
        id_cliente:       identificador permanente del cliente (no cambia entre evaluaciones).
        screening_ofac:   output de construir_reporte() — OFAC + PEP combinados.
        evaluacion_riesgo: output de MatrizRiesgo.evaluar().
        analisis_fondos:  output de analizar_fondos(), SOLO si confirmado_por_investigador=True.
                          Si la extracción no fue confirmada por el investigador, pasar None.
        owner_uid:        UID de Firebase del usuario propietario (para AAD del cifrado y audit).
        usuario_id:       identificador del investigador (para audit log).
        ip_addr:          IP del cliente si disponible.
        kms_client:       cliente KMS inyectable (para tests).

    Returns:
        dict del legajo unificado listo para Firestore.
        decision_oficial_cumplimiento es siempre None.
        requiere_revision_humana es siempre True.

    Raises:
        KMSNotConfiguredError si analisis_fondos tiene montos_confirmados y KMS no está configurado.
    """
    cfg = _cargar_vigencia_config()
    nivel_riesgo = evaluacion_riesgo.get("riesgo", "Moderado")
    id_evaluacion = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    vigencia_hasta = calcular_vigencia_hasta(nivel_riesgo, cfg)

    # Cifrar datos sensibles de fondos antes de incluirlos en el legajo
    datos_sensibles_cifrados = None
    analisis_para_legajo = None

    if analisis_fondos:
        montos = analisis_fondos.get("montos_confirmados", [])
        if montos:
            from .crypto import cifrar  # import local para no fallar al importar el módulo
            payload = json.dumps(
                {"montos_confirmados": montos},
                ensure_ascii=False,
                default=str,
            )
            datos_sensibles_cifrados = cifrar(
                payload, id_evaluacion, owner_uid, kms_client=kms_client
            )
            analisis_para_legajo = {
                **{k: v for k, v in analisis_fondos.items() if k != "montos_confirmados"},
                "montos_confirmados": "[DATOS CIFRADOS — ver campo datos_sensibles_cifrados]",
            }
        else:
            analisis_para_legajo = analisis_fondos

    estado, alertas = _calcular_estado(evaluacion_riesgo, screening_ofac, analisis_fondos)
    consistencia = _evaluar_consistencia_perfil(evaluacion_riesgo, analisis_fondos)

    legajo: dict[str, Any] = {
        # Identidad duradera vs. evaluación puntual
        "id_cliente":                    id_cliente,
        "id_evaluacion":                 id_evaluacion,
        "timestamp_evaluacion":          timestamp,
        "vigencia_hasta":                vigencia_hasta,
        # Postura legal — invariantes
        "estado":                        estado,
        "decision_oficial_cumplimiento": None,
        "requiere_revision_humana":      True,
        # Propietario (multi-tenant)
        "owner_uid":                     owner_uid,
        # Evidencia
        "screening_ofac":                screening_ofac,
        "evaluacion_riesgo":             evaluacion_riesgo,
        "analisis_fondos":               analisis_para_legajo,
        # Indicadores
        "consistencia_perfil_origen":    consistencia,
        "alertas_detectadas":            alertas,
        # Datos sensibles cifrados
        "datos_sensibles_cifrados":      datos_sensibles_cifrados,
        # Marco legal transversal
        "nota_legal":                    _NOTA_LEGAL,
    }

    # Registro obligatorio en audit log append-only
    audit_registrar(
        accion    ="construir_legajo",
        usuario_id=usuario_id,
        recurso   =f"{id_cliente}:{id_evaluacion}",
        detalles  ={
            "estado":              estado,
            "nivel_riesgo":        nivel_riesgo,
            "n_alertas":           len(alertas),
            "fondos_incluidos":    analisis_para_legajo is not None,
            "datos_cifrados":      datos_sensibles_cifrados is not None,
            "vigencia_hasta":      vigencia_hasta,
        },
        ip_addr=ip_addr,
    )

    return legajo


def purgar_legajos_expirados(db: Any, dry_run: bool = True) -> list[str]:
    """
    Elimina legajos cuya fecha de creación supera el período de retención configurado.

    La vigencia_hasta indica cuándo RE-SCREENEAR, no cuándo eliminar.
    La eliminación se basa en 'creado_en' + retencion_anos del config.

    Args:
        db:       cliente Firestore (firebase_admin.firestore.client()).
        dry_run:  si True, solo lista los IDs a purgar sin eliminar (default).

    Returns:
        Lista de legajo IDs purgados (o candidatos si dry_run=True).
    """
    cfg = _cargar_vigencia_config()
    anos = cfg.get("retencion_anos", 5)
    corte = datetime.now(timezone.utc) - timedelta(days=anos * 365)

    candidatos = (
        db.collection("legajos")
        .where("creado_en", "<", corte)
        .stream()
    )

    ids_purgados: list[str] = []
    for doc in candidatos:
        ids_purgados.append(doc.id)
        if not dry_run:
            doc.reference.delete()
            audit_registrar(
                accion    ="purgar_legajo",
                usuario_id="sistema_retencion",
                recurso   =doc.id,
                detalles  ={"retencion_anos": anos, "creado_en": str(doc.get("creado_en"))},
            )

    return ids_purgados
