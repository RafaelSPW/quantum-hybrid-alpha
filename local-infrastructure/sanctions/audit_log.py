"""
Log de auditoría append-only con cadena de hashes.
Registra toda acción de compliance: quién, qué, cuándo.

Una vez escrito, ningún registro puede modificarse sin romper la cadena.
Cumple requisitos de trazabilidad de SENACLAFT, Ley 19.574 y Ley 18.331.
Retención mínima: 5 años (responsabilidad del operador configurar backup y retención).

DISEÑO DE INTEGRIDAD:
  Cada registro incluye el hash SHA-256 del registro anterior (cadena Merkle).
  Modificar cualquier registro rompe todos los hashes posteriores,
  haciendo la manipulación detectable con verificar_integridad().
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path(__file__).parent / "cache" / "audit.jsonl"
ENCODING       = "utf-8"
GENESIS_HASH   = "0" * 64   # hash ficticio del bloque anterior al primero


# ─── Internos ─────────────────────────────────────────────────────────────────

def _leer_ultimo_hash() -> str:
    """Retorna el hash_propio del último registro, o GENESIS_HASH si el log está vacío."""
    if not AUDIT_LOG_PATH.exists() or AUDIT_LOG_PATH.stat().st_size == 0:
        return GENESIS_HASH
    ultima = ""
    with AUDIT_LOG_PATH.open("r", encoding=ENCODING) as f:
        for linea in f:
            s = linea.strip()
            if s:
                ultima = s
    if not ultima:
        return GENESIS_HASH
    try:
        return json.loads(ultima).get("hash_propio", GENESIS_HASH)
    except Exception:
        return GENESIS_HASH


def _hash_registro(registro: dict) -> str:
    """SHA-256 del contenido del registro, excluyendo el campo hash_propio para evitar circularidad."""
    contenido = json.dumps(
        {k: v for k, v in registro.items() if k != "hash_propio"},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(contenido.encode(ENCODING)).hexdigest()


# ─── API pública ──────────────────────────────────────────────────────────────

def registrar(
    accion: str,
    usuario_id: str,
    recurso: str,
    detalles: dict[str, Any] | None = None,
    ip_addr: str | None = None,
) -> str:
    """
    Escribe un registro de auditoría append-only encadenado.

    Args:
        accion:     descripción corta de la acción (ej: "generar_legajo", "screening_ofac")
        usuario_id: identificador del investigador o sistema que ejecutó la acción
        recurso:    identificador del objeto afectado (ej: legajo_id, nombre_consultado)
        detalles:   datos adicionales para auditoría (sin datos sensibles en claro)
        ip_addr:    IP del cliente si disponible

    Returns:
        hash_propio del registro — incluir en el legajo PDF para trazabilidad cruzada.
    """
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    registro: dict[str, Any] = {
        "timestamp":     datetime.utcnow().isoformat() + "Z",
        "usuario_id":    usuario_id,
        "accion":        accion,
        "recurso":       recurso,
        "detalles":      detalles or {},
        "ip_addr":       ip_addr or "unknown",
        "hash_anterior": _leer_ultimo_hash(),
        "hash_propio":   "",   # se calcula y rellena abajo
    }
    registro["hash_propio"] = _hash_registro(registro)

    # Abrir en modo 'a' — nunca 'w': garantiza append-only desde Python
    with AUDIT_LOG_PATH.open("a", encoding=ENCODING) as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")

    return registro["hash_propio"]


def verificar_integridad() -> tuple[bool, list[str]]:
    """
    Recorre el log y verifica la cadena de hashes.
    Devuelve (ok: bool, errores: list[str]).
    Un error indica posible manipulación o corrupción.
    """
    if not AUDIT_LOG_PATH.exists():
        return True, []

    errores: list[str] = []
    hash_esperado = GENESIS_HASH
    linea_num = 0

    with AUDIT_LOG_PATH.open("r", encoding=ENCODING) as f:
        for linea in f:
            s = linea.strip()
            if not s:
                continue
            linea_num += 1
            try:
                reg = json.loads(s)
            except json.JSONDecodeError:
                errores.append(f"Línea {linea_num}: JSON inválido")
                continue

            if reg.get("hash_anterior") != hash_esperado:
                errores.append(
                    f"Línea {linea_num} [{reg.get('timestamp','')}]: "
                    f"hash_anterior no coincide — cadena rota"
                )

            calculado = _hash_registro(reg)
            if calculado != reg.get("hash_propio"):
                errores.append(
                    f"Línea {linea_num} [{reg.get('timestamp','')}]: "
                    f"hash_propio no coincide — posible manipulación del registro"
                )

            hash_esperado = reg.get("hash_propio", "")

    return len(errores) == 0, errores


def buscar_registros(
    usuario_id: str | None = None,
    accion: str | None = None,
    recurso: str | None = None,
    desde_iso: str | None = None,
    hasta_iso: str | None = None,
    limite: int = 500,
) -> list[dict]:
    """
    Consulta el log (solo lectura). Todos los parámetros son filtros opcionales.
    desde_iso / hasta_iso: strings ISO 8601 (ej: "2026-01-01T00:00:00Z").
    """
    if not AUDIT_LOG_PATH.exists():
        return []

    resultados = []
    with AUDIT_LOG_PATH.open("r", encoding=ENCODING) as f:
        for linea in f:
            if len(resultados) >= limite:
                break
            s = linea.strip()
            if not s:
                continue
            try:
                r = json.loads(s)
            except Exception:
                continue
            if usuario_id and r.get("usuario_id") != usuario_id:
                continue
            if accion and r.get("accion") != accion:
                continue
            if recurso and r.get("recurso") != recurso:
                continue
            if desde_iso and r.get("timestamp", "") < desde_iso:
                continue
            if hasta_iso and r.get("timestamp", "") > hasta_iso:
                continue
            resultados.append(r)

    return resultados
