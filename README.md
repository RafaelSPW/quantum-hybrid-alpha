# Quantum Compliance SaaS

Arquitectura híbrida: Frontend en Firebase (nube) + procesamiento IA local (PC 24/7).

## Arquitectura

```
NUBE (Firebase)          LOCAL (PC 24/7)
─────────────────        ─────────────────────────────────
index.html               main_processor.py  ← polling loop
compliance.html    ──►   agents/
markets.html             ├── agent_compliance.py  (Gemini 2.5 Flash)
app.js                   └── agent_markets.py     (Gemini 2.5 Pro)
Firestore DB      ◄──    database/local_cache.py  (SQLite)
```

## Setup Local

### 1. Instalar dependencias
```bash
cd local-infrastructure
pip install -r requirements.txt
```

### 2. Configurar credenciales
Editar `.env`:
```
GEMINI_API_KEY=tu_key_de_ai_studio
FIREBASE_ADMIN_CREDENTIALS=./serviceAccountKey.json
FIREBASE_PROJECT_ID=tu-proyecto
```

Descargar `serviceAccountKey.json` desde Firebase Console → Configuración → Cuentas de servicio.

### 3. Iniciar el procesador
```bash
python main_processor.py
```

## Setup Firebase (Nube)

### 1. Instalar Firebase CLI
```bash
npm install -g firebase-tools
firebase login
```

### 2. Editar `public/app.js`
Reemplazar `firebaseConfig` con los datos de tu proyecto Firebase.

### 3. Desplegar
```bash
cd cloud-infrastructure
firebase deploy
```

## Flujo de una tarea

1. Asesor completa formulario en el browser → `app.js` escribe en Firestore con `status: PENDIENTE`
2. `main_processor.py` detecta la tarea cada 10 segundos
3. Consulta caché local (SQLite) — si existe, costo $0
4. Si es nuevo: llama a Gemini con Google Search grounding
5. Guarda resultado en SQLite + actualiza Firestore con `status: COMPLETADO`
6. Frontend recibe el resultado en tiempo real via `onSnapshot`

## Módulos

| Módulo | Modelo | Herramienta | Uso |
|--------|--------|-------------|-----|
| Compliance | Gemini 2.5 Flash | Google Search | KYC, OFAC, red transfronteriza |
| Mercados | Gemini 2.5 Pro | Google Search | Estrategias Oro/Forex/Bonos |
