# AHC Intelligence — Quantum Compliance SaaS

Plataforma SaaS de inteligencia financiera para asesores de riesgo y compliance.  
Arquitectura cloud-native: frontend en Firebase Hosting + procesamiento IA en Google Cloud Run.

**Frontend:** https://agenteahc.web.app  
**Backend:** https://quantum-processor-912859929290.us-central1.run.app (Cloud Run, privado — acceso solo via Firestore)

---

## Arquitectura

```
FIREBASE (agenteahc)
──────────────────────────────────────────────────────────────
Hosting        app.js + 16 HTML — SPA del asesor
Firestore      Base de datos en tiempo real (tareas, usuarios, pagos)
Storage        Archivos subidos por el usuario (PDF, JPG, PNG)
Auth           Google Sign-In (primario) + Email/Password (secundario) con verificación de email

GOOGLE CLOUD RUN (quantumaits · us-central1)
──────────────────────────────────────────────────────────────
quantum-processor   min-instances=1 · siempre activo · 1 GB RAM
  entrypoint.py         Health check HTTP (PORT) + lanza main_processor
  main_processor.py     Polling loop (10 s) + thread PayPal (15 s)
  paypal_service.py     Monitor de suscripciones PayPal Live
  agents/
  ├── agent_compliance.py          Gemini 2.5 Flash + Google Search (KYC / Forense)
  ├── agent_contracts.py           Gemini 2.5 Flash (auditoría de contratos)
  ├── agent_legal_chat.py          Gemini 2.5 Flash (guía regulatoria)
  ├── agent_markets.py             Gemini 2.5 Pro + Google Search (mercados)
  └── fuentes_oficiales_por_pais.py  Mapeo de fuentes regulatorias por país
  database/
  └── local_cache.py               SQLite — caché de reportes KYC
  sanctions/                       Motor KYC/AML SENACLAFT (Módulos 1–8)
  ├── ofac_loader.py               Descarga listas OFAC SDN + Consolidada (12h cache)
  ├── matcher.py                   Fuzzy matching con rapidfuzz (token_set_ratio NFKD)
  ├── pep_screener.py              Screening PEP + medios adversos (DuckDuckGo + Wikipedia)
  ├── risk_matrix.py               Matriz de riesgo 7 factores (Ley 19.574)
  ├── suspicious_activity.py       Detección señales: smurfing, crypto DDI, rechazo info
  ├── funds_analyzer.py            Análisis origen de fondos dos fases + consistencia perfil
  ├── legajo_exporter.py           Exportación PDF con hash SHA-256 + audit trail
  ├── audit_log.py                 Log append-only con cadena Merkle (JSONL)
  ├── validacion_cruzada.py        Legajo Unificado: cruce screening+riesgo+fondos
  ├── crypto.py                    Envelope encryption AES-256-GCM + KMS (Ley 18.331)
  └── vigencia_config.json         Vigencia por riesgo + retención configurable

FIRESTORE (colecciones)
──────────────────────────────────────────────────────────────
tareas_pendientes        Tareas creadas por frontend → procesadas por Cloud Run
usuarios                 Créditos, plan, suscripción PayPal del usuario
legajos                  Legajos de Cumplimiento unificados (append-only, owner_uid)
pagos_pendientes         Pagos PayPal pendientes de verificación
pagos                    Historial de pagos acreditados
leads_institucionales    Solicitudes tier Enterprise Dedicado
articulos                Blog/artículos generados con IA
```

---

## Flujo de una tarea

```
Browser                   Firestore                  Cloud Run (quantum-processor)
───────                   ─────────                  ─────────────────────────────
1. Asesor completa formulario
2. app.js sube archivo ─────────────────────────────► Firebase Storage
3. app.js escribe tarea ──► tareas_pendientes
                              status: PENDIENTE
                                                  4. Polling detecta tarea (10 s)
                                                  5. doc → status: EN_PROCESO
                                                  6. Descarga archivo de Storage
                                                  7. Llama agente IA (Gemini)
                          tareas_pendientes ◄──── 8. status: COMPLETADO
                              resultado: {...}        descuenta créditos
                              status: ERROR          borra archivo temporal
9. onSnapshot recibe
   el resultado en RT
```

**El frontend NO llama al Cloud Run URL directamente.** Todo pasa por Firestore. El backend lee de `tareas_pendientes`, procesa, y escribe el resultado de vuelta. El frontend lo recibe en tiempo real con `onSnapshot()`.

### Caché KYC
Si el documento ya fue investigado, `agent_compliance.py` devuelve el resultado desde SQLite sin llamar a Gemini (costo $0). Los resultados `SIMULADO` se descartan y se re-analizan.

---

## Módulos, Inputs y Outputs

### Módulo 01-A — Compliance KYC/AML (Persona Natural)
**Créditos:** 50 | **Archivo:** Opcional (PDF, JPG, PNG — cedula o pasaporte)

**Inputs (formulario):**
| Campo | Descripción |
|-------|-------------|
| `nombre` | Nombre completo del investigado |
| `documento` | CI/Pasaporte/RUT (mejora la precisión) |
| `nacionalidad` | País de origen |
| `paises_clave` | Lista de países con intereses comerciales declarados |

**Output JSON:**
```json
{
  "status_evaluacion": "APROBADO | ALERTA_RIESGO | BLOQUEADO",
  "resumen_ejecutivo": "Solo hechos de fuentes abiertas — sin recomendaciones",
  "empresas_vinculadas": [
    {
      "nombre_empresa": "Inversiones del Sur S.A.",
      "pais": "Uruguay",
      "socios_detectados": ["Carlos Méndez — Director", "María López — Socia 30%"]
    }
  ],
  "alertas_ofac_crimen": [
    "Mención encontrada en [URL]: descripción concreta",
    "Sin menciones en fuentes abiertas vinculadas a lista OFAC SDN"
  ],
  "paises_rastreados_efectivos": ["Uruguay", "Argentina", "Suecia"],
  "fuentes": [{"url": "https://...", "titulo": "Fuente del hallazgo"}],
  "tipo_entidad": "persona",
  "analisis_forense_documental": { ... },
  "alcance_metodologico": "Análisis de medios adversos y fuentes abiertas mediante IA. No sustituye consulta a listas oficiales..."
}
```

> **`status_evaluacion`:** `APROBADO` = sin hallazgos relevantes | `ALERTA_RIESGO` = hallazgos que requieren revisión | `BLOQUEADO` = menciones de alta gravedad en fuentes abiertas.

---

### Módulo 01-B — Compliance KYB (Empresa / Persona Jurídica)
**Créditos:** 50 | **Archivo:** Opcional

**Inputs adicionales vs. KYC:**
| Campo | Descripción |
|-------|-------------|
| `tipo_entidad` | `"empresa"` |
| `documento` | RUT / NIF / Número de registro |
| `titular` | Nombre del representante legal (opcional) |

**Output JSON:** Misma estructura que KYC persona, con `empresas_vinculadas` enfocado en UBO (Ultimate Beneficial Owners), directores y participaciones > 25%.

---

### Módulo 01-C — Compliance KYP (Inmueble)
**Créditos:** 50 | **Archivo:** Opcional

**Inputs adicionales vs. KYC:**
| Campo | Descripción |
|-------|-------------|
| `tipo_entidad` | `"inmueble"` |
| `nombre` | Descripción del inmueble (ej: "Apartamento 3B Torre Arenas, Punta del Este") |
| `documento` | Matrícula o dirección catastral |
| `titular` | Nombre del titular declarado |

**Output JSON:** Misma estructura, con `empresas_vinculadas` incluyendo gravámenes, hipotecas y titulares detectados.

---

### Módulo 02 — Análisis Forense de Documentos
**Créditos:** 25 | **Archivo:** Requerido (PDF, JPG, PNG)

**Análisis en 4 capas:**
1. **Capa 1 (local):** Metadatos EXIF/PDF — software creador, fechas de creación vs. modificación
2. **Capa 2 (Gemini):** Tipografía y kerning — fuentes inconsistentes en campos críticos
3. **Capa 3 (Gemini):** Artefactos de compresión — halos, parches, líneas de seguridad alteradas
4. **Capa 4 (Gemini):** Detección de IA generativa — firmas sin presión de trazo, micro-textos incoherentes

**Output JSON:**
```json
{
  "documento_autentico": true,
  "score_confianza_antifraude": 94.5,
  "anomalias_detectadas": [
    "Sin anomalías detectadas"
  ],
  "metadata_local": {
    "creador_detectado": "Microsoft Word 2019",
    "fecha_creacion": "D:20240315",
    "fecha_modificacion": "D:20240316",
    "señales_sospechosas": [
      "Fecha de modificación (20240316) difiere de la de creación (20240315)"
    ]
  }
}
```

> **`score_confianza_antifraude`:** 0–100. Por encima de 85 se considera documento sin anomalías evidentes. Por debajo de 60, múltiples señales detectadas.

---

### Módulo 03 — Auditoría de Contratos (Individual)
**Créditos:** 75 | **Archivo:** Requerido (PDF o imagen del contrato)

**Inputs (formulario):**
| Campo | Descripción |
|-------|-------------|
| `rol_cliente` | Rol de tu cliente en el contrato (ej: "Arrendatario", "Prestador de Servicios") |
| `notas_adicionales` | Contexto extra para el análisis (opcional) |

**Output JSON:**
```json
{
  "tipo_contrato": "Contrato de Prestación de Servicios Profesionales",
  "partes_detectadas": [
    {"nombre": "Grupo Meridional S.A.", "rol": "Contratante"},
    {"nombre": "Consultor Independiente", "rol": "Prestador"}
  ],
  "resumen_ejecutivo": "Se identificaron 2 cláusulas de riesgo ALTO y un vacío crítico en resolución de disputas...",
  "clausulas_problematicas": [
    {
      "clausula": "Cláusula 8.2 — Penalidad por Rescisión",
      "texto_detectado": "En caso de rescisión anticipada, el Prestador abonará el 30% del monto restante.",
      "riesgo": "Penalidad desproporcionada sin considerar incumplimiento previo del Contratante.",
      "severidad": "ALTA"
    }
  ],
  "vacios_legales": [
    "Sin mecanismo de resolución de disputas definido (mediación, arbitraje o sede judicial).",
    "Ausencia de cláusula de confidencialidad."
  ],
  "riesgos_comerciales": [
    "Plazo de pago 60 días sin tasa de interés por mora definida."
  ],
  "clausulas_favorables": [
    "Entregables con criterios de aceptación objetivos (Cláusula 3.1)."
  ],
  "recomendacion_general": "REVISAR_ANTES"
}
```

> **`recomendacion_general`:** `FIRMAR` | `REVISAR_ANTES` | `NO_FIRMAR`

---

### Módulo 03-B — Comparación de Contratos (Original vs. Modificado)
**Créditos:** 75 | **Archivos:** Requeridos (2 PDFs — original y modificado)

**Output JSON:**
```json
{
  "resumen_cambios": "Se detectaron 3 cláusulas modificadas, 2 agregadas, 1 eliminada. El cambio más relevante es el aumento de penalidad del 20% al 30%.",
  "recomendacion": "NEGOCIAR",
  "clausulas_modificadas": [
    {
      "clausula": "Cláusula 8.2 — Penalidad",
      "texto_original": "...abonará el 20%...",
      "texto_nuevo": "...abonará el 30%...",
      "descripcion": "La penalidad aumentó 50%. La base de cálculo también cambió de forma desfavorable.",
      "impacto": "DESFAVORABLE"
    }
  ],
  "clausulas_agregadas": [
    {
      "clausula": "Cláusula 15.1 — Arbitraje Obligatorio",
      "texto": "Toda controversia se resolverá mediante arbitraje ante la Cámara de Comercio...",
      "impacto": "NEUTRAL"
    }
  ],
  "clausulas_eliminadas": [
    {
      "clausula": "Cláusula 11.0 — Confidencialidad",
      "texto": "Ambas partes mantendrán la confidencialidad durante la vigencia y 2 años posteriores.",
      "impacto": "DESFAVORABLE"
    }
  ]
}
```

> **`recomendacion`:** `ACEPTAR` | `NEGOCIAR` | `RECHAZAR`

---

### Módulo 04 — Guía Regulatoria (Chat)
**Créditos:** 30 por mensaje | **Archivo:** Opcional (adjuntar la norma o contrato a consultar)

**Cómo usarlo:** Conversación en lenguaje natural. Si se adjunta un PDF, el agente lo analiza y responde citando artículos y secciones con su identificador exacto.

**Output:** Texto en markdown con análisis estructurado. El agente:
- Cita artículos exactos del documento adjunto
- Indica cuándo responde desde su base de conocimiento general (no del documento)
- Nunca garantiza asesoramiento legal formal — solo referencia normativa

**Ejemplo de preguntas:**
```
"¿Qué dice el Artículo 18 sobre las obligaciones de reporte?"
"¿Hay alguna excepción para personas físicas con operaciones < USD 10.000?"
"¿Qué pasa si el cliente no presenta la declaración jurada de origen de fondos?"
```

---

### Módulo 05-A — Diseñador de Estrategias de Portafolio (Chat)
**Créditos:** 75 por sesión | **Archivo:** No requerido

**Cómo usarlo:** Conversación guiada. El agente pide:
1. Capital disponible (USD)
2. Horizonte de inversión
3. Perfil de riesgo / objetivo de retorno

**Output:** Texto markdown con asignación de activos concreta:
```
**Composición propuesta:**
- 40% Oro (XAU/USD) — Refugio ante inflación
- 35% Bonos del Tesoro 2Y-5Y — Tasa real positiva
- 25% EURUSD — Estrategia de rango

**Retorno proyectado:** 7–9% anual | **Drawdown máximo estimado:** 8–12%
```
> Activos cubiertos: Oro (XAU/USD), Forex (pares principales y emergentes), Bonos soberanos y corporativos, Commodities.

---

### Módulo 05-B — Análisis Clínico de Activo
**Créditos:** 30 | **Archivo:** No requerido

**Input:** Texto libre describiendo el activo y la consulta.
```
"Analiza el panorama del EUR/USD para los próximos 15 días considerando la próxima reunión de la FED"
"¿Cómo está el oro técnicamente? ¿Hay oportunidad de compra?"
```

**Output JSON:**
```json
{
  "activo_consultado": "EUR/USD",
  "precio_referencia": "1.0842 — 9 Jun 2026",
  "contexto_tecnico": {
    "tendencia": "Lateral con sesgo bajista de corto plazo",
    "soporte_clave": "1.0780",
    "resistencia_clave": "1.0920",
    "volatilidad": "Moderada — ATR(14): 0.0062",
    "analisis": "El par se encuentra comprimido en rango 140 pips..."
  },
  "contexto_fundamental": {
    "tasas_interes": "BCE: 3.75% | FED: 5.25–5.50% — Diferencial favorable al USD",
    "eventos_macro": ["Datos de empleo USA (viernes) — impacto alto"],
    "analisis": "La diferencia de tasas sigue favoreciendo al dólar..."
  },
  "matriz_riesgo_retorno": {
    "escenario_base": "Rango 1.0780–1.0920 por 2 semanas más.",
    "escenario_alcista": "Ruptura 1.0920 → 1.1050 si datos USA decepcionan. Prob: 30%.",
    "escenario_bajista": "Ruptura 1.0780 → 1.0680 si nóminas superan expectativas. Prob: 35%.",
    "ratio_riesgo_retorno": "1.5:1 en estrategia de rango"
  },
  "veredicto": "ESPERAR",
  "conclusion": "Posición de espera hasta conocer datos de empleo del viernes...",
  "advertencias": [
    "Alta sensibilidad a publicaciones macro USA esta semana",
    "No operar sin stop definido"
  ]
}
```

> **`veredicto`:** `COMPRAR` | `ESPERAR` | `VENDER` | `NEUTRAL`

---

### Módulo 05-C — Auditoría de Cartera
**Créditos:** 75 | **Archivo:** No requerido

**Inputs (formulario):**
| Campo | Descripción |
|-------|-------------|
| `composicion` | Texto libre con la cartera actual (activos y porcentajes) |
| `plazo` | Horizonte de inversión (ej: "12 meses", "3 años") |
| `notas` | Contexto adicional (perfil del cliente, restricciones) |

**Output JSON:**
```json
{
  "resumen_ejecutivo": "La cartera presenta concentración excesiva en activos de alta volatilidad...",
  "score_salud_cartera": 64.5,
  "alertas_desviacion": [
    {
      "activo": "XAU/USD",
      "problema": "Sobreponderado",
      "descripcion": "30% en Oro es elevado para mediano plazo. Cotiza cerca de máximos históricos.",
      "severidad": "MEDIA"
    },
    {
      "activo": "EUR/USD",
      "problema": "Sin cobertura de volatilidad",
      "descripcion": "20% en Forex sin stop definido. Riesgo de drawdown significativo.",
      "severidad": "ALTA"
    }
  ],
  "propuesta_rebalanceo": [
    {
      "accion": "REDUCIR",
      "activo": "XAU/USD",
      "cambio": "−10% (de 30% a 20%)",
      "razon": "Reducir concentración cerca de máximos. Reasignar a bonos para anclar portafolio."
    },
    {
      "accion": "AUMENTAR",
      "activo": "Bonos Tesoro 2Y–5Y",
      "cambio": "+15% (de 50% a 65%)",
      "razon": "Anclar con tasa real positiva en contexto de soft landing."
    }
  ],
  "composicion_sugerida": [
    {"activo": "Bonos Tesoro 2Y–5Y", "porcentaje": "65%"},
    {"activo": "XAU/USD", "porcentaje": "15%"},
    {"activo": "EUR/USD", "porcentaje": "20%"}
  ],
  "conclusion_macro": "En el contexto actual (tasas altas, inflación moderándose), la cartera optimizada prioriza preservación de capital..."
}
```

> **`score_salud_cartera`:** 0–100. Por encima de 80: cartera sana. Entre 60–79: ajustes recomendados. Por debajo de 60: rebalanceo urgente.

---

## Módulo de Compliance SENACLAFT (local-infrastructure/sanctions/)

Motor KYC/AML para entidades reguladas por SENACLAFT (Ley 19.574 / Decreto 379/018 / Ley 20.469). Corre en el backend Cloud Run.

### Screening OFAC + PEP
```python
from sanctions import buscar_en_ofac, screening_pep_adverse, actualizar_listas, construir_reporte

db = actualizar_listas()  # descarga SDN + Consolidada, caché 12h
coincidencias = buscar_en_ofac("Juan Pérez", db, umbral=85)
resultado_pep = screening_pep_adverse("Juan Pérez")
reporte = construir_reporte("Juan Pérez", coincidencias, resultado_pep, db)
```

### Evaluación de Riesgo (Matriz 7 factores)
```python
from sanctions import MatrizRiesgo

m = MatrizRiesgo()
resultado = m.evaluar({
    "numero_cliente":           "001",
    "nombre_cliente":           "Juan Pérez",
    "actividad_economica":      "JUBILADOS",
    "calidad_pep":              "NO",
    "opera_cuenta_terceros":    "NO",
    "monto_significativo":      "NO",
    "pais_residencia":          "URUGUAY",
    "pais_actividad_comercial": "URUGUAY",
    "productos_servicios":      "NO",
})
# resultado["riesgo"] → "Bajo" | "Moderado" | "Alto"
# resultado["bloqueado"] → False (true si pais/actividad tiene puntaje 999)
# resultado["config_hash"] → SHA-256 del JSON de config (trazabilidad auditorial)
```

**Factores ponderados:**

| Factor | Peso |
|--------|------|
| Actividad económica | 24% |
| Calidad PEP | 24% |
| Opera cuenta terceros | 24% |
| Monto significativo | 13% |
| País de residencia | 5% |
| País de actividad comercial | 5% |
| Productos/Servicios | 5% |

**Umbrales:** Bajo ≤ 12.99 | Moderado 13–23.99 | Alto ≥ 24 | Bloqueo = 999 (IRAN, VENEZUELA, COREA DEL NORTE, SIRIA, etc.)

### Señales de Alerta Interna
```python
from sanctions import analizar_señales, Transaccion

alertas = analizar_señales(transacciones, datos_cliente)
# alertas["alertas"] → lista de AlertaInterna
# alertas["hay_alertas"] → bool
# alertas["nota_ros"] → "posible operación sospechosa — evaluar ROS" (solo si hay alertas)
# INVARIANTE: internal_only=True en TODAS las alertas — NUNCA visible al cliente
```

Detecta: smurfing (múltiples operaciones < umbral que suman ≥ USD 10.000 en 30 días), activos virtuales sin DDI (Ley 20.469), rechazo de información ≥ 2 campos críticos, documentos con anomalías.

### Exportación de Legajo PDF
```python
from sanctions import exportar_legajo, LegajoDatos

resultado = exportar_legajo(LegajoDatos(
    nombre_cliente="Juan Pérez",
    numero_cliente="001",
    formulario_kyc={...},
    screening_ofac=reporte,
    evaluacion_riesgo=resultado_matriz,
    alertas_internas=alertas,
    declaracion_fiscal_presente=True,
))
# resultado.pdf_bytes → bytes del PDF
# resultado.data_hash → SHA-256 del contenido (para verificación)
# resultado.audit_hash → hash del registro en el audit log
# resultado.legajo_id → "20260609_143022_A1B2C3D4"
```

El PDF incluye sección CONFIDENCIAL separada (alertas internas) que no puede ser compartida con el cliente.

---

## Registro de cambios

### 9 Junio 2026 — Legajos tab + correcciones UI SENACLAFT + deploy Cloud Run rev 00005

**Cloud Run:** revision `quantum-processor-00005-6mr` activa. Agrega soporte completo de `senaclaft_legajo` con cifrado KMS y check IDOR.

**Frontend `senaclaft.html`:**
- Tab "Legajos" con lista paginada (B1) y vista de detalle (B2) via Firestore `onSnapshot()`
- Datos sensibles cifrados: nunca se renderiza el ciphertext en pantalla; se muestra "Disponibles bajo solicitud autorizada"
- Badges de vigencia: verde / amber (< 30 días) / rojo (vencido — re-evaluar)
- Estado OFAC: botón deshabilitado + spinner "Descargando listas oficiales OFAC..." durante procesamiento
- Corregido: "tiempo real" → "fuentes oficiales (actualización periódica, caché 12h)" (era overclaim)
- Corregido: URL fuente OFAC → `sanctionslistservice.ofac.treas.gov` (Tesoro de los Estados Unidos)
- Fix listener restart: logout limpia UI; login reactiva el listener si el tab está activo

**Firestore:**
- Índice compuesto `legajos` desplegado: `owner_uid ASC + creado_en DESC` (requerido por la query del tab)
- `requirements.txt`: agregado `cryptography>=42.0.0` y `google-cloud-kms>=3.0.0`

**Verificado en producción:**
- KMS envelope encryption funcionando end-to-end (`datos_sensibles_cifrados` con `algoritmo`, `ciphertext_b64`, `encrypted_dek_b64`, `nonce_b64`, `kek_version`)
- IDOR bloqueado: tarea con IDs de otro usuario retorna "Acceso denegado: IDOR rechazado"

---

### Junio 2026 — Deploy completo + módulo sanctions SENACLAFT

**Deploy completado:**
- Frontend: Firebase Hosting https://agenteahc.web.app
- Backend: Cloud Run `quantum-processor` revision `00002` activa
- Env vars configurados en Cloud Run: `FIREBASE_CREDENTIALS_B64`, `GEMINI_API_KEY`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `FIREBASE_STORAGE_BUCKET`

**Módulo sanctions agregado** (`local-infrastructure/sanctions/`):
- 9 archivos: ofac_loader, matcher, pep_screener, report_builder, risk_matrix, suspicious_activity, funds_analyzer, legajo_exporter, audit_log
- `matriz_riesgo_config.json`: 101 actividades económicas, 264 países, ponderaciones SENACLAFT
- Audit log append-only con cadena de hashes Merkle (`cache/audit.jsonl`)
- Config history auto-archivada en `cache/risk_config_history/`

### Junio 2026 — Auth dual + copy de registro

**Archivos modificados:** `public/app.js`, `public/index.html`

#### (a) Copy / gancho de registro
- Botón del header en `index.html` cambiado de "Iniciar sesión" → **"Registrate gratis"**
- Bloque CTA visible en el hero de `index.html` (solo usuarios no logueados): botón grande + texto "Empezá con créditos gratis incluidos · Sin tarjeta · Sin compromisos."
- Toast verde post-aceptación de T&C: *"¡Listo! Ya tenés tus créditos gratis para empezar. Subí tu primer documento."*

#### (b) Auth dual: Google + Email/Contraseña
- `loginGoogle()` ahora abre `abrirModalAuth()` → todos los botones existentes en los 16 HTML heredan el modal sin cambios en el HTML de módulos
- Modal unificado con:
  - **"Continuar con Google"** (primario)
  - Separador "o"
  - Formulario email/contraseña con toggle **Registrarse / Iniciar sesión**
  - Link **"¿Olvidaste tu contraseña?"** → `sendPasswordResetEmail()`
  - Mensajes de error en español para todos los códigos de Firebase Auth

#### (c) Verificación de email (solo usuarios email/contraseña)
- Post-registro: `sendEmailVerification()` automático antes de cerrar el modal
- `onAuthStateChanged` detecta `providerId === "password" && !emailVerified` → overlay bloqueante
- Overlay con: "Ya verifiqué", "Reenviar correo" (cooldown 30s), "Cerrar sesión"
- **Usuarios Google no se ven afectados** — `emailVerified` siempre es `true` para Google Sign-In

---

## Planes y Créditos

| Plan | Créditos/mes | PayPal Plan ID |
|------|-------------|----------------|
| Trial | 150 (7 días) | — Gratis — |
| Starter | 1.500 | `P-8GL53584124263225NIRKO6Q` |
| Professional | 5.000 | `P-0GF18564ED3901707NIRKYBQ` |
| Enterprise | 25.000 | `P-9L677248CE864754UNIRKY2I` |
| Institutional Custom | Ilimitado | Trato privado · SWIFT |

| Módulo | Créditos |
|--------|----------|
| Compliance KYC/AML (persona, empresa o inmueble) | 50 |
| Análisis Forense | 25 |
| Auditoría de Contratos | 75 |
| Guía Regulatoria (por mensaje) | 30 |
| Diseñador de Estrategias (por sesión) | 75 |
| Análisis de Activo | 30 |
| Auditoría de Cartera | 75 |
| SENACLAFT — Evaluación de Riesgo | 20 |
| SENACLAFT — Screening OFAC/PEP | 40 |
| SENACLAFT — Análisis de Fondos | 30 |
| SENACLAFT — Legajo Unificado | 10 |

> **Trial (150 cr):** alcanza para 2 ciclos completos riesgo + OFAC (20 + 40 = 60 cr c/u) con créditos de sobra para análisis de fondos y legajo.

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
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
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
  --project quantumaits
```

**Configurar variables de entorno (PowerShell):**
```powershell
# Generar el base64 del serviceAccountKey.json
$b64 = [System.Convert]::ToBase64String([System.IO.File]::ReadAllBytes(".\serviceAccountKey.json"))

# Escribir YAML temporal y aplicar
$tmpFile = "$env:TEMP\cr_env.yaml"
@"
FIREBASE_CREDENTIALS_B64: "$b64"
GEMINI_API_KEY: "tu-api-key"
PAYPAL_CLIENT_ID: "tu-client-id"
PAYPAL_CLIENT_SECRET: "tu-client-secret"
FIREBASE_PROJECT_ID: "agenteahc"
FIREBASE_STORAGE_BUCKET: "agenteahc.firebasestorage.app"
"@ | Out-File $tmpFile -Encoding utf8

gcloud run services update quantum-processor --region=us-central1 --project=quantumaits --env-vars-file=$tmpFile
Remove-Item $tmpFile -Force
```

**Ver logs en tiempo real:**
```bash
gcloud run services logs tail quantum-processor --region=us-central1 --project quantumaits
```

### Variables de entorno requeridas en Cloud Run

| Variable | Descripción |
|----------|-------------|
| `FIREBASE_CREDENTIALS_B64` | `serviceAccountKey.json` codificado en base64 |
| `GEMINI_API_KEY` | Google AI Studio → aistudio.google.com/app/apikey |
| `PAYPAL_CLIENT_ID` | PayPal Developer → Apps & Credentials |
| `PAYPAL_CLIENT_SECRET` | PayPal Developer → Apps & Credentials |
| `FIREBASE_PROJECT_ID` | `agenteahc` |
| `FIREBASE_STORAGE_BUCKET` | `agenteahc.firebasestorage.app` |
| `KMS_KEY_NAME` | Nombre completo del recurso KMS para cifrado de datos sensibles |

---

## Módulo 01-E-2 — Legajo de Cumplimiento Unificado (`senaclaft_legajo`)

**Créditos:** 10 (agrega resultados de tareas ya pagadas)

Cruza los resultados del screening OFAC/PEP (`senaclaft_ofac`) y la evaluación de riesgo
(`senaclaft_riesgo`) en un único documento auditoriable. El análisis de fondos se incluye
opcionalmente, solo si el investigador confirmó los montos extraídos.

### Principio rector

> El sistema sugiere y documenta. La determinación final es exclusiva del oficial de cumplimiento humano.

Todos los outputs incluyen:
- `decision_oficial_cumplimiento: null` — siempre null, sin excepción
- `requiere_revision_humana: true` — siempre true, sin excepción
- `nota_legal` — texto legal transversal en cada evaluación

### Input (Firestore task)

```json
{
  "tipo": "senaclaft_legajo",
  "uid": "firebase_uid_del_usuario",
  "id_cliente": "CLIENTE-001",
  "screening_task_id": "<id de la tarea senaclaft_ofac completada>",
  "riesgo_task_id": "<id de la tarea senaclaft_riesgo completada>",
  "fondos_task_id": "<id de tarea de fondos confirmada — OPCIONAL>"
}
```

**Seguridad IDOR:** el backend verifica que `screening_task_id`, `riesgo_task_id` y
`fondos_task_id` pertenezcan todos al mismo `uid` de la tarea. Si alguno pertenece a
otro usuario, la tarea se rechaza y no se construye el legajo.

### Output (campo `resultado` en la tarea + documento en `legajos/`)

```json
{
  "legajo_id": "abc123...",
  "id_evaluacion": "uuid-v4",
  "estado": "SIN_ALERTAS_AUTOMATICAS | ALERTAS_PENDIENTES_REVISION",
  "vigencia_hasta": "2026-12-09T00:00:00+00:00"
}
```

El documento completo se escribe en `legajos/{legajoId}` con `owner_uid` para
aislamiento multi-tenant.

### Vigencia por nivel de riesgo (configurable en `vigencia_config.json`)

| Nivel | Vigencia default | Significado |
|-------|-----------------|-------------|
| Alto | 180 días | Re-screenear en 6 meses (debida diligencia intensificada, SENACLAFT) |
| Moderado | 365 días | Re-screenear en 12 meses |
| Bajo | 730 días | Re-screenear en 24 meses |

**La vigencia vencida significa "re-screenear", no "dar de baja al cliente".**

### Retención y purga

La retención de legajos se rige por `retencion_anos` (default: 5 años, SENACLAFT).
`purgar_legajos_expirados(db, dry_run=True)` elimina legajos cuyo `creado_en` supera
el período. La purga nunca usa `vigencia_hasta` como criterio de eliminación.

---

## Aislamiento Multi-tenant

Cada documento en Firestore lleva `owner_uid` asignado por el backend (Admin SDK)
a partir del `uid` de la tarea, que las Security Rules ya verificaron al momento
de creación.

### Firestore Security Rules — `legajos`

```javascript
match /legajos/{legajoId} {
  allow read:  if request.auth != null
               && request.auth.uid == resource.data.owner_uid;
  allow write: if false;  // solo Admin SDK escribe
}
```

El frontend puede consultar el historial de evaluaciones de un cliente:

```javascript
db.collection('legajos')
  .where('owner_uid', '==', currentUser.uid)
  .where('id_cliente', '==', clienteId)
  .orderBy('timestamp_evaluacion', 'desc')
  .limit(50)
```

Las Security Rules garantizan que la query solo retorna los legajos del usuario autenticado.

---

## Cifrado de datos sensibles (Ley 18.331)

Los montos confirmados del análisis de fondos se cifran con **AES-256-GCM**
usando envelope encryption: Google Cloud KMS gestiona la KEK; la DEK se genera
aleatoriamente por evaluación y se cifra con KMS.

El **AAD** (Additional Authenticated Data) está atado a `{id_evaluacion}|{owner_uid}`,
lo que impide mover un ciphertext a otro legajo o usuario (AESGCM lanza `InvalidTag`
si el AAD no coincide).

### Setup KMS (una vez por proyecto)

```bash
# Crear key ring y clave
gcloud kms keyrings create ahc-compliance \
  --location=us-central1 --project=quantumaits

gcloud kms keys create sensitive-data \
  --location=us-central1 \
  --keyring=ahc-compliance \
  --purpose=encryption \
  --project=quantumaits

# Dar acceso al service account del Cloud Run
gcloud kms keys add-iam-policy-binding sensitive-data \
  --location=us-central1 \
  --keyring=ahc-compliance \
  --member="serviceAccount:SERVICE_ACCOUNT@quantumaits.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" \
  --project=quantumaits
```

### CMEK para Cloud Storage

```bash
gcloud storage buckets update gs://agenteahc.firebasestorage.app \
  --default-encryption-key=projects/quantumaits/locations/us-central1/keyRings/ahc-compliance/cryptoKeys/sensitive-data
```

### Variable de entorno

```powershell
# Agregar al YAML de Cloud Run env vars:
KMS_KEY_NAME: "projects/quantumaits/locations/us-central1/keyRings/ahc-compliance/cryptoKeys/sensitive-data"
```

---

## Tests

### Python (pytest / unittest)

```bash
cd local-infrastructure
python -m pytest sanctions/tests/ -v
```

| Archivo | Casos |
|---------|-------|
| `test_validacion_cruzada.py` | Sin alertas, con alertas, fondos no confirmados, IDOR |
| `test_crypto.py` | Round-trip AES-GCM, AAD binding, KMSNotConfiguredError |
| `test_aislamiento_vigencia.py` | Vigencia por riesgo, purga por retención, owner_uid |

### Firestore Security Rules (Firebase Emulator)

```bash
# 1. Iniciar emulator (desde cloud-infrastructure/)
firebase emulators:start --only firestore --project ahc-compliance-test

# 2. En otra terminal
cd cloud-infrastructure/tests/rules
npm install
npm test
```

Prueba que usuario B no puede leer el legajo de usuario A contra las rules reales.

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
FIREBASE_PROJECT_ID=agenteahc
PAYPAL_CLIENT_ID=...
PAYPAL_CLIENT_SECRET=...
```

Descargar `serviceAccountKey.json` desde:  
Firebase Console → Configuración → Cuentas de servicio → Generar nueva clave privada

```bash
python main_processor.py
```

**Verificar módulo sanctions:**
```bash
cd local-infrastructure
python -c "from sanctions import MatrizRiesgo, version_activa; print('Matriz v' + version_activa())"
# → Matriz v1.0-importada-amigo
```

---

## Seguridad

- `.env` y `serviceAccountKey.json` en `.gitignore` — nunca subir al repo
- `.env` y `serviceAccountKey.json` en `.dockerignore` — nunca incluir en la imagen Docker
- `FIREBASE_CREDENTIALS_B64`: credenciales pasadas como base64 en env var, nunca en el filesystem del contenedor
- Reglas Firestore: cada usuario solo accede a sus propios documentos (validación por UID)
- `tareas_pendientes`: create requiere `uid == auth.uid`; read/update/delete requieren ser el propietario
- Headers HTTP: `X-Frame-Options: DENY`, `HSTS`, `X-Content-Type-Options`, `Referrer-Policy`
- Créditos: decrementos atómicos con `FieldValue.increment()` vía Admin SDK (no manipulables desde frontend)
- Validación de tipo de archivo en frontend: solo PDF, JPG, PNG
- **No tipping-off:** Las alertas internas de señales de sospecha tienen `internal_only=True` — nunca son visibles al cliente ni al investigado
- **No auto-reporte UIAF:** El sistema sugiere "evaluar ROS" al investigador humano. La determinación final siempre es del oficial de cumplimiento

---

## Estructura del Repositorio

```
quantum-compliance-saas/
├── cloud-infrastructure/
│   ├── firebase.json               Hosting config + security headers
│   ├── firestore.rules             Reglas de acceso por UID
│   ├── firestore.indexes.json
│   ├── storage.rules
│   └── public/
│       ├── app.js                  Lógica frontend + auth + PayPal SDK (2985 líneas)
│       ├── index.html              Landing / login
│       ├── compliance-hub.html     Hub de módulos de compliance
│       ├── compliance.html         Análisis KYC/AML
│       ├── senaclaft.html          Módulos SENACLAFT (riesgo + OFAC + legajos)
│       ├── forensic.html           Análisis forense
│       ├── contracts.html          Auditoría de contratos
│       ├── legal-chat.html         Chat de guía regulatoria
│       ├── markets.html            Hub de módulos de mercados
│       ├── market-strategy.html    Estrategia de portafolio (chat)
│       ├── market-asset.html       Análisis de activo individual
│       ├── market-audit.html       Auditoría de cartera
│       ├── articulos.html          Listado del blog / artículos
│       ├── articulo.html           Página de artículo individual
│       ├── contacto.html           Página de contacto
│       ├── terminos.html           Términos y condiciones
│       ├── adminahc.html           Panel de administración
│       └── logoqahc.png
└── local-infrastructure/
    ├── Dockerfile                  Build para Cloud Run (python:3.11-slim-bookworm)
    ├── .dockerignore               Excluye .env, serviceAccountKey.json, *.db
    ├── entrypoint.py               Health check HTTP + arranca main_processor
    ├── cloudbuild.yaml             CI/CD con Cloud Build
    ├── cloudbuild-buildonly.yaml   Build sin deploy (solo imagen)
    ├── deploy.ps1                  Script de deploy PowerShell
    ├── main_processor.py           Polling loop 10s + despacho de agentes (2430 líneas)
    ├── paypal_service.py           Monitor PayPal Live (thread daemon, poll 15s)
    ├── requirements.txt
    ├── .env                        ← NO subir al repo
    ├── serviceAccountKey.json      ← NO subir al repo
    ├── agents/
    │   ├── agent_compliance.py     KYC persona/empresa/inmueble + forense 4 capas
    │   ├── agent_contracts.py      Análisis individual y comparativo de contratos
    │   ├── agent_legal_chat.py     Chat regulatorio con soporte de documento adjunto
    │   ├── agent_markets.py        Estrategia (chat), análisis activo, auditoría cartera
    │   └── fuentes_oficiales_por_pais.py  Fuentes regulatorias por país (ROU, ARG, BRA...)
    ├── database/
    │   ├── local_cache.py          SQLite — caché de reportes KYC
    │   └── compliance_cache.db     ← generado automáticamente, no subir al repo
    └── sanctions/                  Motor KYC/AML SENACLAFT
        ├── __init__.py             Exports públicos del módulo
        ├── ofac_loader.py          Descarga OFAC SDN + Consolidada (ZIP/XML, caché 12h)
        ├── matcher.py              Fuzzy matching NFKD + permutaciones de nombre
        ├── pep_screener.py         Screening PEP + medios adversos (DuckDuckGo + Wikipedia)
        ├── report_builder.py       Construcción del reporte final de screening
        ├── risk_matrix.py          Motor de calificación 7 factores (Ley 19.574)
        ├── suspicious_activity.py  Señales de alerta interna (smurfing, crypto, etc.)
        ├── funds_analyzer.py       Análisis origen de fondos dos fases (PDF + Gemini)
        ├── legajo_exporter.py      PDF con SHA-256 + registro en audit log
        ├── audit_log.py            Log append-only con cadena Merkle (JSONL)
        ├── matriz_riesgo_config.json  Config externa de la matriz (versionada + hash)
        ├── risk_config.yaml        Config YAML alternativa (referencia)
        └── cache/
            ├── audit.jsonl         ← generado en runtime, no subir al repo
            ├── *.xml               ← listas OFAC cacheadas, no subir al repo
            └── risk_config_history/  Historial de versiones de la matriz

```
