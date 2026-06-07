# AHC Intelligence — Quantum Compliance SaaS

Plataforma SaaS de inteligencia financiera para asesores de riesgo y compliance.  
Arquitectura cloud-native: frontend en Firebase Hosting + procesamiento IA en Google Cloud Run.

**Frontend:** https://agenteahc.web.app  
**Backend:** https://quantum-processor-wbjf4jkeqq-uc.a.run.app (Cloud Run, privado)

---

## Arquitectura

```
FIREBASE (agenteahc)
──────────────────────────────────────────────────────────────
Hosting        app.js + 11 HTML — SPA del asesor
Firestore      Base de datos en tiempo real (tareas, usuarios, suscripciones)
Storage        Archivos subidos por el usuario (PDF, JPG, PNG)
Auth           Google Sign-In (primario) + Email/Password (secundario) con verificación de email

GOOGLE CLOUD RUN (quantumaits · us-central1)
──────────────────────────────────────────────────────────────
quantum-processor   min-instances=1 · siempre activo · 1 GB RAM
  entrypoint.py         Health check HTTP (PORT) + lanza main_processor
  main_processor.py     Polling loop (10 s) + thread PayPal (30 s)
  paypal_service.py     Monitor de suscripciones PayPal Live
  agents/
  ├── agent_compliance.py          Gemini 2.5 Flash + Google Search (KYC / Forense)
  ├── agent_contracts.py           Gemini 2.5 Flash (auditoría de contratos)
  ├── agent_legal_chat.py          Gemini 2.5 Flash (guía regulatoria)
  ├── agent_markets.py             Gemini 2.5 Flash + Google Search (mercados)
  └── fuentes_oficiales_por_pais.py  Mapeo de fuentes regulatorias por país
  database/
  └── local_cache.py               SQLite — caché de reportes KYC

FIRESTORE (colecciones)
──────────────────────────────────────────────────────────────
tareas_pendientes        Tareas creadas por frontend → procesadas por Cloud Run
usuarios                 Créditos, plan, suscripción PayPal del usuario
suscripciones_pendientes Activación PayPal pendiente de validación
suscripciones            Historial de suscripciones activas
leads_institucionales    Solicitudes tier Enterprise Dedicado
```

---

## Registro de cambios

### Junio 2026 — Auth dual + copy de registro

**Archivos modificados:** `public/app.js`, `public/index.html`

#### (a) Copy / gancho de registro
- Botón del header en `index.html` cambiado de "Iniciar sesión" → **"Registrate gratis"**
- Bloque CTA visible en el hero de `index.html` (solo usuarios no logueados): botón grande + texto "Empezá con créditos gratis incluidos · Sin tarjeta · Sin compromisos."
- Toast verde post-aceptación de T&C: *"¡Listo! Ya tenés tus créditos gratis para empezar. Subí tu primer documento."*

#### (b) Auth dual: Google + Email/Contraseña
- `loginGoogle()` ahora abre `abrirModalAuth()` → todos los botones existentes en los 11 HTML heredan el modal sin cambios en el HTML de módulos
- Modal unificado con:
  - **"Continuar con Google"** (primario)
  - Separador "o"
  - Formulario email/contraseña con toggle **Registrarse / Iniciar sesión**
  - Link **"¿Olvidaste tu contraseña?"** → `sendPasswordResetEmail()`
  - Mensajes de error en español para todos los códigos de Firebase Auth
- `_triggerGoogleSignIn()` maneja el popup de Google internamente

#### (c) Verificación de email (solo usuarios email/contraseña)
- Post-registro: `sendEmailVerification()` se llama automáticamente antes de cerrar el modal
- `onAuthStateChanged` detecta `providerId === "password" && !emailVerified` → muestra overlay bloqueante
- Overlay `mostrarVerificacionPendiente(user)`:
  - **"Ya verifiqué"** → `auth.currentUser.reload()` + chequea `emailVerified`
  - **"Reenviar correo"** → `sendEmailVerification()` con cooldown de 30 s
  - **"¿No es tu email? Cerrar sesión"** → cierra sesión y limpia overlay
- `verificarCreditos()` tiene la misma guardia como red de seguridad antes de cualquier módulo
- **Usuarios Google no se ven afectados** — `emailVerified` siempre es `true` para Google Sign-In

---

## Módulos y Créditos

| Módulo | Agente | Créditos | Descripción |
|--------|--------|----------|-------------|
| Compliance KYC/AML | `agent_compliance.py` | 50 | Rastreo transfronterizo OFAC, PEPs, redes corporativas |
| Análisis Forense | `agent_compliance.py` | 25 | Autenticación multimodal 4 capas (metadatos, ELA, IA, tipografía) |
| Auditoría de Contratos | `agent_contracts.py` | 75 | Cláusulas leoninas, vacíos legales, riesgo comercial |
| Guía Regulatoria (chat) | `agent_legal_chat.py` | 30 | Consulta normativa con documentos adjuntos |
| Estrategias AI (chat) | `agent_markets.py` | 75 | Portafolios conversacionales a medida |
| Análisis de Activos | `agent_markets.py` | 30 | Análisis técnico/fundamental de un activo |
| Auditoría de Carteras | `agent_markets.py` | 75 | Diagnóstico + rebalanceo de portafolio |

### Planes

| Plan | Créditos/mes | PayPal Plan ID |
|------|-------------|----------------|
| Trial | 150 (7 días) | — Gratis — |
| Starter | 1.500 | `P-8GL53584124263225NIRKO6Q` |
| Professional | 5.000 | `P-0GF18564ED3901707NIRKYBQ` |
| Enterprise | 25.000 | `P-9L677248CE864754UNIRKY2I` |
| Institutional Custom | Ilimitado | Trato privado · SWIFT |

---

## Flujo de una tarea

```
Browser                   Firestore                  Cloud Run (quantum-processor)
───────                   ─────────                  ─────────────────────────────
1. Asesor envía formulario
2. app.js escribe tarea ──► tareas_pendientes
                              status: PENDIENTE
                                                  3. Polling detecta tarea (10 s)
                                                  4. doc → status: EN_PROCESO
                                                  5. Llama agente IA (Gemini)
                                                  6. Si archivo: descarga de
                                                     Firebase Storage, analiza,
                                                     borra tmp
                          tareas_pendientes ◄──── 7. status: COMPLETADO
                              resultado: {...}        descuenta créditos
8. onSnapshot recibe
   el resultado en RT
```

### Caché KYC

Si el documento ya fue investigado, `agent_compliance.py` devuelve el resultado
desde SQLite local sin llamar a Gemini (costo $0). Los resultados `SIMULADO` se
descartan y se re-analizan con datos reales.

---

## Deploy

### Frontend (Firebase Hosting + Firestore rules)

```bash
cd cloud-infrastructure
firebase deploy --only hosting,firestore --project agenteahc
```

### Backend (Google Cloud Run)

**Primera vez — habilitar APIs y crear repositorio:**
```bash
gcloud config set project quantumaits
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
gcloud artifacts repositories create quantum-compliance --repository-format=docker --location=us-central1
```

**Build y deploy:**
```bash
cd local-infrastructure
gcloud builds submit --tag us-central1-docker.pkg.dev/quantumaits/quantum-compliance/processor:latest

gcloud run deploy quantum-processor \
  --image=us-central1-docker.pkg.dev/quantumaits/quantum-compliance/processor:latest \
  --region=us-central1 --platform=managed \
  --no-allow-unauthenticated \
  --min-instances=1 --max-instances=1 \
  --memory=1Gi --cpu=1 --timeout=540 \
  --update-env-vars="GEMINI_API_KEY=...,PAYPAL_CLIENT_ID=...,PAYPAL_CLIENT_SECRET=...,FIREBASE_STORAGE_BUCKET=agenteahc.firebasestorage.app,FIREBASE_CREDENTIALS_B64=<base64 de serviceAccountKey.json>,PYTHONUNBUFFERED=1" \
  --project quantumaits
```

**Ver logs en tiempo real:**
```bash
gcloud run services logs tail quantum-processor --region=us-central1 --project quantumaits
```

### Variables de entorno requeridas en Cloud Run

| Variable | Descripción |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio → aistudio.google.com/app/apikey |
| `PAYPAL_CLIENT_ID` | PayPal Developer → Apps & Credentials |
| `PAYPAL_CLIENT_SECRET` | PayPal Developer → Apps & Credentials |
| `FIREBASE_STORAGE_BUCKET` | `agenteahc.firebasestorage.app` |
| `FIREBASE_CREDENTIALS_B64` | `base64 -w0 serviceAccountKey.json` |
| `PYTHONUNBUFFERED` | `1` (logs visibles en tiempo real) |

---

## Setup local (desarrollo)

**Requisitos:** Python 3.11+, cuenta Firebase, cuenta Google Cloud, cuenta PayPal Developer.

```bash
cd local-infrastructure
pip install -r requirements.txt
```

Crear `local-infrastructure/.env`:
```env
GEMINI_API_KEY=...
FIREBASE_ADMIN_CREDENTIALS=./serviceAccountKey.json
FIREBASE_STORAGE_BUCKET=agenteahc.firebasestorage.app
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

Descargar `serviceAccountKey.json` desde:  
Firebase Console → Configuración → Cuentas de servicio → Generar nueva clave privada

```bash
python main_processor.py
```

---

## Seguridad

- `.env` y `serviceAccountKey.json` en `.gitignore` — nunca subir al repo
- `FIREBASE_CREDENTIALS_B64` se pasa en base64 para evitar problemas de escaping con el private key
- Reglas Firestore: cada usuario solo accede a sus propios documentos (validación por UID)
- `tareas_pendientes`: create requiere `uid == auth.uid`; read/update/delete requieren ser el propietario
- Headers HTTP: `X-Frame-Options: DENY`, `HSTS`, `X-Content-Type-Options`, `Referrer-Policy`
- Créditos: decrementos atómicos con `FieldValue.increment()` vía Admin SDK (no manipulables desde frontend)
- Validación de tipo de archivo en frontend: solo PDF, JPG, PNG

---

## Estructura del Repositorio

```
quantum-compliance-saas/
├── cloud-infrastructure/
│   ├── firebase.json               Hosting config + security headers
│   ├── firestore.rules             Reglas de acceso por UID
│   └── public/
│       ├── app.js                  Lógica frontend + auth + PayPal SDK
│       ├── index.html              Landing / login
│       ├── compliance-hub.html     Hub de módulos de compliance
│       ├── compliance.html         Análisis KYC/AML
│       ├── forensic.html           Análisis forense
│       ├── contracts.html          Auditoría de contratos
│       ├── legal-chat.html         Chat de guía regulatoria
│       ├── markets.html            Hub de módulos de mercados
│       ├── market-strategy.html    Estrategia de portafolio
│       ├── market-asset.html       Análisis de activo individual
│       ├── market-audit.html       Auditoría de cartera
│       └── logoqahc.png
└── local-infrastructure/
    ├── Dockerfile                  Build para Cloud Run
    ├── entrypoint.py               Health check HTTP + arranca main_processor
    ├── cloudbuild.yaml             CI/CD con Cloud Build
    ├── main_processor.py           Polling loop + despacho de agentes
    ├── paypal_service.py           Monitor de suscripciones PayPal Live
    ├── requirements.txt
    ├── .env                        ← NO subir al repo
    ├── serviceAccountKey.json      ← NO subir al repo
    ├── agents/
    │   ├── __init__.py
    │   ├── agent_compliance.py     KYC/AML + análisis forense
    │   ├── agent_contracts.py      Auditoría de contratos
    │   ├── agent_legal_chat.py     Chat de guía regulatoria
    │   ├── agent_markets.py        Mercados, activos y carteras
    │   └── fuentes_oficiales_por_pais.py  Fuentes regulatorias por país
    └── database/
        ├── __init__.py
        ├── local_cache.py          SQLite — caché de reportes KYC
        └── compliance_cache.db     ← generado automáticamente, no subir al repo
```
