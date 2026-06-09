/**
 * Tests de Firestore Security Rules para la colección 'legajos'.
 *
 * Ejecuta contra el Firebase Local Emulator Suite.
 *
 * Prerequisitos:
 *   1. Firebase CLI instalado: npm install -g firebase-tools
 *   2. Emulator corriendo:
 *        firebase emulators:start --only firestore --project ahc-compliance-test
 *   3. Instalar dependencias: npm install (en este directorio)
 *   4. Correr tests: npm test
 *
 * Estos tests verifican las rules REALES de firestore.rules —
 * no simulan la lógica en Python. Un usuario B no puede leer el legajo
 * de usuario A aunque use el SDK directamente.
 */

const {
  initializeTestEnvironment,
  assertFails,
  assertSucceeds,
} = require("@firebase/rules-unit-testing");
const { readFileSync } = require("fs");
const path = require("path");

const PROJECT_ID = "ahc-compliance-test";
const RULES_PATH = path.resolve(__dirname, "../../firestore.rules");

let testEnv;

// ─── Setup / Teardown ─────────────────────────────────────────────────────────

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: {
      rules: readFileSync(RULES_PATH, "utf8"),
      host: "localhost",
      port: 8080,
    },
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

const UID_A = "user-alpha-001";
const UID_B = "user-beta-002";

async function crearLegajoAdmin(legajoId, ownerUid, extras = {}) {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await ctx
      .firestore()
      .collection("legajos")
      .doc(legajoId)
      .set({
        owner_uid:                    ownerUid,
        id_cliente:                   "CLIENTE-001",
        id_evaluacion:                "eval-uuid-0001",
        timestamp_evaluacion:         new Date().toISOString(),
        vigencia_hasta:               new Date(Date.now() + 180 * 86400000).toISOString(),
        estado:                       "SIN_ALERTAS_AUTOMATICAS",
        decision_oficial_cumplimiento: null,
        requiere_revision_humana:     true,
        nota_legal:                   "Nota legal de prueba.",
        ...extras,
      });
  });
}

// ─── Colección legajos ────────────────────────────────────────────────────────

describe("legajos — aislamiento entre usuarios (IDOR)", () => {
  beforeEach(async () => {
    await crearLegajoAdmin("legajo-de-userA", UID_A);
    await crearLegajoAdmin("legajo-de-userB", UID_B);
  });

  test("usuario A puede leer su propio legajo", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertSucceeds(
      userA.firestore().collection("legajos").doc("legajo-de-userA").get()
    );
  });

  test("usuario B NO puede leer el legajo de usuario A (IDOR → deny)", async () => {
    const userB = testEnv.authenticatedContext(UID_B);
    await assertFails(
      userB.firestore().collection("legajos").doc("legajo-de-userA").get()
    );
  });

  test("usuario A NO puede leer el legajo de usuario B", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertFails(
      userA.firestore().collection("legajos").doc("legajo-de-userB").get()
    );
  });

  test("usuario no autenticado no puede leer ningún legajo", async () => {
    const anon = testEnv.unauthenticatedContext();
    await assertFails(
      anon.firestore().collection("legajos").doc("legajo-de-userA").get()
    );
  });
});

describe("legajos — write bloqueado para el frontend (solo Admin SDK escribe)", () => {
  test("usuario autenticado NO puede crear un legajo directamente", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertFails(
      userA.firestore().collection("legajos").doc("legajo-nuevo").set({
        owner_uid: UID_A,
        id_cliente: "CLIENTE-HACK",
        estado: "SIN_ALERTAS_AUTOMATICAS",
      })
    );
  });

  test("usuario autenticado NO puede actualizar un legajo", async () => {
    await crearLegajoAdmin("legajo-de-userA", UID_A);
    const userA = testEnv.authenticatedContext(UID_A);
    await assertFails(
      userA.firestore().collection("legajos").doc("legajo-de-userA").update({
        estado: "SIN_ALERTAS_AUTOMATICAS",
      })
    );
  });

  test("usuario autenticado NO puede eliminar un legajo", async () => {
    await crearLegajoAdmin("legajo-de-userA", UID_A);
    const userA = testEnv.authenticatedContext(UID_A);
    await assertFails(
      userA.firestore().collection("legajos").doc("legajo-de-userA").delete()
    );
  });
});

describe("legajos — query de historial por owner_uid", () => {
  beforeEach(async () => {
    // Crear 3 legajos de userA y 2 de userB
    for (let i = 1; i <= 3; i++) {
      await crearLegajoAdmin(`legajo-a-${i}`, UID_A, {
        id_cliente: "CLIENTE-A",
        timestamp_evaluacion: new Date(Date.now() - i * 86400000).toISOString(),
      });
    }
    for (let i = 1; i <= 2; i++) {
      await crearLegajoAdmin(`legajo-b-${i}`, UID_B, { id_cliente: "CLIENTE-B" });
    }
  });

  test("usuario A puede listar sus legajos filtrando por owner_uid", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertSucceeds(
      userA
        .firestore()
        .collection("legajos")
        .where("owner_uid", "==", UID_A)
        .get()
    );
  });

  test("usuario A NO puede listar legajos de usuario B usando query", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    // La query filtra por owner_uid=UID_B pero el cliente ES userA → deny
    // (Firestore solo permite la query si el filtro coincide con request.auth.uid)
    await assertFails(
      userA
        .firestore()
        .collection("legajos")
        .where("owner_uid", "==", UID_B)
        .get()
    );
  });
});

describe("tareas_pendientes — regla create obliga uid == request.auth.uid", () => {
  test("usuario puede crear tarea con su propio uid", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertSucceeds(
      userA.firestore().collection("tareas_pendientes").add({
        uid:   UID_A,
        tipo:  "senaclaft_riesgo",
        nombre_cliente: "Test",
        status: "PENDIENTE",
      })
    );
  });

  test("usuario NO puede crear tarea con uid ajeno", async () => {
    const userA = testEnv.authenticatedContext(UID_A);
    await assertFails(
      userA.firestore().collection("tareas_pendientes").add({
        uid:   UID_B,   // UID de otro usuario — debe ser rechazado
        tipo:  "senaclaft_riesgo",
        status: "PENDIENTE",
      })
    );
  });
});
