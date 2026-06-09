"""
Motor de matching fuzzy entre un nombre consultado y las entradas de la base OFAC.
Normaliza acentos, mayúsculas y prueba variaciones de orden nombre/apellido.
Usa rapidfuzz.token_set_ratio, que es robusto a reordenamientos de tokens.
"""

import re
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz

from .ofac_loader import OFACDatabase, OFACEntry

# Umbral mínimo para reportar una coincidencia (0-100, configurable por llamador)
UMBRAL_DEFECTO = 85


@dataclass
class Coincidencia:
    uid: str
    nombre_en_lista: str
    nombre_consultado: str
    score: float            # 0–100; cuánto se parece el nombre consultado al de la lista
    tipo_match: str         # "nombre_principal" | "alias"
    categoria_alias: str    # "" | "strong" | "weak"
    lista_origen: str       # "SDN" | "Consolidated"
    programas: list[str]
    paises: list[str]
    fuente_url: str         # URL del portal OFAC para auditoría


# ─── Normalización ────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """
    Pasa a minúsculas, elimina diacríticos (tildes, diéresis) y puntuación.
    Ejemplos: "García López" → "garcia lopez", "AL-QAEDA" → "al qaeda"
    """
    texto = texto.lower().strip()
    # Descomponer en base + marca diacrítica y eliminar las marcas
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Reemplazar todo lo que no sea letra o dígito con espacio
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _variaciones(nombre: str) -> list[str]:
    """
    Genera permutaciones del nombre para cubrir diferencias de orden.
    Cubre: "Juan García" ↔ "García Juan" ↔ "García, Juan" etc.
    """
    norm = normalizar(nombre.replace(",", " "))
    partes = norm.split()
    if len(partes) < 2:
        return [norm]

    variaciones: set[str] = {norm}
    # Invertir primer / segundo bloque de tokens
    mitad = len(partes) // 2
    variaciones.add(" ".join(partes[mitad:] + partes[:mitad]))
    # Primera palabra al final (cubre "Juan García López" → "García López Juan")
    variaciones.add(" ".join(partes[1:] + [partes[0]]))
    # Última palabra al inicio
    variaciones.add(" ".join([partes[-1]] + partes[:-1]))
    return list(variaciones)


# ─── Scoring ──────────────────────────────────────────────────────────────────

def _score_maximo(query: str, nombre_lista: str) -> float:
    """
    Score máximo entre todas las variaciones del nombre consultado vs. el nombre de lista.
    token_set_ratio ignora orden de tokens y tokens duplicados: ideal para nombres compuestos.
    """
    lista_norm = normalizar(nombre_lista)
    return max(
        fuzz.token_set_ratio(variante, lista_norm)
        for variante in _variaciones(query)
    )


def _url_ofac(entrada: OFACEntry) -> str:
    """URL canónica del portal OFAC para auditoría y trazabilidad."""
    return f"https://sanctionssearch.ofac.treas.gov/Details.aspx?id={entrada.uid}"


# ─── API pública ──────────────────────────────────────────────────────────────

def buscar_en_ofac(
    nombre: str,
    db: OFACDatabase,
    umbral: int = UMBRAL_DEFECTO,
) -> list[Coincidencia]:
    """
    Busca el nombre en la base OFAC evaluando nombre principal y todos los aliases.
    Devuelve coincidencias con score >= umbral, ordenadas por score descendente.
    Cada coincidencia incluye el nombre exacto que disparó el match (auditable).
    """
    resultados: list[Coincidencia] = []

    for entrada in db.entradas:
        # Evaluar nombre principal
        score = _score_maximo(nombre, entrada.nombre_principal)
        if score >= umbral:
            resultados.append(Coincidencia(
                uid=entrada.uid,
                nombre_en_lista=entrada.nombre_principal,
                nombre_consultado=nombre,
                score=score,
                tipo_match="nombre_principal",
                categoria_alias="",
                lista_origen=entrada.lista_origen,
                programas=entrada.programas,
                paises=entrada.paises,
                fuente_url=_url_ofac(entrada),
            ))
            # Si el nombre principal ya supera el umbral, no es necesario revisar aliases
            continue

        # Evaluar aliases: registrar el de mayor score
        mejor_score = 0.0
        mejor_alias = None
        for alias in entrada.aliases:
            s = _score_maximo(nombre, alias.nombre)
            if s > mejor_score:
                mejor_score, mejor_alias = s, alias

        if mejor_score >= umbral and mejor_alias:
            resultados.append(Coincidencia(
                uid=entrada.uid,
                nombre_en_lista=mejor_alias.nombre,
                nombre_consultado=nombre,
                score=mejor_score,
                tipo_match="alias",
                categoria_alias=mejor_alias.categoria,
                lista_origen=entrada.lista_origen,
                programas=entrada.programas,
                paises=entrada.paises,
                fuente_url=_url_ofac(entrada),
            ))

    resultados.sort(key=lambda c: c.score, reverse=True)
    return resultados
