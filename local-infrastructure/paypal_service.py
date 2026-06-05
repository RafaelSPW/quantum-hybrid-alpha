"""
paypal_service.py — Monitor de pagos únicos PayPal.
Corre en thread paralelo dentro de main_processor.
Detecta pagos pendientes en Firestore, valida el Order con la API
de PayPal Live y acredita los créditos al usuario.
"""
import os
import time
import base64
import requests


PAYPAL_CLIENT_ID     = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE          = "https://api-m.paypal.com"  # Live (cambiar a api-m.sandbox.paypal.com para tests)


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


def _verificar_orden(order_id: str) -> bool:
    """Retorna True si la Order de PayPal está en estado COMPLETED."""
    token = _paypal_token()
    r = requests.get(
        f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if r.status_code == 404:
        return False
    r.raise_for_status()
    return r.json().get("status", "") == "COMPLETED"


def monitorear_suscripciones(db) -> None:
    """
    Bucle infinito (corre en thread daemon).
    Cada 15 s escanea la colección pagos_pendientes.
    Por cada doc: valida la Order con PayPal → acredita créditos → mueve a pagos.
    """
    from firebase_admin import firestore as fa_fs

    print("[PAYPAL] Servicio de acreditación de pagos iniciado.")

    while True:
        try:
            docs = list(db.collection("pagos_pendientes").stream())
            for doc in docs:
                data     = doc.to_dict()
                doc_id   = doc.id
                uid      = data.get("uid", "")
                order_id = data.get("order_id", "")
                pack_id  = data.get("pack_id", "")
                creditos = data.get("creditos", 0)

                if not uid or not order_id or not creditos:
                    continue

                print(f"[PAYPAL] Verificando order_id={order_id} pack={pack_id} uid={uid}")
                try:
                    if _verificar_orden(order_id):
                        # 1. Sumar créditos (atómico) sin pisar el plan existente
                        db.collection("usuarios").document(uid).update({
                            "creditos":         fa_fs.Increment(creditos),
                            "ultima_actividad": fa_fs.SERVER_TIMESTAMP,
                        })

                        # 2. Registrar en colección pagos (historial)
                        db.collection("pagos").add({
                            "pack_id":    pack_id,
                            "order_id":  order_id,
                            "creditos":  creditos,
                            "uid":       uid,
                            "email":     data.get("email", ""),
                            "status":    "completado",
                            "pagado_en": fa_fs.SERVER_TIMESTAMP,
                        })

                        # 3. Borrar de pendientes
                        db.collection("pagos_pendientes").document(doc_id).delete()

                        print(f"[PAYPAL] ✅ Pack '{pack_id}' acreditado → uid={uid} | +{creditos} créditos")
                    else:
                        print(f"[PAYPAL] ⏳ Order {order_id} aún no COMPLETED. Reintentando en 15 s...")

                except requests.HTTPError as e:
                    print(f"[PAYPAL] HTTP error verificando order {order_id}: {e}")
                except Exception as e:
                    print(f"[PAYPAL] Error procesando order {order_id}: {e}")

        except Exception as e:
            print(f"[PAYPAL] Error general en monitor: {e}")

        time.sleep(15)
