"""
AHC Intelligence — Sanctions / PEP Screening
Punto de entrada CLI para correr una consulta end-to-end.

Uso:
    python -m sanctions.main --nombre "Juan García López"
    python -m sanctions.main --nombre "Petróleo de Venezuela S.A." --umbral 80
    python -m sanctions.main --nombre "John Smith" --forzar --output reporte.json
"""

import argparse
import logging
import sys
from pathlib import Path

from .ofac_loader import actualizar_listas
from .matcher import buscar_en_ofac, UMBRAL_DEFECTO
from .pep_screener import screening_pep_adverse
from .report_builder import construir_reporte, reporte_a_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_screening(
    nombre: str,
    umbral: int = UMBRAL_DEFECTO,
    forzar_descarga: bool = False,
) -> dict:
    """
    Pipeline completo:
      1. Actualizar / cargar listas OFAC desde caché o descarga
      2. Matching fuzzy contra SDN + Consolidated
      3. Búsqueda PEP / adverse media en fuentes abiertas
      4. Construcción del reporte JSON estructurado

    Raises: nunca — los errores de fuentes se registran en el reporte, no rompen el flujo.
    """
    logger.info("=== Screening iniciado: %r (umbral=%d) ===", nombre, umbral)

    # Paso 1 — Listas OFAC
    logger.info("[1/3] Verificando listas OFAC...")
    db = actualizar_listas(forzar=forzar_descarga)
    logger.info("[1/3] %d entradas cargadas (fuentes OK: %s)", len(db.entradas), db.fuentes_ok)

    # Paso 2 — Matching OFAC
    logger.info("[2/3] Matching OFAC...")
    coincidencias = buscar_en_ofac(nombre, db, umbral=umbral)
    logger.info("[2/3] %d coincidencia(s) OFAC encontrada(s)", len(coincidencias))
    for c in coincidencias:
        logger.info("      ↳ %r [%s] score=%.1f lista=%s", c.nombre_en_lista, c.tipo_match, c.score, c.lista_origen)

    # Paso 3 — PEP / Adverse media
    logger.info("[3/3] Búsqueda PEP / adverse media...")
    resultado_pep = screening_pep_adverse(nombre)
    n_pep = len(resultado_pep["posibles_coincidencias"])
    logger.info("[3/3] %d resultado(s) en fuentes abiertas", n_pep)

    # Reporte final
    reporte = construir_reporte(nombre, coincidencias, resultado_pep, db)
    logger.info("=== Riesgo OFAC: %s ===", reporte["ofac"]["riesgo"])

    return reporte


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AHC Intelligence — Sanctions/PEP Screening",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--nombre", required=True, help="Nombre de persona o entidad a consultar")
    parser.add_argument(
        "--umbral", type=int, default=UMBRAL_DEFECTO,
        help=f"Umbral de matching fuzzy 0-100 (default: {UMBRAL_DEFECTO})",
    )
    parser.add_argument(
        "--forzar", action="store_true",
        help="Forzar descarga de listas aunque el caché esté vigente",
    )
    parser.add_argument(
        "--output", type=str,
        help="Ruta donde guardar el reporte JSON (omitir = imprimir en stdout)",
    )
    args = parser.parse_args()

    reporte = run_screening(args.nombre, umbral=args.umbral, forzar_descarga=args.forzar)
    json_str = reporte_a_json(reporte)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        logger.info("Reporte guardado en %s", args.output)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
