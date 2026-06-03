"""
main_processor.py — Cerebro local del sistema.
Escucha tareas pendientes en Firestore y las despacha a los agentes.
Corre 24/7 en la PC local.
"""
import os
import time
import tempfile
import threading
from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore, storage as admin_storage

from agents.agent_compliance  import QuantumComplianceAgent
from agents.agent_markets     import QuantumMarketsAgent
from agents.agent_contracts   import QuantumContractsAgent
from agents.agent_legal_chat  import QuantumLegalChatAgent
from database.local_cache     import init_db, guardar_reporte_compliance, buscar_reporte_compliance
from paypal_service           import monitorear_suscripciones

GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_ADMIN_CREDENTIALS", "./serviceAccountKey.json")
FIREBASE_BUCKET      = os.getenv("FIREBASE_STORAGE_BUCKET", "agenteahc.firebasestorage.app")
POLL_INTERVAL_SECONDS = 10

# Costo en créditos por tipo de tarea
CREDIT_COSTS = {
    "compliance":       50,
    "markets":          30,
    "contracts":        75,
    "legal_chat":       30,
    "forensic":         25,
    "market_strategy":  75,
    "market_asset":     30,
    "market_audit":     75,
}


def init_firebase():
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred, {"storageBucket": FIREBASE_BUCKET})
    return firestore.client()


def _descargar_archivo(storage_path: str, nombre_archivo: str) -> str | None:
    try:
        ext    = os.path.splitext(nombre_archivo)[1] or ".tmp"
        bucket = admin_storage.bucket()
        blob   = bucket.blob(storage_path)
        tmp    = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.close()
        blob.download_to_filename(tmp.name)
        print(f"[STORAGE] Descargado: {nombre_archivo} → {tmp.name}")
        return tmp.name
    except Exception as e:
        print(f"[STORAGE] Error al descargar '{storage_path}': {e}")
        return None


def _descontar_creditos(db, uid: str, tipo: str):
    """Resta créditos del wallet del usuario de forma atómica."""
    costo = CREDIT_COSTS.get(tipo, 50)
    try:
        db.collection("usuarios").document(uid).update({
            "creditos": firestore.Increment(-costo),
            "ultima_actividad": firestore.SERVER_TIMESTAMP,
        })
        print(f"[CREDITOS] -{costo} créditos para uid={uid} (tarea: {tipo})")
    except Exception as e:
        print(f"[CREDITOS] No se pudieron descontar créditos: {e}")


def procesar_tarea_compliance(db, doc_ref, data: dict):
    agent = QuantumComplianceAgent(api_key=GEMINI_API_KEY)

    archivo_local = None
    if data.get("archivo_storage_path"):
        archivo_local = _descargar_archivo(
            data["archivo_storage_path"],
            data.get("archivo_nombre", "documento.tmp"),
        )

    try:
        resultado = agent.ejecutar_investigacion_profunda(data, archivo_path=archivo_local)
    finally:
        if archivo_local and os.path.exists(archivo_local):
            os.unlink(archivo_local)

    doc_ref.update({
        "status":      "COMPLETADO",
        "resultado":   resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "compliance")
    print(f"[COMPLIANCE] Completado: {data['nombre']}")


def procesar_tarea_markets(db, doc_ref, data: dict):
    agent    = QuantumMarketsAgent(api_key=GEMINI_API_KEY)
    resultado = agent.consultar_estrategia(data)

    doc_ref.update({
        "status":      "COMPLETADO",
        "resultado":   resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "markets")
    print(f"[MARKETS] Completado: {data.get('activo')}")


def procesar_tarea_contracts(db, doc_ref, data: dict):
    agent = QuantumContractsAgent(api_key=GEMINI_API_KEY)

    archivo_local = None
    if data.get("archivo_storage_path"):
        archivo_local = _descargar_archivo(
            data["archivo_storage_path"],
            data.get("archivo_nombre", "contrato.pdf"),
        )

    contexto = {
        "rol_cliente":        data.get("rol_cliente", ""),
        "notas_adicionales":  data.get("notas_adicionales", ""),
    }

    try:
        resultado = agent.analizar_contrato(archivo_local or "", contexto)
    finally:
        if archivo_local and os.path.exists(archivo_local):
            os.unlink(archivo_local)

    doc_ref.update({
        "status":      "COMPLETADO",
        "resultado":   resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "contracts")
    print(f"[CONTRACTS] Completado para uid={data.get('uid')}")


def procesar_tarea_market_strategy(db, doc_ref, data: dict):
    agent     = QuantumMarketsAgent(api_key=GEMINI_API_KEY)
    historial = data.get("historial", [])
    mensaje   = data.get("mensaje", "")
    respuesta = agent.disenar_estrategia(historial, mensaje)
    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    {"respuesta": respuesta},
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "market_strategy")
    print(f"[MARKET STRATEGY] Respuesta generada para uid={data.get('uid')}")


def procesar_tarea_market_asset(db, doc_ref, data: dict):
    agent    = QuantumMarketsAgent(api_key=GEMINI_API_KEY)
    consulta = data.get("consulta", "")
    resultado = agent.analizar_activo(consulta)
    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "market_asset")
    print(f"[MARKET ASSET] Análisis completado para uid={data.get('uid')}")


def procesar_tarea_market_audit(db, doc_ref, data: dict):
    agent = QuantumMarketsAgent(api_key=GEMINI_API_KEY)
    resultado = agent.auditar_cartera(
        composicion=data.get("composicion", ""),
        plazo=data.get("plazo", ""),
        notas=data.get("notas", ""),
    )
    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "market_audit")
    print(f"[MARKET AUDIT] Auditoría completada para uid={data.get('uid')}")


def procesar_tarea_forensic(db, doc_ref, data: dict):
    if not data.get("archivo_storage_path"):
        doc_ref.update({"status": "ERROR", "error": "No se adjuntó documento."})
        return

    archivo_local = _descargar_archivo(
        data["archivo_storage_path"],
        data.get("archivo_nombre", "documento.pdf"),
    )
    if not archivo_local:
        doc_ref.update({"status": "ERROR", "error": "No se pudo descargar el archivo."})
        return

    agent = QuantumComplianceAgent(api_key=GEMINI_API_KEY)
    try:
        resultado = agent.analizar_forense_standalone(archivo_local)
    finally:
        if os.path.exists(archivo_local):
            os.unlink(archivo_local)

    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "forensic")
    print(f"[FORENSIC] Completado para uid={data.get('uid')}")


def procesar_tarea_legal_chat(db, doc_ref, data: dict):
    agent = QuantumLegalChatAgent(api_key=GEMINI_API_KEY)

    archivo_local = None
    if data.get("archivo_storage_path"):
        archivo_local = _descargar_archivo(
            data["archivo_storage_path"],
            data.get("archivo_nombre", "documento.pdf"),
        )

    historial = data.get("historial", [])
    mensaje   = data.get("mensaje", "")

    try:
        respuesta = agent.responder(mensaje, historial, archivo_path=archivo_local)
    finally:
        if archivo_local and os.path.exists(archivo_local):
            os.unlink(archivo_local)

    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    {"respuesta": respuesta},
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "legal_chat")
    print(f"[LEGAL CHAT] Respuesta generada para uid={data.get('uid')}")


def main():
    init_db()
    db = init_firebase()
    print("[SISTEMA] Procesador local iniciado. Escuchando tareas en Firestore...")

    # Monitor PayPal en thread paralelo (no bloquea el procesador principal)
    t = threading.Thread(target=monitorear_suscripciones, args=(db,), daemon=True)
    t.start()

    while True:
        tareas = (
            db.collection("tareas_pendientes")
            .where(filter=firestore.FieldFilter("status", "==", "PENDIENTE"))
            .limit(5)
            .stream()
        )

        for tarea in tareas:
            data    = tarea.to_dict()
            doc_ref = db.collection("tareas_pendientes").document(tarea.id)
            doc_ref.update({"status": "EN_PROCESO"})

            tipo = data.get("tipo")
            try:
                if tipo == "compliance":
                    procesar_tarea_compliance(db, doc_ref, data)
                elif tipo == "markets":
                    procesar_tarea_markets(db, doc_ref, data)
                elif tipo == "contracts":
                    procesar_tarea_contracts(db, doc_ref, data)
                elif tipo == "legal_chat":
                    procesar_tarea_legal_chat(db, doc_ref, data)
                elif tipo == "forensic":
                    procesar_tarea_forensic(db, doc_ref, data)
                elif tipo == "market_strategy":
                    procesar_tarea_market_strategy(db, doc_ref, data)
                elif tipo == "market_asset":
                    procesar_tarea_market_asset(db, doc_ref, data)
                elif tipo == "market_audit":
                    procesar_tarea_market_audit(db, doc_ref, data)
                else:
                    print(f"[WARN] Tipo desconocido: {tipo}")
                    doc_ref.update({"status": "ERROR", "error": "Tipo desconocido"})
            except Exception as e:
                print(f"[ERROR] Tarea {tarea.id}: {e}")
                doc_ref.update({"status": "ERROR", "error": str(e)})

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
