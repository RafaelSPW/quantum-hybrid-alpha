# AHC Intelligence — Quantum Compliance SaaS

Plataforma SaaS de inteligencia financiera para asesores de riesgo y compliance.  
Arquitectura híbrida: frontend en Firebase Hosting + procesamiento IA local (PC 24/7).

**Live:** https://agenteahc.web.app

---

## Arquitectura

```
NUBE (Firebase Hosting + Firestore + Storage)
──────────────────────────────────────────────────────────────
index.html              Panel principal + módulos
compliance-hub.html     Hub Módulo 01
markets.html            Hub Módulo 02
compliance.html         Due Diligence KYC / AML
forensic.html           Análisis Forense de Documentos
contracts.html          Auditoría de Contratos
legal-chat.html         Guía Regulatoria (chat)
market-strategy.html    Diseñador de Estrategias AI (chat)
market-asset.html       Analizador Clínico de Activos
market-audit.html       Auditor de Carteras
app.js                  Lógica frontend + autenticación + PayPal SDK

LOCAL (PC 24/7)
──────────────────────────────────────────────────────────────
main_processor.py       Polling loop (cada 10 s) + thread PayPal
paypal_service.py       Monitor de suscripciones PayPal Live
agents/
├── agent_compliance.py     Gemini 2.5 Flash + Google Search (KYC/Forense)
├── agent_contracts.py      Gemini 2.5 Flash (auditoría de contratos)
├── agent_legal_chat.py     Gemini 2.5 Flash (guía regulatoria)
└── agent_markets.py        Gemini 2.5 Flash + Google Search (mercados)
database/
└── local_cache.py          SQLite — caché de reportes KYC

FIRESTORE (colecciones)
──────────────────────────────────────────────────────────────
tareas_pendientes       Tareas creadas por el frontend, procesadas por main_processor
usuarios                Créditos, plan, suscripción PayPal del usuario
suscripciones_pendientes Activación PayPal pendiente de validación
suscripciones           Historial de suscripciones activas
leads_institucionales   Solicitudes del tier Enterprise Dedicado
```

---

## Módulos y Créditos

| Módulo | Herramienta | Créditos | Descripción |
|--------|-------------|----------|-------------|
| Compliance KYC/AML | `agent_compliance.py` | 50 | Rastreo transfronterizo OFAC, PEPs, redes corporativas |
| Análisis Forense | `agent_compliance.py` | 25 | Autenticación multimodal 4 capas (metadatos, ELA, IA, tipografía) |
| Auditoría de Contratos | `agent_contracts.py` | 75 | Cláusulas leoninas, vacíos legales, riesgo comercial |
| Guía Regulatoria (chat) | `agent_legal_chat.py` | 30 | Consulta normativa con documentos adjuntos |
| Estrategias AI (chat) | `agent_markets.py` | 75 | Portafolios conversacionales a medida |
| Análisis de Activos | `agent_markets.py` | 30 | Análisis técnico/fundamental de un activo |
| Auditoría de Carteras | `agent_markets.py` | 75 | Diagnóstico + rebalanceo de portafolio |

### Planes

| Plan | Créditos/mes | Precio |
|------|-------------|--------|
| Trial | 150 (7 días) | Gratis |
| Starter | 1.500 | USD 10/mes |
| Professional | 5.000 | USD 50/mes |
| Enterprise | 25.000 | USD 250/mes |
| Institutional Custom | Ilimitado | Trato privado · SWIFT |

---

## Setup Local

### 1. Instalar dependencias

```bash
cd local-infrastructure
pip install -r requirements.txt
```

### 2. Configurar credenciales

Crear `local-infrastructure/.env`:

```env
# Gemini (Google AI Studio → aistudio.google.com/app/apikey)
GEMINI_API_KEY=AIzaSy...

# Firebase Admin SDK
FIREBASE_ADMIN_CREDENTIALS=./serviceAccountKey.json
FIREBASE_PROJECT_ID=tu-proyecto
FIREBASE_STORAGE_BUCKET=tu-proyecto.firebasestorage.app

# PayPal Live (developer.paypal.com → Apps & Credentials)
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

Descargar `serviceAccountKey.json` desde:  
Firebase Console → Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada

### 3. Iniciar el procesador

```bash
cd local-infrastructure
python main_processor.py
```

El procesador corre 24/7:
- Cada 10 s consulta `tareas_pendientes` con `status: PENDIENTE`
- Despacha cada tarea al agente correspondiente
- Hilo paralelo valida suscripciones PayPal cada 30 s

---

## Setup Firebase (Nube)

### 1. Instalar Firebase CLI

```bash
npm install -g firebase-tools
firebase login
```

### 2. Configurar PayPal Plan IDs

En `cloud-infrastructure/public/app.js`, reemplazar los placeholders con los IDs reales de planes de suscripción PayPal  
(PayPal Dashboard → Billing → Subscriptions → Plans → Crear plan para cada nivel):

```js
const PAYPAL_PLAN_IDS = {
  starter:      "P-XXXXXXXXXXXXXXXX",
  professional: "P-XXXXXXXXXXXXXXXX",
  enterprise:   "P-XXXXXXXXXXXXXXXX",
};
```

### 3. Desplegar

```bash
cd cloud-infrastructure
firebase deploy
```

O solo hosting / solo reglas:

```bash
firebase deploy --only hosting
firebase deploy --only hosting,firestore:rules
```

---

## Flujo de una tarea

```
Browser                   Firestore                  Local (main_processor.py)
───────                   ─────────                  ─────────────────────────
1. Asesor envía formulario
2. app.js escribe tarea ──► tareas_pendientes
                              status: PENDIENTE
                                                  3. Polling detecta tarea
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
desde SQLite local sin llamar a Gemini (costo $0). Los resultados marcados como  
`SIMULADO` se descartan automáticamente y se re-analizan.

---

## Seguridad

- `.env` y `serviceAccountKey.json` están en `.gitignore` — **nunca subir al repo**
- Reglas Firestore: cada usuario solo accede a sus propios documentos
- `leads_institucionales`: solo `create` para usuarios autenticados, sin lectura pública
- Créditos: decrementos atómicos con `FieldValue.increment()` vía Admin SDK

---

## Estructura del Repositorio

```
quantum-compliance-saas/
├── cloud-infrastructure/
│   ├── firebase.json
│   ├── firestore.rules
│   └── public/
│       ├── app.js
│       ├── index.html
│       ├── compliance-hub.html
│       ├── compliance.html
│       ├── forensic.html
│       ├── contracts.html
│       ├── legal-chat.html
│       ├── markets.html
│       ├── market-strategy.html
│       ├── market-asset.html
│       ├── market-audit.html
│       └── logoqahc.png
└── local-infrastructure/
    ├── main_processor.py
    ├── paypal_service.py
    ├── requirements.txt
    ├── .env                    ← NO subir al repo
    ├── serviceAccountKey.json  ← NO subir al repo
    ├── agents/
    │   ├── agent_compliance.py
    │   ├── agent_contracts.py
    │   ├── agent_legal_chat.py
    │   └── agent_markets.py
    └── database/
        └── local_cache.py
```
