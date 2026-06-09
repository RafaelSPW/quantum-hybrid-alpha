# Tests de Firestore Security Rules

Estos tests verifican las rules reales de `firestore.rules` contra el
Firebase Local Emulator Suite.

## Prerequisitos

```bash
# 1. Instalar Firebase CLI
npm install -g firebase-tools

# 2. Instalar dependencias del test
npm install

# 3. En una terminal separada, iniciar el emulator
#    (ejecutar desde cloud-infrastructure/)
firebase emulators:start --only firestore --project ahc-compliance-test
```

## Ejecutar tests

```bash
# Con el emulator corriendo:
npm test
```

## Qué se prueba

- `legajos` — usuario A no puede leer legajo de usuario B (IDOR)
- `legajos` — el frontend no puede escribir directamente (solo Admin SDK)
- `legajos` — query de historial solo retorna docs propios
- `tareas_pendientes` — la regla `create` obliga `uid == request.auth.uid`
