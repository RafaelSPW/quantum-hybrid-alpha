"""
Motor de calificacion de riesgo de clientes (SENACLAFT / Ley 19.574).
Consume matriz_riesgo_config.json. Toda calificacion es AYUDA: la decision
final es del oficial de cumplimiento humano. El sistema sugiere y documenta.

TRAZABILIDAD AUDITORIAL:
  Cada evaluacion incluye version_matriz y config_hash (SHA-256 del JSON).
  Permite reproducir exactamente que criterios estaban vigentes en cada caso,
  incluso si la matriz se actualizo despues.

MECANISMO DE BLOQUEO:
  Puntaje 999 en cualquier factor → riesgo=Alto + bloqueado=True, independientemente
  del puntaje ponderado total. Requiere escalamiento al oficial senior.
"""

import hashlib
import json
import shutil
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Rutas absolutas — independientes del directorio de trabajo
CONFIG_PATH       = Path(__file__).parent / "matriz_riesgo_config.json"
ARCHIVE_DIR       = Path(__file__).parent / "cache" / "risk_config_history"
_VIGENCIA_PATH    = Path(__file__).parent / "vigencia_config.json"
_DEFAULTS_VIGENCIA = {"Alto": 180, "Moderado": 365, "Bajo": 730}

_NOTA_LEGAL_RIESGO = (
    "Calificación automática de apoyo. No constituye determinación legal ni "
    "habilitación de operación. La determinación final es exclusiva del oficial "
    "de cumplimiento humano. AHC Intelligence — SENACLAFT / Ley 19.574."
)


def _vigencia_hasta(nivel_riesgo: str) -> str:
    """Calcula vigencia_hasta según nivel de riesgo. Configurable vía vigencia_config.json."""
    try:
        cfg = json.loads(_VIGENCIA_PATH.read_text(encoding="utf-8"))
        dias_map = cfg.get("vigencias_dias", _DEFAULTS_VIGENCIA)
    except Exception:
        dias_map = _DEFAULTS_VIGENCIA
    dias = dias_map.get(nivel_riesgo, 365)
    return (datetime.now(timezone.utc) + timedelta(days=dias)).isoformat()


def _norm(texto: str) -> str:
    """
    Normaliza texto para lookup robusto: NFKD, sin diacriticos, strip, mayusculas.
    Permite que 'URUGUAY', 'Uruguay', 'Urúguay' resuelvan al mismo valor en la tabla.
    """
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.strip().upper()


def _hash_config(raw: bytes) -> str:
    """SHA-256 del contenido del archivo de config para trazabilidad auditorial."""
    return hashlib.sha256(raw).hexdigest()


class MatrizRiesgo:
    """
    Motor de calificacion de riesgo basado en matriz_riesgo_config.json.

    Uso:
        m = MatrizRiesgo()
        resultado = m.evaluar({
            "numero_cliente": "001",
            "nombre_cliente": "Juan Perez",
            "actividad_economica": "JUBILADOS",
            "calidad_pep": "NO",
            "opera_cuenta_terceros": "NO",
            "monto_significativo": "NO",
            "pais_residencia": "URUGUAY",
            "pais_actividad_comercial": "URUGUAY",
            "productos_servicios": "NO",
        })
    """

    def __init__(self, ruta_config: str | Path | None = None):
        ruta = Path(ruta_config) if ruta_config else CONFIG_PATH
        raw = ruta.read_bytes()

        self.cfg         = json.loads(raw)
        self.config_hash = _hash_config(raw)
        self.config_path = str(ruta)

        # Tablas normalizadas para lookup robusto (sin diacriticos, uppercase)
        self._tablas = {
            nombre: {_norm(k): v for k, v in tabla.items()}
            for nombre, tabla in self.cfg["tablas"].items()
        }
        self.pesos     = self.cfg["ponderaciones"]
        self.umbrales  = self.cfg["umbrales"]
        self.BLOQUEO   = self.cfg["puntaje_bloqueo"]

        # Archivar version actual si no existe copia historica
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        version      = self.cfg.get("version", "sin-version")
        archivo_hist = ARCHIVE_DIR / f"matriz_riesgo_v{version}.json"
        if not archivo_hist.exists():
            shutil.copy2(ruta, archivo_hist)

    def _puntaje(self, tabla: str, respuesta: str) -> tuple[int | None, bool]:
        """
        Busca la respuesta en la tabla normalizada.
        Devuelve (puntaje, encontrado). Si no esta, encontrado=False.
        """
        val = self._tablas[tabla].get(_norm(respuesta))
        return (val, True) if val is not None else (None, False)

    def evaluar(self, cliente: dict) -> dict:
        """
        Califica el riesgo del cliente evaluando los 7 factores de la matriz.

        Args:
            cliente: dict con las claves del perfil. Claves requeridas:
                - actividad_economica   → tabla "actividad"
                - calidad_pep           → tabla "pep"        (SI / NO)
                - opera_cuenta_terceros → tabla "terceros"   (SI / NO)
                - monto_significativo   → tabla "monto_significativo" (SI / NO)
                - pais_residencia       → tabla "pais"
                - pais_actividad_comercial → tabla "pais"
                - productos_servicios   → tabla "productos"  (SI / NO)
                Opcionales: numero_cliente, nombre_cliente

        Returns:
            dict con: riesgo (Bajo/Moderado/Alto), total_ponderado, detalle por factor,
            version_matriz, config_hash, bloqueado, timestamp, nota.
        """
        # Mapeo factor → tabla de lookup
        mapa = {
            "actividad_economica":      "actividad",
            "calidad_pep":              "pep",
            "opera_cuenta_terceros":    "terceros",
            "monto_significativo":      "monto_significativo",
            "pais_residencia":          "pais",
            "pais_actividad_comercial": "pais",
            "productos_servicios":      "productos",
        }

        detalle         = []
        total_ponderado = 0.0
        bloqueado       = False
        faltantes       = []

        for factor, tabla in mapa.items():
            respuesta    = cliente.get(factor)
            peso         = self.pesos[factor]
            puntaje, ok  = self._puntaje(tabla, respuesta)

            if not ok:
                faltantes.append({"factor": factor, "respuesta_recibida": respuesta})
                puntaje = 0   # no suma al total, queda registrado como pendiente

            es_bloqueo = (puntaje is not None and puntaje >= self.BLOQUEO)
            if es_bloqueo:
                bloqueado = True

            ponderado        = round((puntaje or 0) * peso, 4)
            total_ponderado += ponderado

            detalle.append({
                "factor":    factor,
                "respuesta": respuesta,
                "puntaje":   puntaje,
                "peso":      peso,
                "ponderado": ponderado,
                "bloqueo":   es_bloqueo,
                "en_tabla":  ok,
            })

        total_ponderado = round(total_ponderado, 2)

        # Etiqueta de riesgo
        if bloqueado:
            etiqueta      = "Alto"
            motivo_bloqueo = (
                "Jurisdiccion o parametro marcado como NO OPERAR (codigo de bloqueo 999). "
                "Requiere escalamiento al oficial de cumplimiento senior."
            )
        elif total_ponderado >= self.umbrales["alto_desde"]:
            etiqueta      = "Alto"
            motivo_bloqueo = None
        elif total_ponderado <= self.umbrales["bajo_max"]:
            etiqueta      = "Bajo"
            motivo_bloqueo = None
        else:
            etiqueta      = "Moderado"
            motivo_bloqueo = None

        return {
            "cliente": {
                "numero": cliente.get("numero_cliente"),
                "nombre": cliente.get("nombre_cliente"),
            },
            "timestamp":                     datetime.now(timezone.utc).isoformat(),
            "id_evaluacion":                 str(uuid.uuid4()),
            "vigencia_hasta":                _vigencia_hasta(etiqueta),
            "version_matriz":                self.cfg["version"],
            "fecha_lista_paises":            self.cfg.get("fecha_lista_paises", ""),
            "config_hash":                   self.config_hash,
            "total_ponderado":               total_ponderado,
            "riesgo":                        etiqueta,
            "bloqueado":                     bloqueado,
            "motivo_bloqueo":                motivo_bloqueo,
            "respuestas_no_encontradas":     faltantes,
            "detalle":                       detalle,
            "decision_oficial_cumplimiento": None,
            "requiere_revision_humana":      True,
            "nota_legal":                    _NOTA_LEGAL_RIESGO,
            "nota": (
                "Calificacion automatica de apoyo. No constituye determinacion legal. "
                "Revision y firma del oficial de cumplimiento requerida. "
                "AHC Intelligence / SENACLAFT — Ley 19.574."
            ),
        }

    def actividades_disponibles(self) -> list[str]:
        """Lista de actividades economicas reconocidas por la matriz."""
        return sorted(self.cfg["tablas"]["actividad"].keys())

    def paises_disponibles(self) -> list[str]:
        """Lista de paises reconocidos por la matriz."""
        return sorted(self.cfg["tablas"]["pais"].keys())


# ─── Helpers de modulo (compatibilidad con imports anteriores) ─────────────────

def version_activa() -> str:
    return MatrizRiesgo().cfg["version"]


# ─── Ejemplo de uso ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    m = MatrizRiesgo()

    # Ejemplo 1: cliente local de bajo riesgo
    r1 = m.evaluar({
        "numero_cliente":          "001",
        "nombre_cliente":          "Juan Perez",
        "actividad_economica":     "JUBILADOS",
        "calidad_pep":             "NO",
        "opera_cuenta_terceros":   "NO",
        "monto_significativo":     "NO",
        "pais_residencia":         "URUGUAY",
        "pais_actividad_comercial":"URUGUAY",
        "productos_servicios":     "NO",
    })
    print(json.dumps(r1, ensure_ascii=False, indent=2))

    print("\n" + "="*60 + "\n")

    # Ejemplo 2: dispara bloqueo por pais + PEP + todo alto
    r2 = m.evaluar({
        "numero_cliente":          "002",
        "nombre_cliente":          "Entidad X",
        "actividad_economica":     "ACTIVIDADES FIDUCIARIAS",
        "calidad_pep":             "SI",
        "opera_cuenta_terceros":   "SI",
        "monto_significativo":     "SI",
        "pais_residencia":         "IRAN",
        "pais_actividad_comercial":"URUGUAY",
        "productos_servicios":     "SI",
    })
    print(json.dumps(r2, ensure_ascii=False, indent=2))
