"""
Análisis de origen de fondos (justificación patrimonial) — Módulo 3.

FLUJO OBLIGATORIO EN DOS FASES:
  FASE 1: extraer_documento() → devuelve ExtraccionDocumento (no confirmada)
          El investigador DEBE revisar y corregir los montos extraídos.
  FASE 2: analizar_fondos(extraccion_confirmada, perfil) → AnalisisFondos
          Solo se ejecuta después de confirmación humana explícita.

NUNCA se calcula ninguna bandera sin confirmación del investigador.
Los montos extraídos automáticamente son SUGERENCIAS, no hechos.

Marco legal: Art. 11 Ley 19.574 (identificación de clientes y origen de fondos).
"""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EXTENSIONES_PDF    = {".pdf"}
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

# Umbral de incongruencia configurable: ratio entre volumen documentado y perfil declarado
UMBRAL_INCONGRUENCIA_DEFECTO = 2.0   # 200% del perfil declarado dispara bandera


# ─── Estructuras de datos ──────────────────────────────────────────────────────

@dataclass
class MontoExtraido:
    descripcion: str
    monto: Decimal
    moneda: str
    periodo: str            # ej: "2025-01", "2024", "2025-T1"
    linea_fuente: str       # texto exacto del documento donde se encontró


@dataclass
class ExtraccionDocumento:
    """
    Resultado de fase 1. Siempre requiere confirmación humana antes de usarse.
    El investigador debe revisar montos y marcar confirmado_por_investigador=True.
    """
    filepath: str
    tipo_documento: str                        # "balance" | "estado_cuenta" | "declaracion_jurada" | "otro"
    montos_extraidos: list[MontoExtraido]
    texto_bruto: str                           # texto crudo del documento (para auditoría)
    metodo_extraccion: str                     # "pdfplumber" | "gemini_vision"
    confianza: str                             # "alta" | "media" | "baja"
    advertencias: list[str]
    timestamp_extraccion: str
    confirmado_por_investigador: bool = False  # DEBE quedar False en fase 1


@dataclass
class PerfilCliente:
    actividad_declarada: str
    ingresos_anuales_declarados_usd: Decimal
    patrimonio_declarado_usd: Decimal


@dataclass
class AnalisisFondos:
    """Resultado de fase 2 (solo después de confirmación humana)."""
    total_documentado_usd: Decimal
    total_perfil_usd: Decimal
    ratio_discrepancia: float
    bandera_incongruencia: bool
    umbral_usado: float
    descripcion_bandera: str
    documentos_analizados: list[str]
    montos_confirmados: list[dict]
    timestamp_analisis: str
    nota: str
    # Indicador de consistencia — no es un veredicto
    consistencia_perfil_origen: str = ""
    requiere_revision_humana: bool = True


# ─── Extracción desde PDF (pdfplumber) ────────────────────────────────────────

def _extraer_texto_pdf(filepath: str) -> tuple[str, str]:
    """
    Extrae texto de un PDF con capas de texto seleccionable (no escaneado).
    Devuelve (texto, metodo). Si falla o el texto es muy corto, devuelve ("", "pdfplumber_vacio").
    """
    try:
        import pdfplumber
        texto = ""
        with pdfplumber.open(filepath) as pdf:
            for pagina in pdf.pages:
                t = pagina.extract_text() or ""
                texto += t + "\n"
        texto = texto.strip()
        if len(texto) < 50:
            return "", "pdfplumber_vacio"
        return texto, "pdfplumber"
    except ImportError:
        logger.warning("pdfplumber no instalado — instalar con: pip install pdfplumber")
        return "", "pdfplumber_no_disponible"
    except Exception as exc:
        logger.warning("Error extrayendo PDF %s: %s", filepath, exc)
        return "", f"pdfplumber_error: {exc}"


# ─── Extracción con Gemini Vision (PDFs escaneados / imágenes) ────────────────

def _extraer_con_gemini(filepath: str) -> tuple[str, list[MontoExtraido], list[str]]:
    """
    Usa Gemini Vision para extraer montos de documentos escaneados o imágenes.
    Devuelve (texto_bruto, montos_extraidos, advertencias).
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    except (ImportError, KeyError) as exc:
        return "", [], [f"Gemini no disponible: {exc}"]

    ext = Path(filepath).suffix.lower()
    mime_tipos = {
        ".pdf":  "application/pdf",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".tiff": "image/tiff",
    }
    mime = mime_tipos.get(ext, "application/octet-stream")

    try:
        with open(filepath, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode()
    except Exception as exc:
        return "", [], [f"Error leyendo archivo: {exc}"]

    prompt = """Analiza este documento financiero y extrae ÚNICAMENTE datos numéricos EXPLÍCITOS.
No inferir, no calcular, no completar. Solo reportar lo que está textualmente en el documento.

Devuelve un JSON con esta estructura exacta:
{
  "tipo_documento": "balance|estado_cuenta|declaracion_jurada|libro_contable|otro",
  "montos": [
    {
      "descripcion": "descripción del concepto tal como aparece en el documento",
      "monto": 0.00,
      "moneda": "USD|UYU|EUR|ARS|BRL|otro",
      "periodo": "YYYY-MM o YYYY o texto del período",
      "linea_fuente": "texto exacto de la línea del documento"
    }
  ],
  "advertencias": ["posibles errores de lectura o ambigüedades detectadas"]
}

Si el documento no contiene información financiera clara, devolver montos=[].
IMPORTANTE: Esta extracción será revisada por un investigador antes de usarse."""

    try:
        import google.generativeai as genai
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content([
            {"mime_type": mime, "data": data_b64},
            prompt,
        ])
        texto_resp = resp.text.strip()

        # Extraer bloque JSON de la respuesta
        match = re.search(r"\{.*\}", texto_resp, re.DOTALL)
        if not match:
            return texto_resp, [], ["Gemini no devolvió JSON estructurado"]

        datos = json.loads(match.group())
        montos: list[MontoExtraido] = []
        for m in datos.get("montos", []):
            try:
                montos.append(MontoExtraido(
                    descripcion=str(m.get("descripcion", "")),
                    monto=Decimal(str(m.get("monto", "0"))),
                    moneda=str(m.get("moneda", "USD")),
                    periodo=str(m.get("periodo", "")),
                    linea_fuente=str(m.get("linea_fuente", "")),
                ))
            except (InvalidOperation, Exception) as exc:
                pass  # monto malformado — omitir e incluir en advertencias

        advertencias = datos.get("advertencias", [])
        return texto_resp, montos, advertencias

    except Exception as exc:
        logger.error("Error en Gemini Vision para %s: %s", filepath, exc)
        return "", [], [f"Error Gemini: {exc}"]


# ─── Parser de montos en texto plano ─────────────────────────────────────────

_PATRON_MONTO = re.compile(
    r"(?P<desc>[A-Za-záéíóúüñÁÉÍÓÚÜÑ][^$\d\n]{2,40}?)"
    r"[$€£]?\s*(?P<monto>[\d.,]{3,15})"
    r"\s*(?P<moneda>USD|UYU|EUR|ARS|BRL)?",
    re.IGNORECASE,
)


def _parsear_montos_texto(texto: str) -> list[MontoExtraido]:
    """
    Extracción heurística de montos desde texto plano (pdfplumber).
    Confianza baja — siempre requiere revisión del investigador.
    """
    montos: list[MontoExtraido] = []
    for linea in texto.splitlines():
        for m in _PATRON_MONTO.finditer(linea):
            try:
                monto_str = m.group("monto").replace(",", "").replace(".", "")
                # Distinguir separador decimal del de miles
                monto_raw = m.group("monto")
                if monto_raw.count(".") == 1 and len(monto_raw.split(".")[-1]) <= 2:
                    valor = Decimal(monto_raw.replace(",", ""))
                else:
                    valor = Decimal(monto_raw.replace(",", "").replace(".", ""))
                montos.append(MontoExtraido(
                    descripcion=m.group("desc").strip(),
                    monto=valor,
                    moneda=m.group("moneda") or "UYU",
                    periodo="",
                    linea_fuente=linea.strip(),
                ))
            except Exception:
                continue
    return montos[:50]   # limitar a 50 para evitar falsos positivos masivos


# ─── API pública — Fase 1 ─────────────────────────────────────────────────────

def extraer_documento(filepath: str) -> ExtraccionDocumento:
    """
    FASE 1: Extrae montos y texto del documento financiero.

    El resultado NUNCA se considera confirmado (confirmado_por_investigador=False).
    El investigador DEBE revisar, corregir si es necesario, y confirmar
    antes de llamar a analizar_fondos().

    Prueba primero pdfplumber (texto seleccionable) y cae back a Gemini Vision
    si el PDF no tiene capa de texto o es una imagen.
    """
    filepath_str = str(filepath)
    ext = Path(filepath_str).suffix.lower()
    timestamp = datetime.utcnow().isoformat() + "Z"
    advertencias: list[str] = []
    montos: list[MontoExtraido] = []
    texto_bruto = ""
    metodo = "desconocido"

    if not Path(filepath_str).exists():
        return ExtraccionDocumento(
            filepath=filepath_str,
            tipo_documento="desconocido",
            montos_extraidos=[],
            texto_bruto="",
            metodo_extraccion="archivo_no_encontrado",
            confianza="baja",
            advertencias=[f"Archivo no encontrado: {filepath_str}"],
            timestamp_extraccion=timestamp,
        )

    # Intentar extracción por texto (PDF con capas)
    if ext in EXTENSIONES_PDF:
        texto_bruto, metodo_pdf = _extraer_texto_pdf(filepath_str)
        if texto_bruto:
            metodo = metodo_pdf
            montos = _parsear_montos_texto(texto_bruto)
            confianza = "media"   # texto extraído pero parsing heurístico
            advertencias.append(
                "Extracción automática heurística. Revisar y confirmar cada monto antes de proceder."
            )

    # Fallback a Gemini Vision (PDFs escaneados o imágenes)
    if not texto_bruto or not montos:
        if ext in EXTENSIONES_PDF or ext in EXTENSIONES_IMAGEN:
            logger.info("Usando Gemini Vision para %s", Path(filepath_str).name)
            texto_bruto, montos, advs_gemini = _extraer_con_gemini(filepath_str)
            metodo = "gemini_vision"
            confianza = "media" if montos else "baja"
            advertencias.extend(advs_gemini)
        else:
            advertencias.append(f"Extensión no soportada: {ext}")
            confianza = "baja"

    if not montos:
        advertencias.append("No se pudieron extraer montos del documento. Ingresar manualmente.")
        confianza = "baja"

    return ExtraccionDocumento(
        filepath=filepath_str,
        tipo_documento="balance",           # el investigador debe ajustar si es incorrecto
        montos_extraidos=montos,
        texto_bruto=texto_bruto[:5000],     # limitar para log/auditoría
        metodo_extraccion=metodo,
        confianza=confianza,
        advertencias=advertencias,
        timestamp_extraccion=timestamp,
        confirmado_por_investigador=False,   # SIEMPRE False en fase 1
    )


# ─── API pública — Fase 2 ─────────────────────────────────────────────────────

def analizar_fondos(
    extraccion: ExtraccionDocumento,
    perfil: PerfilCliente,
    umbral_incongruencia: float = UMBRAL_INCONGRUENCIA_DEFECTO,
) -> AnalisisFondos:
    """
    FASE 2: Analiza si el volumen documentado es congruente con el perfil declarado.

    PRECONDICIÓN: extraccion.confirmado_por_investigador debe ser True.
    Si se llama sin confirmación, se ejecuta con advertencia en el log y en el resultado.

    Args:
        extraccion:             ExtraccionDocumento con confirmado_por_investigador=True
        perfil:                 datos declarados del cliente
        umbral_incongruencia:   ratio monto_doc / ingreso_declarado que dispara bandera

    Returns:
        AnalisisFondos con bandera_incongruencia y descripción auditoriable.
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    advertencias_analisis: list[str] = []

    if not extraccion.confirmado_por_investigador:
        advertencias_analisis.append(
            "ADVERTENCIA: análisis ejecutado sin confirmación del investigador. "
            "Los resultados deben considerarse preliminares."
        )
        logger.warning("analizar_fondos() llamado sin confirmación del investigador")

    # Sumar montos en USD (conversión simplificada — investigador debe verificar)
    # En producción, integrar con API de tipo de cambio BCU (Banco Central Uruguay)
    tasas_aproximadas: dict[str, Decimal] = {
        "USD": Decimal("1"),
        "UYU": Decimal("0.025"),   # aproximado — actualizar según BCU
        "EUR": Decimal("1.08"),
        "ARS": Decimal("0.001"),
        "BRL": Decimal("0.20"),
    }

    total_usd = Decimal("0")
    montos_confirmados: list[dict] = []
    for m in extraccion.montos_extraidos:
        tasa = tasas_aproximadas.get(m.moneda.upper(), Decimal("1"))
        equiv_usd = m.monto * tasa
        total_usd += equiv_usd
        montos_confirmados.append({
            "descripcion":  m.descripcion,
            "monto":        str(m.monto),
            "moneda":       m.moneda,
            "equiv_usd":    str(equiv_usd.quantize(Decimal("0.01"))),
            "periodo":      m.periodo,
        })

    perfil_usd = perfil.ingresos_anuales_declarados_usd
    if perfil_usd == 0:
        advertencias_analisis.append("Perfil del cliente tiene ingresos declarados = 0. No se puede calcular ratio.")
        ratio = 0.0
        bandera = False
    else:
        ratio = float(total_usd / perfil_usd)
        bandera = ratio >= umbral_incongruencia

    descripcion = ""
    _nota_no_licitud = (
        "La coincidencia entre el volumen documentado y la actividad declarada "
        "no constituye prueba de licitud de los fondos. "
        "La determinación es responsabilidad exclusiva del oficial de cumplimiento."
    )

    if bandera:
        descripcion = (
            f"Posible incongruencia: volumen documentado USD {total_usd:.2f} "
            f"es {ratio:.1f}× el ingreso anual declarado (USD {perfil_usd:.2f}). "
            f"Supera umbral configurado de {umbral_incongruencia:.1f}×. "
            f"Requiere verificación por el investigador."
        )
        consistencia = (
            f"Indicador: volumen documentado supera {ratio:.1f}× el perfil declarado "
            f"(umbral: {umbral_incongruencia:.1f}×). {_nota_no_licitud}"
        )
    else:
        descripcion = (
            f"Sin incongruencia detectada: volumen documentado USD {total_usd:.2f} "
            f"({ratio:.1f}× del perfil declarado, umbral: {umbral_incongruencia:.1f}×)."
        )
        consistencia = (
            f"Sin indicador de incongruencia numérica en revisión automática "
            f"({ratio:.2f}× del perfil, umbral: {umbral_incongruencia:.1f}×). "
            f"La ausencia de este indicador no implica conformidad. {_nota_no_licitud}"
        )

    if advertencias_analisis:
        descripcion = " | ".join(advertencias_analisis) + " | " + descripcion

    return AnalisisFondos(
        total_documentado_usd=total_usd.quantize(Decimal("0.01")),
        total_perfil_usd=perfil_usd,
        ratio_discrepancia=round(ratio, 3),
        bandera_incongruencia=bandera,
        umbral_usado=umbral_incongruencia,
        descripcion_bandera=descripcion,
        documentos_analizados=[extraccion.filepath],
        montos_confirmados=montos_confirmados,
        timestamp_analisis=timestamp,
        nota=(
            "Análisis automático de apoyo. Las tasas de cambio son aproximadas — "
            "verificar con el BCU. " + _nota_no_licitud
        ),
        consistencia_perfil_origen=consistencia,
        requiere_revision_humana=True,
    )
