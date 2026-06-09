"""
Detección de señales de alerta y posibles operaciones sospechosas.

PRINCIPIOS RECTORES (no negociables):
  1. Solo SUGIERE al investigador. Nunca toma decisiones ni reporta por sí solo.
  2. NUNCA reporta automáticamente a la UIAF — el ROS es decisión del sujeto obligado.
  3. NUNCA notifica, muestra ni expone estas señales al cliente (regla "no tipping off").
  4. Toda AlertaInterna tiene internal_only=True como invariante.
  5. Lenguaje de salida: "posible", "sugiere", "evaluar" — nunca afirmaciones categóricas.

Marco legal: Ley 19.574 (Art. 17 señales de alerta), Decreto 379/018.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

# Umbral de reporte SENACLAFT para efectivo / activos virtuales (configurable)
UMBRAL_REPORTE_USD: Decimal = Decimal("10000.00")

# Cantidad mínima de transacciones para disparar análisis de fraccionamiento
MIN_TXNS_SMURFING:  int = 3

# Ventana de días para agrupar transacciones en el análisis de smurfing
VENTANA_DIAS_SMURFING: int = 30


# ─── Estructuras de datos ──────────────────────────────────────────────────────

@dataclass
class Transaccion:
    """Transacción individual para análisis de patrones."""
    monto:       Decimal
    moneda:      str
    fecha:       date
    tipo:        str   # "ingreso" | "egreso"
    contraparte: str
    descripcion: str
    medio:       str   # "efectivo" | "transferencia" | "cripto" | "cheque" | "otro"


@dataclass
class AlertaInterna:
    """
    Señal de alerta de uso ESTRICTAMENTE INTERNO.
    internal_only=True es un invariante — nunca debe modificarse a False.
    No incluir en respuestas al cliente, correos automáticos ni vistas públicas.
    """
    tipo:            str
    descripcion:     str
    evidencia:       list[str]
    sugerencia:      str
    fecha_deteccion: str
    internal_only:   bool = True   # invariante — ver docstring


# ─── Detectores de patrones ───────────────────────────────────────────────────

def _detectar_smurfing(
    transacciones: list[Transaccion],
    umbral: Decimal = UMBRAL_REPORTE_USD,
    ventana_dias: int = VENTANA_DIAS_SMURFING,
) -> AlertaInterna | None:
    """
    Detecta fraccionamiento de pagos (smurfing):
    múltiples transacciones en efectivo o cripto, cada una bajo el umbral,
    pero cuya suma en una ventana de días supera el umbral de reporte.
    """
    candidatas = [
        t for t in transacciones
        if t.medio in ("efectivo", "cripto")
        and Decimal("1000") < t.monto < umbral
    ]
    if len(candidatas) < MIN_TXNS_SMURFING:
        return None

    fechas = sorted({t.fecha for t in candidatas})
    for fecha_inicio in fechas:
        ventana = [
            t for t in candidatas
            if 0 <= (t.fecha - fecha_inicio).days <= ventana_dias
        ]
        if len(ventana) < MIN_TXNS_SMURFING:
            continue
        suma = sum(t.monto for t in ventana)
        if suma < umbral:
            continue

        moneda_ref = ventana[0].moneda
        evidencia = [
            f"{t.fecha.isoformat()} | {t.moneda} {t.monto:.2f} | {t.contraparte or 'N/D'} | {t.medio}"
            for t in ventana
        ]
        return AlertaInterna(
            tipo="fraccionamiento_smurfing",
            descripcion=(
                f"{len(ventana)} transacciones en {ventana_dias} días suman "
                f"{moneda_ref} {suma:.2f}, superando el umbral de reporte de {umbral}. "
                f"Patrón sugiere posible fraccionamiento para evadir reporte obligatorio."
            ),
            evidencia=evidencia,
            sugerencia=(
                "Posible operación sospechosa — evaluar presentación de ROS ante UIAF. "
                "Solicitar justificación de la operación al cliente antes de proceder."
            ),
            fecha_deteccion=datetime.utcnow().isoformat() + "Z",
        )
    return None


def _detectar_activos_virtuales(transacciones: list[Transaccion]) -> AlertaInterna | None:
    """
    Detecta uso de criptoactivos.
    Ley 20.469 (regulación activos virtuales) requiere DDI y documentación de fuente.
    """
    cripto = [t for t in transacciones if t.medio == "cripto"]
    if not cripto:
        return None
    total = sum(t.monto for t in cripto)
    moneda_ref = cripto[0].moneda
    evidencia = [
        f"{t.fecha.isoformat()} | {t.moneda} {t.monto:.2f} | {t.contraparte or 'N/D'}"
        for t in cripto
    ]
    return AlertaInterna(
        tipo="activos_virtuales",
        descripcion=(
            f"Se detectaron {len(cripto)} transacción(es) con activos virtuales "
            f"por un total estimado de {moneda_ref} {total:.2f}. "
            f"Ley 20.469 requiere Debida Diligencia Intensificada."
        ),
        evidencia=evidencia,
        sugerencia=(
            "Aplicar DDI — solicitar origen de criptoactivos, billetera fuente y "
            "respaldo documental del proveedor de servicios de activos virtuales (PSAV). "
            "Evaluar ROS si el origen no puede justificarse."
        ),
        fecha_deteccion=datetime.utcnow().isoformat() + "Z",
    )


def _detectar_rechazo_informacion(campos_faltantes: list[str]) -> AlertaInterna | None:
    """
    Detecta negativa o incapacidad de entregar información requerida.
    Evalúa cuántos campos críticos no fueron completados por el cliente.
    """
    keywords_criticos = (
        "dni", "rut", "declaraci", "fiscal", "origen", "domicilio",
        "beneficiario", "actividad", "patrimonio",
    )
    criticos = [
        c for c in campos_faltantes
        if any(k in c.lower() for k in keywords_criticos)
    ]
    if len(criticos) < 2:
        return None
    return AlertaInterna(
        tipo="rechazo_informacion",
        descripcion=(
            f"El cliente no aportó {len(criticos)} campo(s) crítico(s) "
            f"requeridos para la debida diligencia. "
            f"Posible renuencia a proveer información (Art. 17, Ley 19.574)."
        ),
        evidencia=criticos,
        sugerencia=(
            "Requerir documentación faltante por escrito con plazo. "
            "Si persiste la omisión, evaluar suspensión de la operación y presentación de ROS."
        ),
        fecha_deteccion=datetime.utcnow().isoformat() + "Z",
    )


def _detectar_documentos_invalidos(anomalias: list[str]) -> AlertaInterna | None:
    """
    Recibe anomalías detectadas por el validador de documentos
    (ej: "Pasaporte vencido", "Imagen ilegible", "Datos inconsistentes con formulario").
    """
    if not anomalias:
        return None
    return AlertaInterna(
        tipo="documento_invalido_o_sospechoso",
        descripcion=(
            f"Se detectaron {len(anomalias)} anomalía(s) en documento(s) "
            f"presentados por el cliente que requieren revisión."
        ),
        evidencia=anomalias,
        sugerencia=(
            "Solicitar documento original válido y vigente. "
            "Si el cliente entrega documentación alterada o ilegible de forma reiterada, "
            "evaluar ROS ante UIAF."
        ),
        fecha_deteccion=datetime.utcnow().isoformat() + "Z",
    )


# ─── API pública ──────────────────────────────────────────────────────────────

def analizar_señales(
    transacciones: list[Transaccion] | None = None,
    campos_faltantes: list[str] | None = None,
    anomalias_documentos: list[str] | None = None,
    umbral_fraccionamiento: Decimal = UMBRAL_REPORTE_USD,
) -> dict[str, Any]:
    """
    Ejecuta todos los detectores de señales de alerta sobre el legajo del cliente.

    AVISO OBLIGATORIO — NO TIPPING OFF:
      El resultado de esta función es ESTRICTAMENTE CONFIDENCIAL.
      No incluir en: respuestas al cliente, emails automáticos, vistas del portal cliente,
      logs accesibles desde la sesión del cliente, ni notificaciones de cualquier tipo.
      Ver Ley 19.574, Art. 20 (prohibición de divulgación).

    Args:
        transacciones:          lista de Transaccion del cliente (puede ser None)
        campos_faltantes:       campos del formulario que el cliente omitió
        anomalias_documentos:   problemas detectados en documentos subidos
        umbral_fraccionamiento: monto en USD que activa análisis de smurfing

    Returns:
        {
          "alertas":     lista de dicts con tipo, descripción, evidencia, sugerencia
          "hay_alertas": bool
          "nota_ros":    aviso para el investigador
        }
        Todas las alertas tienen internal_only=True.
    """
    alertas: list[AlertaInterna] = []

    txns      = transacciones      or []
    faltantes = campos_faltantes   or []
    anomalias = anomalias_documentos or []

    for detector in [
        lambda: _detectar_smurfing(txns, umbral=umbral_fraccionamiento),
        lambda: _detectar_activos_virtuales(txns),
        lambda: _detectar_rechazo_informacion(faltantes),
        lambda: _detectar_documentos_invalidos(anomalias),
    ]:
        resultado = detector()
        if resultado:
            alertas.append(resultado)

    return {
        "alertas": [
            {
                "tipo":          a.tipo,
                "descripcion":   a.descripcion,
                "evidencia":     a.evidencia,
                "sugerencia":    a.sugerencia,
                "fecha":         a.fecha_deteccion,
                "internal_only": True,   # reforzar en cada salida
            }
            for a in alertas
        ],
        "hay_alertas": bool(alertas),
        "nota_ros": (
            "⚠ AVISO INTERNO — NO TIPPING OFF: estas señales son estrictamente "
            "confidenciales. No notificar al cliente bajo ninguna circunstancia. "
            "La decisión de presentar un ROS es exclusiva del sujeto obligado. "
            "AHC Intelligence / SENACLAFT — Ley 19.574, Art. 20."
        ),
    }
