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
from decimal import Decimal
from sanctions import (
    MatrizRiesgo,
    actualizar_listas,
    buscar_en_ofac,
    screening_pep_adverse,
    construir_reporte,
    construir_legajo_unificado,
    extraer_documento,
    analizar_fondos,
    PerfilCliente,
    KMSNotConfiguredError,
)

GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
FIREBASE_BUCKET      = os.getenv("FIREBASE_STORAGE_BUCKET", "agenteahc.firebasestorage.app")

# Soporta credenciales como base64 (Cloud Run), JSON string, o archivo físico (local)
_FIREBASE_CREDENTIALS_B64  = os.getenv("FIREBASE_CREDENTIALS_B64")
_FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")
_FIREBASE_CREDENTIALS_FILE = os.getenv("FIREBASE_ADMIN_CREDENTIALS", "./serviceAccountKey.json")
POLL_INTERVAL_SECONDS = 10

# Costo en créditos por tipo de tarea
CREDIT_COSTS = {
    "compliance":        50,
    "markets":           30,
    "contracts":         75,
    "legal_chat":        30,
    "forensic":          25,
    "market_strategy":   75,
    "market_asset":      30,
    "market_audit":      75,
    "senaclaft_riesgo":  20,
    "senaclaft_ofac":    40,
    "senaclaft_fondos":  30,
    "senaclaft_legajo":  10,   # agregación de resultados ya pagados
}


def init_firebase():
    if _FIREBASE_CREDENTIALS_B64:
        import base64, json
        cred = credentials.Certificate(json.loads(base64.b64decode(_FIREBASE_CREDENTIALS_B64)))
    elif _FIREBASE_CREDENTIALS_JSON:
        import json
        cred = credentials.Certificate(json.loads(_FIREBASE_CREDENTIALS_JSON))
    else:
        cred = credentials.Certificate(_FIREBASE_CREDENTIALS_FILE)
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
    modo  = data.get("modo", "individual")

    contexto = {
        "rol_cliente":       data.get("rol_cliente", ""),
        "notas_adicionales": data.get("notas_adicionales", ""),
    }

    if modo == "comparativo":
        archivo1_local = None
        archivo2_local = None
        if data.get("archivo_storage_path"):
            archivo1_local = _descargar_archivo(
                data["archivo_storage_path"],
                data.get("archivo_nombre", "contrato_original.pdf"),
            )
        if data.get("archivo2_storage_path"):
            archivo2_local = _descargar_archivo(
                data["archivo2_storage_path"],
                data.get("archivo2_nombre", "contrato_recibido.pdf"),
            )
        try:
            resultado = agent.analizar_contratos_comparativos(
                archivo1_local or "", archivo2_local or "", contexto
            )
        finally:
            if archivo1_local and os.path.exists(archivo1_local):
                os.unlink(archivo1_local)
            if archivo2_local and os.path.exists(archivo2_local):
                os.unlink(archivo2_local)
    else:
        archivo_local = None
        if data.get("archivo_storage_path"):
            archivo_local = _descargar_archivo(
                data["archivo_storage_path"],
                data.get("archivo_nombre", "contrato.pdf"),
            )
        try:
            resultado = agent.analizar_contrato(archivo_local or "", contexto)
        finally:
            if archivo_local and os.path.exists(archivo_local):
                os.unlink(archivo_local)

    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "contracts")
    print(f"[CONTRACTS] Completado ({modo}) para uid={data.get('uid')}")


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


def procesar_tarea_senaclaft_riesgo(db, doc_ref, data: dict):
    """Evalúa el riesgo del cliente con la matriz SENACLAFT (7 factores, Ley 19.574)."""
    cliente = {
        "numero_cliente":           data.get("numero_cliente", ""),
        "nombre_cliente":           data.get("nombre_cliente", ""),
        "actividad_economica":      data.get("actividad_economica", ""),
        "calidad_pep":              data.get("calidad_pep", "NO"),
        "opera_cuenta_terceros":    data.get("opera_cuenta_terceros", "NO"),
        "monto_significativo":      data.get("monto_significativo", "NO"),
        "pais_residencia":          data.get("pais_residencia", ""),
        "pais_actividad_comercial": data.get("pais_actividad_comercial", ""),
        "productos_servicios":      data.get("productos_servicios", "NO"),
    }
    m = MatrizRiesgo()
    resultado = m.evaluar(cliente)
    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    resultado,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "senaclaft_riesgo")
    print(f"[SENACLAFT RIESGO] {cliente['nombre_cliente']} → {resultado['riesgo']} ({resultado['total_ponderado']})")


def procesar_tarea_senaclaft_ofac(db, doc_ref, data: dict):
    """Screening OFAC SDN + PEP con listas oficiales descargadas (Módulo 1+2 sanctions)."""
    nombre   = data.get("nombre", "").strip()
    umbral   = int(data.get("umbral", 85))

    try:
        print(f"[SENACLAFT OFAC] Actualizando listas OFAC...")
        # Pasa el bucket GCS para backup persistente entre deploys de Cloud Run.
        # Si OFAC rechaza la conexión, carga desde GCS. Si descarga OK, hace backup.
        gcs_bucket = admin_storage.bucket(FIREBASE_BUCKET)
        ofac_db = actualizar_listas(gcs_bucket=gcs_bucket)
    except Exception as e:
        doc_ref.update({"status": "ERROR", "error": f"Error descargando listas OFAC: {e}"})
        return

    print(f"[SENACLAFT OFAC] Buscando '{nombre}' en OFAC (umbral={umbral})...")
    coincidencias = buscar_en_ofac(nombre, ofac_db, umbral=umbral)

    print(f"[SENACLAFT OFAC] Screening PEP/medios adversos para '{nombre}'...")
    try:
        resultado_pep = screening_pep_adverse(nombre)
    except Exception as e:
        resultado_pep = {"error": str(e), "indicadores_pep": [], "confianza": "bajo", "nota": "Error en screening PEP"}

    reporte = construir_reporte(nombre, coincidencias, resultado_pep, ofac_db)

    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    reporte,
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, data.get("uid", ""), "senaclaft_ofac")
    print(f"[SENACLAFT OFAC] Completado: {len(coincidencias)} coincidencias para '{nombre}'")


def procesar_tarea_senaclaft_fondos(db, doc_ref, data: dict):
    """Extrae montos de un PDF de origen de fondos y evalúa congruencia con el perfil declarado."""
    uid          = data.get("uid", "")
    storage_path = data.get("archivo_storage_path", "")
    if not storage_path:
        doc_ref.update({"status": "ERROR", "error": "archivo_storage_path requerido para análisis de fondos"})
        return

    archivo_local = _descargar_archivo(storage_path, data.get("archivo_nombre", "fondos.pdf"))
    if not archivo_local:
        doc_ref.update({"status": "ERROR", "error": "No se pudo descargar el archivo desde Storage"})
        return

    try:
        extraccion = extraer_documento(archivo_local)
        extraccion.confirmado_por_investigador = True  # el investigador envió conscientemente

        perfil = PerfilCliente(
            actividad_declarada=data.get("actividad_economica", "SIN_ACTIVIDAD"),
            ingresos_anuales_declarados_usd=Decimal(str(data.get("ingresos_anuales_usd", 0))),
            patrimonio_declarado_usd=Decimal(str(data.get("patrimonio_declarado_usd", 0))),
        )
        analisis = analizar_fondos(extraccion, perfil)

        resultado = {
            "total_documentado_usd":     str(analisis.total_documentado_usd),
            "total_perfil_usd":          str(analisis.total_perfil_usd),
            "ratio_discrepancia":        analisis.ratio_discrepancia,
            "bandera_incongruencia":     analisis.bandera_incongruencia,
            "umbral_usado":              analisis.umbral_usado,
            "descripcion_bandera":       analisis.descripcion_bandera,
            "consistencia_perfil_origen": analisis.consistencia_perfil_origen,
            "montos_confirmados":        analisis.montos_confirmados,
            "metodo_extraccion":         extraccion.metodo_extraccion,
            "confianza_extraccion":      extraccion.confianza,
            "advertencias_extraccion":   extraccion.advertencias,
            "timestamp_analisis":        analisis.timestamp_analisis,
            "nota":                      analisis.nota,
            "requiere_revision_humana":  True,
            "decision_oficial_cumplimiento": None,
        }
        doc_ref.update({
            "status":       "COMPLETADO",
            "resultado":    resultado,
            "procesado_en": firestore.SERVER_TIMESTAMP,
        })
        _descontar_creditos(db, uid, "senaclaft_fondos")
        print(
            f"[SENACLAFT FONDOS] {data.get('nombre_cliente','?')} — "
            f"bandera={analisis.bandera_incongruencia} ratio={analisis.ratio_discrepancia} "
            f"metodo={extraccion.metodo_extraccion}"
        )
    finally:
        if archivo_local and os.path.exists(archivo_local):
            os.unlink(archivo_local)


def _verificar_ownership_tareas(db, uid: str, *task_ids: str) -> tuple[bool, str]:
    """
    Verifica que todas las tareas referenciadas pertenecen al mismo uid.
    Previene IDOR: un usuario no puede referenciar tareas ajenas para construir un legajo.
    task_ids vacíos o None se ignoran.
    """
    for task_id in task_ids:
        if not task_id:
            continue
        doc = db.collection("tareas_pendientes").document(task_id).get()
        if not doc.exists:
            return False, f"Tarea '{task_id}' no encontrada"
        task_uid = doc.to_dict().get("uid")
        if task_uid != uid:
            return False, (
                f"Tarea '{task_id}' pertenece a otro usuario — IDOR rechazado. "
                "El legajo solo puede construirse desde tareas del mismo usuario."
            )
    return True, ""


def procesar_tarea_senaclaft_legajo(db, doc_ref, data: dict):
    """
    Construye el Legajo de Cumplimiento unificado cruzando resultados de tareas previas.

    Seguridad IDOR: verifica que screening_task_id, riesgo_task_id y fondos_task_id
    (si presente) pertenecen todos al mismo uid que esta tarea. Cualquier mismatch
    rechaza la operación con 403 lógico — no se construye el legajo.

    El legajo resultante se escribe en la colección 'legajos' con owner_uid = uid,
    para que las Firestore Security Rules puedan aislarlo por usuario.
    """
    uid        = data.get("uid", "")
    id_cliente = data.get("id_cliente", "").strip()
    scr_id     = data.get("screening_task_id", "").strip()
    riesgo_id  = data.get("riesgo_task_id", "").strip()
    fondos_id  = data.get("fondos_task_id", "").strip()

    if not id_cliente:
        doc_ref.update({"status": "ERROR", "error": "id_cliente requerido"})
        return
    if not scr_id or not riesgo_id:
        doc_ref.update({"status": "ERROR", "error": "screening_task_id y riesgo_task_id son obligatorios"})
        return

    # ── Verificación IDOR ─────────────────────────────────────────────────────
    ok, motivo = _verificar_ownership_tareas(db, uid, scr_id, riesgo_id, fondos_id)
    if not ok:
        print(f"[LEGAJO] IDOR rechazado para uid={uid}: {motivo}")
        doc_ref.update({"status": "ERROR", "error": f"Acceso denegado: {motivo}"})
        return

    # ── Leer resultados de tareas referenciadas ────────────────────────────────
    scr_doc    = db.collection("tareas_pendientes").document(scr_id).get()
    riesgo_doc = db.collection("tareas_pendientes").document(riesgo_id).get()

    if not scr_doc.exists or not riesgo_doc.exists:
        doc_ref.update({"status": "ERROR", "error": "Tarea referenciada no encontrada o fue eliminada"})
        return

    screening_ofac    = scr_doc.to_dict().get("resultado", {})
    evaluacion_riesgo = riesgo_doc.to_dict().get("resultado", {})

    if not screening_ofac or not evaluacion_riesgo:
        doc_ref.update({"status": "ERROR", "error": "Tarea referenciada sin resultado (aún PENDIENTE o ERROR)"})
        return

    # ── Fondos: solo si confirmado_por_investigador ───────────────────────────
    analisis_fondos = None
    if fondos_id:
        fondos_doc = db.collection("tareas_pendientes").document(fondos_id).get()
        if fondos_doc.exists:
            fondos_resultado = fondos_doc.to_dict().get("resultado", {})
            if fondos_resultado.get("confirmado_por_investigador", False):
                analisis_fondos = fondos_resultado
            else:
                print(f"[LEGAJO] fondos_task '{fondos_id}' ignorado — no confirmado por investigador")

    # ── Construir legajo ──────────────────────────────────────────────────────
    try:
        legajo = construir_legajo_unificado(
            id_cliente        =id_cliente,
            screening_ofac    =screening_ofac,
            evaluacion_riesgo =evaluacion_riesgo,
            analisis_fondos   =analisis_fondos,
            owner_uid         =uid,
            usuario_id        =uid,
        )
    except KMSNotConfiguredError as e:
        doc_ref.update({"status": "ERROR", "error": f"KMS no configurado: {e}"})
        return
    except Exception as e:
        doc_ref.update({"status": "ERROR", "error": f"Error construyendo legajo: {e}"})
        return

    # ── Escribir en colección legajos (owner_uid para Firestore Rules) ─────────
    legajo_doc = db.collection("legajos").document()
    legajo_doc.set({
        **legajo,
        "owner_uid":  uid,        # garantiza aislamiento multi-tenant
        "creado_en":  firestore.SERVER_TIMESTAMP,
    })

    doc_ref.update({
        "status": "COMPLETADO",
        "resultado": {
            "legajo_id":      legajo_doc.id,
            "id_evaluacion":  legajo["id_evaluacion"],
            "estado":         legajo["estado"],
            "vigencia_hasta": legajo["vigencia_hasta"],
        },
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    _descontar_creditos(db, uid, "senaclaft_legajo")
    print(
        f"[LEGAJO] {legajo_doc.id} creado para cliente '{id_cliente}' "
        f"(uid={uid}, estado={legajo['estado']})"
    )


def procesar_tarea_generar_articulo(db, doc_ref, data: dict):
    """Genera un artículo con Gemini y lo guarda en la colección 'articulos' (sin publicar)."""
    from google import genai
    from google.genai import types
    import json

    tema         = data.get("tema", "Inteligencia financiera y compliance")
    tag          = data.get("tag", "General")
    instrucciones = data.get("instrucciones", "").strip()
    extra        = f"\nInstrucciones adicionales del editor: {instrucciones}" if instrucciones else ""

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""Eres un redactor senior especializado en finanzas, compliance y mercados de capitales para AHC Intelligence, plataforma de inteligencia financiera orientada a asesores de riesgo latinoamericanos.

Escribí un artículo profesional sobre: {tema}
Categoría: {tag}{extra}

Requisitos:
- Título atractivo y profesional (sin clickbait)
- Resumen ejecutivo de 2-3 oraciones directo al punto
- 4 a 6 secciones con subtítulos claros
- Lenguaje profesional pero accesible para asesores financieros
- Entre 600 y 900 palabras de contenido
- Orientado al mercado latinoamericano (Argentina, Uruguay, México principalmente)
- Párrafos cortos, aptos para lectura en mobile

Respondé ESTRICTAMENTE en JSON:
{{
  "titulo": "título del artículo",
  "resumen": "resumen ejecutivo de 2-3 oraciones",
  "tag": "{tag}",
  "contenido_html": "contenido completo en HTML. Solo el body. Usar <h2> para secciones, <p> para párrafos, <strong> para énfasis, <ul>/<li> para listas. Sin <html>, <head>, ni <body>."
}}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )
    resultado = json.loads(response.text)

    art_ref = db.collection("articulos").document()
    art_ref.set({
        "titulo":          resultado.get("titulo", tema),
        "resumen":         resultado.get("resumen", ""),
        "tag":             resultado.get("tag", tag),
        "contenido_html":  resultado.get("contenido_html", ""),
        "publicado":       False,
        "generado_por_ia": True,
        "creado_en":       firestore.SERVER_TIMESTAMP,
        "actualizado_en":  firestore.SERVER_TIMESTAMP,
    })

    doc_ref.update({
        "status":       "COMPLETADO",
        "resultado":    {"articulo_id": art_ref.id},
        "procesado_en": firestore.SERVER_TIMESTAMP,
    })
    print(f"[ARTICULO] Generado: '{resultado.get('titulo')}' (id: {art_ref.id})")


def _recuperar_tareas_huerfanas(db) -> None:
    """
    Al startup, resetea a PENDIENTE las tareas que quedaron en EN_PROCESO por una
    revisión anterior de Cloud Run que fue reemplazada mientras procesaba.
    Es seguro hacerlo al arrancar porque el container anterior ya fue terminado.
    """
    try:
        huerfanas = (
            db.collection("tareas_pendientes")
            .where(filter=firestore.FieldFilter("status", "==", "EN_PROCESO"))
            .stream()
        )
        count = 0
        for t in huerfanas:
            db.collection("tareas_pendientes").document(t.id).update({"status": "PENDIENTE"})
            count += 1
        if count:
            print(f"[SISTEMA] {count} tarea(s) huérfana(s) EN_PROCESO → PENDIENTE (retomadas)")
    except Exception as e:
        print(f"[SISTEMA] Error recuperando tareas huérfanas: {e}")


def main():
    init_db()

    # Reintentar la conexión a Firestore si falla al arrancar
    db = None
    for intento in range(10):
        try:
            db = init_firebase()
            db.collection("tareas_pendientes").limit(1).get()  # ping para verificar conexión
            print("[SISTEMA] Procesador local iniciado. Escuchando tareas en Firestore...")
            break
        except Exception as e:
            wait = 2 ** intento
            print(f"[SISTEMA] Error al conectar con Firestore (intento {intento+1}/10): {e}. Reintentando en {wait}s...")
            time.sleep(wait)
            try:
                firebase_admin.get_app()
                firebase_admin.delete_app(firebase_admin.get_app())
            except Exception:
                pass

    if db is None:
        print("[FATAL] No se pudo conectar a Firestore después de 10 intentos. Abortando.")
        return

    # Recuperar tareas que quedaron EN_PROCESO si la revisión anterior fue reemplazada
    _recuperar_tareas_huerfanas(db)

    # Monitor PayPal en thread paralelo (no bloquea el procesador principal)
    t = threading.Thread(target=monitorear_suscripciones, args=(db,), daemon=True)
    t.start()

    while True:
        try:
            tareas = (
                db.collection("tareas_pendientes")
                .where(filter=firestore.FieldFilter("status", "==", "PENDIENTE"))
                .limit(5)
                .stream()
            )

            for tarea in tareas:
                data    = tarea.to_dict()
                doc_ref = db.collection("tareas_pendientes").document(tarea.id)
                doc_ref.update({
                    "status": "EN_PROCESO",
                    "en_proceso_desde": firestore.SERVER_TIMESTAMP,
                })

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
                    elif tipo == "generar_articulo":
                        procesar_tarea_generar_articulo(db, doc_ref, data)
                    elif tipo == "senaclaft_riesgo":
                        procesar_tarea_senaclaft_riesgo(db, doc_ref, data)
                    elif tipo == "senaclaft_ofac":
                        procesar_tarea_senaclaft_ofac(db, doc_ref, data)
                    elif tipo == "senaclaft_fondos":
                        procesar_tarea_senaclaft_fondos(db, doc_ref, data)
                    elif tipo == "senaclaft_legajo":
                        procesar_tarea_senaclaft_legajo(db, doc_ref, data)
                    else:
                        print(f"[WARN] Tipo desconocido: {tipo}")
                        doc_ref.update({"status": "ERROR", "error": "Tipo desconocido"})
                except Exception as e:
                    print(f"[ERROR] Tarea {tarea.id}: {e}")
                    doc_ref.update({"status": "ERROR", "error": str(e)})

        except Exception as e:
            print(f"[ERROR] Poll Firestore: {e}. Reinicializando cliente en {POLL_INTERVAL_SECONDS}s...")
            time.sleep(POLL_INTERVAL_SECONDS)
            try:
                firebase_admin.delete_app(firebase_admin.get_app())
            except Exception:
                pass
            try:
                db = init_firebase()
                print("[SISTEMA] Cliente Firestore reinicializado.")
            except Exception as e2:
                print(f"[ERROR] No se pudo reinicializar Firestore: {e2}")
            continue

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
