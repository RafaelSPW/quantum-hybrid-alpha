"""
Descarga, cacheo y parsing de listas de sanciones OFAC.
Fuentes: SDN (Specially Designated Nationals) y Consolidated Sanctions List.
Servicio oficial: https://sanctionslistservice.ofac.treas.gov/
"""

import io
import json
import logging
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── URLs del OFAC Sanctions List Service (SLS) ───────────────────────────────
# Primarias: Enhanced XML empaquetado en ZIP
OFAC_SDN_URL        = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_XML.ZIP"
OFAC_CONS_URL       = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONS_PRIM.ZIP"
# Fallback: descarga directa XML desde treasury.gov (formato legacy sin namespace)
OFAC_SDN_FALLBACK   = "https://www.treasury.gov/ofac/downloads/sdn.xml"
OFAC_CONS_FALLBACK  = "https://www.treasury.gov/ofac/downloads/consolidated/consolidated.xml"

# Namespace del Enhanced XML emitido por el SLS
OFAC_NS             = "urn:us:gov:treasury:fin:fac:sdnList"

CACHE_DIR           = Path(__file__).parent / "cache"
SDN_CACHE_PATH      = CACHE_DIR / "sdn.xml"
CONS_CACHE_PATH     = CACHE_DIR / "cons.xml"
META_PATH           = CACHE_DIR / "meta.json"

REFRESH_HORAS       = 24   # una descarga por día; compartida por todos los clientes
TIMEOUT_SEG         = 60

# Singleton en memoria: se parsea el XML una sola vez por ciclo de 24h.
# Todos los requests del día reutilizan el mismo objeto sin leer disco.
_DB_LOCK:     threading.Lock          = threading.Lock()
_DB_INSTANCE: Optional["OFACDatabase"] = None
_DB_INSTANCE_TS: str                  = ""  # coincide con meta["descargado_el"] cuando es válido


# ─── Estructuras de datos ──────────────────────────────────────────────────────

@dataclass
class OFACAlias:
    nombre: str
    tipo: str       # "a.k.a." | "f.k.a." | "n.k.a."
    categoria: str  # "strong" | "weak"


@dataclass
class OFACDocumento:
    tipo: str
    numero: str
    pais: str


@dataclass
class OFACEntry:
    uid: str
    nombre_principal: str
    tipo: str                        # "Individual" | "Entity" | "Vessel" | "Aircraft"
    programas: list[str]
    aliases: list[OFACAlias]
    documentos: list[OFACDocumento]
    paises: list[str]
    lista_origen: str                # "SDN" | "Consolidated"


@dataclass
class OFACDatabase:
    entradas: list[OFACEntry] = field(default_factory=list)
    publicado_el: str = ""
    descargado_el: str = ""
    fuentes_ok: list[str] = field(default_factory=list)
    fuentes_error: list[str] = field(default_factory=list)


# ─── Helpers de XML ───────────────────────────────────────────────────────────

def _txt(elem: Optional[ET.Element]) -> str:
    """Texto de un elemento o cadena vacía si es None."""
    return (elem.text or "").strip() if elem is not None else ""


def _tag(nombre: str, usa_ns: bool) -> str:
    """Prefija el namespace si el documento lo usa."""
    return f"{{{OFAC_NS}}}{nombre}" if usa_ns else nombre


# ─── Descarga ─────────────────────────────────────────────────────────────────

def _descargar_xml(url: str, fallback: Optional[str] = None) -> tuple[bytes, int]:
    """
    Descarga el XML desde la URL principal; si falla, intenta el fallback.
    Desempaqueta ZIPs automáticamente. Devuelve (bytes_xml, http_status).
    """
    for intento in filter(None, [url, fallback]):
        try:
            logger.info("OFAC fetch → %s", intento)
            resp = requests.get(
                intento,
                timeout=TIMEOUT_SEG,
                headers={"User-Agent": "AHC-Intelligence/1.0 KYC-Compliance-Module"},
            )
            resp.raise_for_status()

            # Descomprimir si es ZIP (SLS entrega ZIPs)
            if intento.upper().endswith(".ZIP") or "zip" in resp.headers.get("Content-Type", ""):
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    nombres_xml = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                    if not nombres_xml:
                        raise ValueError("ZIP sin archivos XML")
                    contenido = zf.read(nombres_xml[0])
            else:
                contenido = resp.content

            logger.info("Descarga OK desde %s (%d bytes)", intento, len(contenido))
            return contenido, resp.status_code

        except Exception as exc:
            logger.warning("Error descargando %s: %s", intento, exc)

    return b"", 0


# ─── Parser del Enhanced XML ──────────────────────────────────────────────────

def _parsear_lista(xml_bytes: bytes, lista_origen: str) -> tuple[list[OFACEntry], str]:
    """
    Parsea el Enhanced XML de OFAC.
    Detecta automáticamente si usa namespace (SLS) o formato legacy (treasury.gov).
    Devuelve (entradas, fecha_publicacion).
    """
    if not xml_bytes:
        return [], ""

    root = ET.fromstring(xml_bytes)
    usa_ns = root.tag.startswith("{")

    def t(nombre: str) -> str:
        return _tag(nombre, usa_ns)

    pub_date = _txt(root.find(f".//{t('Publish_Date')}"))
    entradas: list[OFACEntry] = []

    for sdn in root.iter(t("sdnEntry")):
        uid       = _txt(sdn.find(t("uid")))
        first     = _txt(sdn.find(t("firstName")))
        last      = _txt(sdn.find(t("lastName")))
        sdn_type  = _txt(sdn.find(t("sdnType")))

        # Nombre completo: "Apellido, Nombre" para individuos; solo last para entidades
        nombre_principal = f"{last}, {first}".strip(", ") if first else last

        programas = [_txt(p) for p in sdn.iter(t("program")) if _txt(p)]

        aliases: list[OFACAlias] = []
        for aka in sdn.iter(t("aka")):
            a_first = _txt(aka.find(t("firstName")))
            a_last  = _txt(aka.find(t("lastName")))
            nombre_aka = f"{a_last}, {a_first}".strip(", ") if a_first else a_last
            if nombre_aka:
                aliases.append(OFACAlias(
                    nombre=nombre_aka,
                    tipo=_txt(aka.find(t("type"))),
                    categoria=_txt(aka.find(t("category"))),
                ))

        documentos: list[OFACDocumento] = []
        for doc in sdn.iter(t("id")):
            documentos.append(OFACDocumento(
                tipo=_txt(doc.find(t("idType"))),
                numero=_txt(doc.find(t("idNumber"))),
                pais=_txt(doc.find(t("idCountry"))),
            ))

        paises = list({
            _txt(addr.find(t("country")))
            for addr in sdn.iter(t("address"))
            if _txt(addr.find(t("country")))
        })

        entradas.append(OFACEntry(
            uid=uid,
            nombre_principal=nombre_principal,
            tipo=sdn_type,
            programas=programas,
            aliases=aliases,
            documentos=documentos,
            paises=paises,
            lista_origen=lista_origen,
        ))

    return entradas, pub_date


# ─── Caché y metadatos ────────────────────────────────────────────────────────

def _leer_meta() -> dict:
    if META_PATH.exists():
        try:
            return json.loads(META_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _guardar_meta(meta: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _cache_vigente() -> bool:
    meta = _leer_meta()
    ts = meta.get("descargado_el")
    if not ts:
        return False
    try:
        horas = (datetime.utcnow() - datetime.fromisoformat(ts)).total_seconds() / 3600
        return horas < REFRESH_HORAS
    except Exception:
        return False


# ─── API pública ──────────────────────────────────────────────────────────────

def actualizar_listas(forzar: bool = False) -> OFACDatabase:
    """
    Descarga las listas OFAC si el caché de disco venció (o forzar=True).
    Parsea el XML solo cuando el timestamp de disco cambia; todos los
    clientes dentro del mismo proceso reutilizan el objeto en memoria.
    """
    global _DB_INSTANCE, _DB_INSTANCE_TS

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK:
        # ── Paso 1: decidir si hay que re-descargar de OFAC ──────────────
        if forzar or not _cache_vigente():
            ahora = datetime.utcnow().isoformat()
            meta = {"descargado_el": ahora, "fuentes": {}}
            for nombre, url, fallback, cache_path in [
                ("SDN",          OFAC_SDN_URL,  OFAC_SDN_FALLBACK,  SDN_CACHE_PATH),
                ("Consolidated", OFAC_CONS_URL, OFAC_CONS_FALLBACK, CONS_CACHE_PATH),
            ]:
                xml_bytes, status = _descargar_xml(url, fallback)
                meta["fuentes"][nombre] = {"status_http": status, "timestamp": ahora}
                if xml_bytes:
                    cache_path.write_bytes(xml_bytes)
                    logger.info("Lista %s → caché actualizado (%d bytes, HTTP %d)", nombre, len(xml_bytes), status)
                else:
                    logger.error("Lista %s → descarga fallida (HTTP %d)", nombre, status)
            _guardar_meta(meta)

        # ── Paso 2: si el singleton en memoria es del mismo ciclo, reusarlo ──
        disco_ts = _leer_meta().get("descargado_el", "")
        if _DB_INSTANCE is not None and _DB_INSTANCE_TS == disco_ts:
            logger.info(
                "OFACDatabase en memoria vigente — %d entradas, ts=%s",
                len(_DB_INSTANCE.entradas), disco_ts,
            )
            return _DB_INSTANCE

        # ── Paso 3: parsear XML desde disco (una vez por ciclo de 24h) ──────
        db = OFACDatabase(descargado_el=disco_ts)
        for nombre, cache_path, lista_origen in [
            ("SDN",          SDN_CACHE_PATH,  "SDN"),
            ("Consolidated", CONS_CACHE_PATH, "Consolidated"),
        ]:
            if not cache_path.exists():
                logger.warning("Caché %s no encontrado en disco", nombre)
                db.fuentes_error.append(nombre)
                continue
            try:
                entradas, pub_date = _parsear_lista(cache_path.read_bytes(), lista_origen)
                db.entradas.extend(entradas)
                if pub_date:
                    db.publicado_el = pub_date
                db.fuentes_ok.append(nombre)
                logger.info("Lista %s cargada: %d entradas (publicada: %s)", nombre, len(entradas), pub_date)
            except Exception as exc:
                logger.error("Error parseando lista %s: %s", nombre, exc)
                db.fuentes_error.append(nombre)

        _DB_INSTANCE    = db
        _DB_INSTANCE_TS = disco_ts
        logger.info("OFACDatabase actualizado en memoria — %d entradas totales", len(db.entradas))
        return db
