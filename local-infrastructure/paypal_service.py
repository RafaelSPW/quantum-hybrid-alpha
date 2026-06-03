"""
paypal_service.py — Monitor de suscripciones PayPal.
Corre en thread paralelo dentro de main_processor.
Detecta suscripciones pendientes en Firestore, las valida con la API
de PayPal Live y activa los créditos del usuario.
"""
import os
import time
import base64
import requests


PAYPAL_CLIENT_ID     = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE          = "https://api-m.paypal.com"  # Live (cambiar a api-m.sandbox.paypal.com para tests)

PLAN_CREDITOS = {
    "starter":      1500,
    "professional": 5000,
    "enterprise":   25000,
}


def _paypal_token() -> str:
    """Obtiene Bearer token de PayPal OAuth2."""
    auth = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        data="grant_type=client_credentials",
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _verificar_suscripcion(subscription_id: str) -> bool:
    """Retorna True si la suscripción está ACTIVE o APPROVED en PayPal."""
    token = _paypal_token()
    r = requests.get(
        f"{PAYPAL_BASE}/v1/billing/subscriptions/{subscription_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    status = r.json().get("status", "")
    return status in ("ACTIVE", "APPROVED")


def monitorear_suscripciones(db) -> None:
    """
    Bucle infinito (corre en thread daemon).
    Cada 30 s escanea la colección suscripciones_pendientes.
    Por cada doc: valida con PayPal → actualiza usuario → mueve a suscripciones.
    """
    from firebase_admin import firestore as fa_fs

    print("[PAYPAL] Servicio de activación de suscripciones iniciado.")

    while True:
        try:
            docs = list(db.collection("suscripciones_pendientes").stream())
            for doc in docs:
                data       = doc.to_dict()
                uid        = doc.id
                plan       = data.get("plan", "")
                sub_id     = data.get("subscription_id", "")

                if not plan or not sub_id:
                    continue

                print(f"[PAYPAL] Verificando sub_id={sub_id} plan={plan} uid={uid}")
                try:
                    if _verificar_suscripcion(sub_id):
                        creditos = PLAN_CREDITOS.get(plan, 1500)

                        # 1. Actualizar documento del usuario
                        db.collection("usuarios").document(uid).update({
                            "plan":                   plan,
                            "creditos":               creditos,
                            "paypal_subscription_id": sub_id,
                            "plan_activado_en":       fa_fs.SERVER_TIMESTAMP,
                        })

                        # 2. Registrar en colección suscripciones (historial)
                        db.collection("suscripciones").document(uid).set({
                            "plan":            plan,
                            "subscription_id": sub_id,
                            "creditos":        creditos,
                            "status":          "activo",
                            "activado_en":     fa_fs.SERVER_TIMESTAMP,
                        })

                        # 3. Borrar de pendientes
                        db.collection("suscripciones_pendientes").document(uid).delete()

                        print(f"[PAYPAL] ✅ Plan '{plan}' activado → uid={uid} | {creditos} créditos asignados")
                    else:
                        print(f"[PAYPAL] ⏳ Suscripción {sub_id} aún no activa. Reintentando en 30 s...")

                except requests.HTTPError as e:
                    print(f"[PAYPAL] HTTP error verificando {sub_id}: {e}")
                except Exception as e:
                    print(f"[PAYPAL] Error procesando {sub_id}: {e}")

        except Exception as e:
            print(f"[PAYPAL] Error general en monitor: {e}")

        time.sleep(30)
