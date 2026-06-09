"""
Búsqueda de posibles menciones PEP y adverse media en fuentes abiertas.

AVISO LEGAL: Este módulo NUNCA determina si una persona "es PEP".
Solo detecta indicios en fuentes públicas y los presenta para verificación humana.
Toda salida incluye fuente citada. Resultados sin fuente verificable no se reportan.
"""

import logging
import time
from datetime import datetime
from typing import Any

from ddgs import DDGS

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SEG          = 15
PAUSA_ENTRE_REQUESTS = 1.2    # segundos — evita rate-limiting de fuentes
MAX_RESULTADOS_DDG   = 8

# Términos PEP: cargos públicos y roles políticos
_TERMINOS_PEP = (
    "ministro OR senador OR diputado OR presidente OR intendente OR "
    "secretario OR subsecretario OR director OR gobernador OR alcalde OR "
    "\"cargo público\" OR \"función pública\" OR parliament OR official OR politician"
)

# Términos adverse media: noticias negativas / riesgo de integridad
_TERMINOS_ADVERSE = (
    "corrupción OR lavado OR sanción OR fraude OR investigado OR procesado OR "
    "detenido OR acusado OR imputado OR extradición OR soborno OR narcotráfico OR "
    "corruption OR \"money laundering\" OR sanctioned OR fraud OR arrested OR bribery"
)

# Nota legal obligatoria incluida en todo reporte de este módulo
NOTA_LEGAL = (
    "Requiere verificación humana. No constituye determinación legal ni "
    "confirmación de condición PEP. Los resultados son indicios basados en "
    "fuentes abiertas y deben ser validados por un oficial de cumplimiento. "
    "AHC Intelligence — módulo de screening / SENACLAFT Uruguay."
)


# ─── Búsquedas ────────────────────────────────────────────────────────────────

def _buscar_duckduckgo(query: str, max_resultados: int = MAX_RESULTADOS_DDG) -> list[dict[str, str]]:
    """
    Realiza una búsqueda en DuckDuckGo y devuelve resultados normalizados.
    Retorna lista de dicts: {title, url, body}.
    Si falla, devuelve lista vacía y loguea el error.
    """
    try:
        with DDGS() as ddgs:
            return [
                {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
                for r in ddgs.text(query, max_results=max_resultados)
                if r.get("href")  # descartar resultados sin URL
            ]
    except Exception as exc:
        logger.warning("DuckDuckGo falló para query %r: %s", query[:60], exc)
        return []


def _buscar_wikipedia(nombre: str) -> list[dict[str, str]]:
    """
    Consulta la Wikipedia API (español) para detectar si existe un artículo
    que asocie el nombre con roles públicos o políticos.
    Retorna lista de dicts: {title, url, body}.
    """
    try:
        resp = requests.get(
            "https://es.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": nombre, "limit": 3, "format": "json"},
            timeout=TIMEOUT_SEG,
        )
        resp.raise_for_status()
        data = resp.json()
        titles = data[1] if len(data) > 1 else []
        descs  = data[2] if len(data) > 2 else []
        urls   = data[3] if len(data) > 3 else []
        return [
            {"title": t, "url": u, "body": d}
            for t, d, u in zip(titles, descs, urls)
            if u
        ]
    except Exception as exc:
        logger.warning("Wikipedia falló para %r: %s", nombre, exc)
        return []


# ─── Nivel de confianza ───────────────────────────────────────────────────────

def _confianza(n_resultados: int, tipo: str, tiene_wikipedia: bool) -> str:
    """
    Heurística de confianza basada en cantidad y calidad de indicios.
    "alto" no significa certeza — solo más señales convergentes.
    """
    if tipo == "posible_pep" and tiene_wikipedia:
        return "alto"
    if n_resultados >= 5:
        return "alto"
    if n_resultados >= 2:
        return "medio"
    return "bajo"


# ─── Construcción de resultados ───────────────────────────────────────────────

def _construir_items(
    resultados: list[dict[str, str]],
    tipo: str,
    nivel_confianza: str,
    fuente_nombre: str,
    fecha_busqueda: str,
) -> list[dict[str, Any]]:
    """Convierte resultados crudos al formato estándar del reporte."""
    return [
        {
            "titulo":        r["title"],
            "extracto":      r["body"] or "(sin extracto disponible)",
            "url":           r["url"],
            "fecha_busqueda": fecha_busqueda,
            "tipo":          tipo,
            "confianza":     nivel_confianza,
            "fuente_nombre": fuente_nombre,
        }
        for r in resultados
        if r.get("url")
    ]


# ─── API pública ──────────────────────────────────────────────────────────────

def screening_pep_adverse(nombre: str) -> dict[str, Any]:
    """
    Realiza búsqueda de adverse media y posibles indicios PEP para el nombre dado.

    Consulta:
      1. DuckDuckGo — términos PEP (cargos públicos / roles políticos)
      2. DuckDuckGo — términos adverse media (corrupción, sanciones, etc.)
      3. Wikipedia   — artículos asociados al nombre

    Devuelve estructura con posibles_coincidencias (siempre con fuente citada),
    errores_fuente (para auditoría) y nota_legal.
    """
    fecha_busqueda = datetime.utcnow().strftime("%Y-%m-%d")
    errores: list[str] = []
    posibles: list[dict[str, Any]] = []

    # ── 1. DuckDuckGo — PEP ──────────────────────────────────────────────────
    query_pep = f'"{nombre}" ({_TERMINOS_PEP})'
    res_pep = _buscar_duckduckgo(query_pep)
    if not res_pep:
        errores.append("DuckDuckGo PEP: sin resultados o error de conexión")
    time.sleep(PAUSA_ENTRE_REQUESTS)

    # ── 2. DuckDuckGo — Adverse media ────────────────────────────────────────
    query_adverse = f'"{nombre}" ({_TERMINOS_ADVERSE})'
    res_adverse = _buscar_duckduckgo(query_adverse)
    if not res_adverse:
        errores.append("DuckDuckGo Adverse Media: sin resultados o error de conexión")
    time.sleep(PAUSA_ENTRE_REQUESTS)

    # ── 3. Wikipedia ──────────────────────────────────────────────────────────
    res_wiki = _buscar_wikipedia(nombre)
    if not res_wiki:
        errores.append("Wikipedia: sin artículos coincidentes")

    tiene_wiki = bool(res_wiki)

    # Ensamblar resultados con nivel de confianza por tipo
    posibles.extend(_construir_items(
        res_pep,
        tipo="posible_pep",
        nivel_confianza=_confianza(len(res_pep), "posible_pep", tiene_wiki),
        fuente_nombre="DuckDuckGo Web Search",
        fecha_busqueda=fecha_busqueda,
    ))
    posibles.extend(_construir_items(
        res_adverse,
        tipo="adverse_media",
        nivel_confianza=_confianza(len(res_adverse), "adverse_media", False),
        fuente_nombre="DuckDuckGo Web Search",
        fecha_busqueda=fecha_busqueda,
    ))
    # Wikipedia siempre se reporta con confianza "alto" por ser fuente estructurada
    posibles.extend(_construir_items(
        res_wiki,
        tipo="posible_pep",
        nivel_confianza="alto",
        fuente_nombre="Wikipedia (es.wikipedia.org)",
        fecha_busqueda=fecha_busqueda,
    ))

    return {
        "posibles_coincidencias": posibles,
        "errores_fuente":         errores,
        "nota":                   NOTA_LEGAL,
    }
