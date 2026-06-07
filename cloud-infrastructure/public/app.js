const firebaseConfig = {
  apiKey: "AIzaSyCErA2F20Y7NJzdxX3phQZ6baXQvT8E27A",
  authDomain: "agenteahc.firebaseapp.com",
  projectId: "agenteahc",
  storageBucket: "agenteahc.firebasestorage.app",
  messagingSenderId: "574213027867",
  appId: "1:574213027867:web:e5845f4d8a9d86adcea0be",
  measurementId: "G-Z8WWEKJCRG",
};

firebase.initializeApp(firebaseConfig);
const db      = firebase.firestore();
const auth    = firebase.auth();
const storage = typeof firebase.storage === "function" ? firebase.storage() : null;

function escHtml(s) {
  if (s == null) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function safeUrl(url) {
  if (!url) return "#";
  var u = String(url).trim();
  return /^javascript:/i.test(u) ? "#" : u;
}

// Costo de créditos por tipo de tarea
const CREDIT_COSTS = { compliance: 50, markets: 30, contracts: 75, legal_chat: 30, forensic: 25, market_strategy: 75, market_asset: 30, market_audit: 75 };

// PayPal Live — Client ID público (frontend)
const PAYPAL_CLIENT_ID = "ASgYio7YMJjMUEPh8cBeG8wjVSHQrblcozu-wdWN_YRyZeNahEoALcX0IVBxLSx2WUqhj89vwDICR_GT";
// Packs de créditos — pagos únicos (sin suscripción mensual)
const PAYPAL_PACKS = [
  { id: "starter",      creditos: 1500,  precio: "10.00",  label: "Pack 1.500"  },
  { id: "professional", creditos: 5000,  precio: "50.00",  label: "Pack 5.000"  },
  { id: "enterprise",   creditos: 25000, precio: "250.00", label: "Pack 25.000" },
];

const TRIAL_CREDITOS   = 150;
const TRIAL_DIAS       = 7;
const ALLOWED_FILE_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/jpg"];
const TRIAL_MAX_MB     = 5;      // MB máx por archivo en plan trial
const TRIAL_MAX_BYTES  = TRIAL_MAX_MB * 1024 * 1024;

let _tareaActivaId        = null;
let _datosCliente         = {};
let _archivoSeleccionado  = null;
let _contratoSeleccionado = null;
let _contratoRecibido     = null;
let _modoContrato         = "individual";
let _creditos             = null;
let _userPlan             = "trial";
let _trialExpiraDate      = null;
let _unsubCreditos        = null;
let _unsubCompliance      = null;
let _tipoEntidad          = "persona";
let _feedbackDado         = false;
let _fbEstrellas          = 0;

// ── SPINNER GLOBAL (para páginas sin loading-panel propio) ────────────────────
(function() {
  var s = document.createElement("style");
  s.textContent =
    "@keyframes _ahc-spin{to{transform:rotate(360deg)}}" +
    ".ahc-spinner{display:inline-block;width:13px;height:13px;border:2px solid currentColor;" +
    "border-top-color:transparent;border-radius:50%;animation:_ahc-spin .7s linear infinite;" +
    "vertical-align:middle;margin-right:7px;flex-shrink:0}";
  document.head.appendChild(s);
})();

function _mostrarLoadingPanel(labelText, sublabelText) {
  var panel = document.getElementById("loading-panel");
  var idle  = document.getElementById("placeholder-msg");
  if (panel) {
    if (labelText)    document.getElementById("loading-label").textContent    = labelText;
    if (sublabelText) document.getElementById("loading-sublabel").textContent = sublabelText;
    panel.classList.add("visible");
  }
  if (idle) idle.style.display = "none";
}

function _ocultarLoadingPanel() {
  var panel = document.getElementById("loading-panel");
  if (panel) panel.classList.remove("visible");
}

// ── INTERNACIONALIZACIÓN (i18n) ───────────────────────────────────────────────

var _lang = (navigator.language || navigator.userLanguage || "es").toLowerCase().startsWith("en") ? "en" : "es";

var _i18n = {
  es: {
    "panel.titulo": "Due Diligence KYC / AML",
    "tipo.persona": "Persona", "tipo.empresa": "Empresa", "tipo.inmueble": "Inmueble",
    "opcional": "(opcional)", "opcional.coma": "(opcional, separar con coma)",
    "p.nombre.label": "Nombre Completo",        "p.nombre.ph": "Ej: Juan Ramón Pérez Sosa",
    "p.doc.label":    "Documento / Pasaporte",   "p.doc.ph":    "Ej: 1.234.567-8",
    "p.nac.label":    "Nacionalidad",            "p.nac.ph":    "Ej: Argentino",
    "p.paises.label": "Países con intereses",    "p.paises.ph": "Ej: Argentina, Uruguay, Suecia",
    "e.nombre.label": "Razón Social",            "e.nombre.ph": "Ej: Inversiones del Sur S.A.",
    "e.rut.label":    "RUT / NIF / Nº Registro", "e.rut.ph":    "Ej: 214.356.780-2",
    "e.pais.label":   "País de Constitución",    "e.pais.ph":   "Ej: Uruguay",
    "e.paises.label": "Países con intereses",    "e.paises.ph": "Ej: Argentina, Paraguay, España",
    "i.desc.label":   "Descripción del Inmueble","i.desc.ph":   "Ej: Apartamento 3 dorm., Pocitos, Montevideo",
    "i.dir.label":    "Dirección / Matrícula",   "i.dir.ph":    "Ej: Av. Brasil 2856, apto 5B",
    "i.titular.label":"Titular Declarado",       "i.titular.ph":"Ej: Juan García o Sociedad XYZ",
    "i.pais.label":   "País",                    "i.pais.ph":   "Ej: Uruguay",
    "submit.persona": "Iniciar Investigación con IA",
    "submit.empresa": "Iniciar Due Diligence Corporativo",
    "submit.inmueble":"Iniciar Análisis de Inmueble",
    "placeholder.msg":"El informe aparecerá aquí una vez procesada la investigación",
    "r.subtitulo":    "Informe de Debida Diligencia — KYC / AML",
    "r.doc.label":    "Documento", "r.generado": "Generado",
    "r.resumen":      "Resumen Ejecutivo",
    "r.entidades.persona": "Entidades Vinculadas",
    "r.entidades.empresa": "Directivos / Beneficiarios Finales",
    "r.entidades.inmueble":"Titulares y Gravámenes",
    "r.ofac":         "OFAC / Sanciones Internacionales",
    "r.fuentes":      "Fuentes Consultadas",
    "r.paises":       "Jurisdicciones Rastreadas",
    "r.forense":      "Análisis Forense Documental — 4 Capas",
    "r.forense.meta": "Metadatos del Archivo (Capa 1)",
    "r.forense.anomalias": "Anomalías Detectadas (Capas 2–4)",
    "r.conclusion":   "Conclusión del Asesor Responsable",
    "r.conclusion.ph":"Ingrese la conclusión, observaciones adicionales y recomendación final del asesor responsable...",
    "btn.guardar":    "Guardar Conclusión", "btn.pdf": "Exportar PDF / Imprimir",
    "status.creando": "Creando tarea...", "status.subiendo": "Subiendo documento forense...",
    "status.subido":  "Documento subido. Procesando investigación...",
    "status.procesando": "Investigación en proceso...",
    "status.sin_doc": "Investigación en proceso (sin documento adjunto)...",
    "status.completado": "Investigación completada.",
    "no.entidades":   "No se detectaron entidades vinculadas.",
    "no.alertas":     "Sin alertas registradas.",
    "no.fuentes":     "No se registraron fuentes externas.",
    "badge.aprobado": "APROBADO", "badge.alerta": "ALERTA DE RIESGO", "badge.bloqueado": "BLOQUEADO",
    "forense.autentico": "✓ Documento Auténtico",
    "forense.alterado":  "⚠ Posible Alteración Detectada",
    "forense.pendiente": "— Veredicto Pendiente",
    "valid.req": "Por favor complete el campo principal de la búsqueda.",
    "valid.login": "Debes iniciar sesión.",
    "doc.label.empresa": "RUT / Registro", "doc.label.inmueble": "Dirección / Matrícula",
    "loading.sublabel": "Consultando bases de datos y fuentes externas",
  },
  en: {
    "panel.titulo": "KYC / AML Due Diligence",
    "tipo.persona": "Person", "tipo.empresa": "Company", "tipo.inmueble": "Property",
    "opcional": "(optional)", "opcional.coma": "(optional, comma-separated)",
    "p.nombre.label": "Full Name",              "p.nombre.ph": "E.g.: John Robert Smith",
    "p.doc.label":    "ID / Passport",           "p.doc.ph":    "E.g.: 1.234.567-8",
    "p.nac.label":    "Nationality",             "p.nac.ph":    "E.g.: American",
    "p.paises.label": "Countries of interest",   "p.paises.ph": "E.g.: USA, UK, Spain",
    "e.nombre.label": "Company Name",            "e.nombre.ph": "E.g.: Southern Investments Inc.",
    "e.rut.label":    "Tax ID / Registration No.","e.rut.ph":   "E.g.: 214.356.780-2",
    "e.pais.label":   "Country of Incorporation","e.pais.ph":   "E.g.: Uruguay",
    "e.paises.label": "Countries of interest",   "e.paises.ph": "E.g.: Argentina, Paraguay, Spain",
    "i.desc.label":   "Property Description",    "i.desc.ph":   "E.g.: 3-bedroom apt., Pocitos, Montevideo",
    "i.dir.label":    "Address / Cadastral Ref.", "i.dir.ph":   "E.g.: 2856 Brasil Ave., apt 5B",
    "i.titular.label":"Declared Owner",          "i.titular.ph":"E.g.: John Smith or XYZ Corp.",
    "i.pais.label":   "Country",                 "i.pais.ph":   "E.g.: Uruguay",
    "submit.persona": "Start AI Investigation",
    "submit.empresa": "Start Corporate Due Diligence",
    "submit.inmueble":"Start Property Analysis",
    "placeholder.msg":"The report will appear here once the investigation is processed",
    "r.subtitulo":    "Due Diligence Report — KYC / AML",
    "r.doc.label":    "Document", "r.generado": "Generated",
    "r.resumen":      "Executive Summary",
    "r.entidades.persona": "Linked Entities",
    "r.entidades.empresa": "Directors / Ultimate Beneficial Owners",
    "r.entidades.inmueble":"Owners and Encumbrances",
    "r.ofac":         "OFAC / International Sanctions",
    "r.fuentes":      "Sources Consulted",
    "r.paises":       "Jurisdictions Traced",
    "r.forense":      "Document Forensic Analysis — 4 Layers",
    "r.forense.meta": "File Metadata (Layer 1)",
    "r.forense.anomalias": "Detected Anomalies (Layers 2–4)",
    "r.conclusion":   "Responsible Advisor's Conclusion",
    "r.conclusion.ph":"Enter conclusions, additional observations and final recommendation...",
    "btn.guardar":    "Save Conclusion", "btn.pdf": "Export PDF / Print",
    "status.creando": "Creating task...", "status.subiendo": "Uploading forensic document...",
    "status.subido":  "Document uploaded. Processing investigation...",
    "status.procesando": "Investigation in progress...",
    "status.sin_doc": "Investigation in progress (no document attached)...",
    "status.completado": "Investigation completed.",
    "no.entidades":   "No linked entities detected.",
    "no.alertas":     "No alerts recorded.",
    "no.fuentes":     "No external sources recorded.",
    "badge.aprobado": "APPROVED", "badge.alerta": "RISK ALERT", "badge.bloqueado": "BLOCKED",
    "forense.autentico": "✓ Authentic Document",
    "forense.alterado":  "⚠ Possible Alteration Detected",
    "forense.pendiente": "— Verdict Pending",
    "valid.req": "Please fill in the main search field.",
    "valid.login": "You must be logged in.",
    "doc.label.empresa": "Tax ID / Registration", "doc.label.inmueble": "Address / Cadastral Ref.",
    "loading.sublabel": "Consulting databases and external sources",
  }
};

function t(key) {
  return (_i18n[_lang] || _i18n.es)[key] || (_i18n.es)[key] || key;
}

function aplicarIdioma() {
  document.querySelectorAll("[data-i18n]").forEach(function(el) {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll("[data-i18n-ph]").forEach(function(el) {
    el.placeholder = t(el.getAttribute("data-i18n-ph"));
  });
}

document.addEventListener("DOMContentLoaded", aplicarIdioma);

// ── BANNER MÓVIL ─────────────────────────────────────────────────────────────

(function() {
  if (window.innerWidth > 768) return;
  if (localStorage.getItem("ahc_mob_banner_closed")) return;
  // Solo en páginas hub — no en herramientas con chat o formularios
  var path = window.location.pathname;
  var isHub = /\/(index\.html|compliance-hub\.html|markets\.html)?$/.test(path);
  if (!isHub) return;

  var s = document.createElement("style");
  s.textContent =
    "#mob-banner{"
    + "position:fixed;bottom:0;left:0;right:0;z-index:9998;"
    + "background:#0c1828;color:#a8c4de;"
    + "border-top:2px solid #1e3e6a;"
    + "padding:14px 16px 14px 20px;"
    + "display:flex;align-items:center;gap:12px;"
    + "box-shadow:0 -4px 24px rgba(0,0,0,.4);"
    + "font-family:'Segoe UI',system-ui,sans-serif"
    + "}"
    + "#mob-banner-icon{font-size:1.3rem;flex-shrink:0}"
    + "#mob-banner-txt{flex:1;font-size:0.78rem;line-height:1.5;color:#a8c4de}"
    + "#mob-banner-txt strong{color:#fff;display:block;font-size:0.8rem;margin-bottom:2px}"
    + "#mob-banner-close{"
    + "flex-shrink:0;background:none;border:1px solid #1e3e6a;"
    + "color:#4a7aaa;border-radius:3px;padding:6px 10px;"
    + "font-size:0.75rem;cursor:pointer;font-family:inherit;line-height:1"
    + "}"
    + "#mob-banner-close:active{background:#1a3050}";
  document.head.appendChild(s);

  var el = document.createElement("div");
  el.id = "mob-banner";
  el.innerHTML =
    '<div id="mob-banner-icon">💻</div>'
    + '<div id="mob-banner-txt">'
    +   '<strong>Mejor experiencia en escritorio</strong>'
    +   'Para visualización completa usá una PC o tablet.'
    + '</div>'
    + '<button id="mob-banner-close" onclick="this.parentElement.remove();localStorage.setItem(\'ahc_mob_banner_closed\',\'1\')">Entendido</button>';

  document.addEventListener("DOMContentLoaded", function() {
    document.body.appendChild(el);
  });
  if (document.readyState !== "loading") document.body.appendChild(el);
})();

// ── WALLET DE CRÉDITOS ───────────────────────────────────────────────────────

function iniciarEscuchaCreditos(user) {
  if (_unsubCreditos) _unsubCreditos();
  _unsubCreditos = db.collection("usuarios").doc(user.uid).onSnapshot(function(doc) {
    if (doc.exists) {
      var data = doc.data();
      _creditos        = typeof data.creditos === "number" ? data.creditos : 0;
      _userPlan        = data.plan || "trial";
      _trialExpiraDate = data.trial_expira ? data.trial_expira.toDate() : null;
      actualizarCreditosBadge(_creditos, _userPlan, _trialExpiraDate);

      // Mostrar T&C si aún no fueron aceptados
      if (!data.terminos_aceptados) {
        mostrarTerminos(user);
        return;
      }

      // Abrir paywall automáticamente si el trial expiró
      if (_userPlan === "trial" && _trialExpirado()) {
        mostrarPaywall("expired");
      }
    } else {
      // Primera vez: mostrar T&C antes de crear el perfil
      mostrarTerminos(user);
    }
  });
}

function mostrarTerminos(user) {
  if (document.getElementById("tc-overlay")) return;

  if (!document.getElementById("tc-styles")) {
    var s = document.createElement("style");
    s.id = "tc-styles";
    s.textContent =
      "#tc-overlay{position:fixed;inset:0;background:rgba(4,13,24,.75);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px}"
      + "#tc-modal{background:#fff;border-radius:8px;max-width:680px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.3);display:flex;flex-direction:column;max-height:90vh}"
      + ".tc-header{padding:28px 36px 0;flex-shrink:0}"
      + ".tc-label{font-size:0.72rem;font-weight:700;color:#1a56a0;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}"
      + ".tc-titulo{font-size:1.4rem;font-weight:700;color:#040d18;margin-bottom:4px}"
      + ".tc-subtitulo{font-size:0.88rem;color:#3a5068;margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #e0e8f0}"
      + ".tc-body{padding:0 36px;overflow-y:auto;flex:1}"
      + ".tc-section{margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #f0f0f0}"
      + ".tc-section:last-child{border-bottom:none}"
      + ".tc-section h3{font-size:0.82rem;font-weight:700;color:#1a56a0;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}"
      + ".tc-section p,.tc-section li{font-size:0.88rem;color:#3a5068;line-height:1.75}"
      + ".tc-section ul{padding-left:18px;margin-top:6px}"
      + ".tc-section ul li{margin-bottom:4px}"
      + ".tc-footer{padding:20px 36px 28px;flex-shrink:0;border-top:1px solid #e0e8f0}"
      + ".tc-check-row{display:flex;align-items:flex-start;gap:12px;margin-bottom:16px;cursor:pointer}"
      + ".tc-check-row input[type=checkbox]{width:18px;height:18px;flex-shrink:0;margin-top:2px;accent-color:#1a56a0;cursor:pointer}"
      + ".tc-check-row span{font-size:0.88rem;color:#1a2535;line-height:1.5}"
      + ".tc-check-row span a{color:#1a56a0;text-decoration:underline}"
      + ".tc-btns{display:flex;gap:12px;justify-content:flex-end}"
      + ".tc-btn-accept{padding:11px 28px;background:#1a56a0;color:#fff;border:none;border-radius:4px;font-size:0.9rem;font-weight:700;cursor:pointer;transition:background .15s}"
      + ".tc-btn-accept:hover{background:#1464bf}"
      + ".tc-btn-accept:disabled{opacity:.45;cursor:default}"
      + ".tc-btn-decline{padding:11px 20px;background:transparent;color:#3a5068;border:1px solid #c8d4e0;border-radius:4px;font-size:0.9rem;font-weight:600;cursor:pointer}"
      + ".tc-btn-decline:hover{color:#040d18}";
    document.head.appendChild(s);
  }

  var overlay = document.createElement("div");
  overlay.id = "tc-overlay";
  overlay.innerHTML =
    '<div id="tc-modal">'
    + '<div class="tc-header">'
    + '<div class="tc-label">AHC Intelligence — Plataforma</div>'
    + '<div class="tc-titulo">Términos y Condiciones de Uso</div>'
    + '<div class="tc-subtitulo">Por favor, leé y aceptá los términos antes de continuar. Última actualización: junio 2026.</div>'
    + '</div>'
    + '<div class="tc-body">'

    + '<div class="tc-section"><h3>1. Naturaleza del Servicio</h3><p>AHC Intelligence es una plataforma de inteligencia financiera y compliance que provee análisis de referencia basados en inteligencia artificial. Los reportes, análisis y recomendaciones generados <strong>no constituyen asesoramiento legal, financiero, regulatorio ni inversión formal</strong>. Son herramientas de apoyo para profesionales calificados.</p></div>'

    + '<div class="tc-section"><h3>2. Uso Autorizado</h3><p>El acceso está reservado exclusivamente para:</p><ul><li>Profesionales del sector financiero, legal y de compliance</li><li>Asesores de inversión y gestores de portafolios</li><li>Estudios jurídicos y firmas de consultoría</li><li>Instituciones financieras y corporativas</li></ul><p style="margin-top:8px">Queda expresamente <strong>prohibido</strong> el uso de la plataforma para actividades ilícitas, evasión fiscal, lavado de activos o cualquier fin contrario a la normativa vigente.</p></div>'

    + '<div class="tc-section"><h3>3. Confidencialidad de Datos</h3><p>AHC Intelligence no comparte los datos ingresados por el usuario con terceros no autorizados. La información procesada se utiliza exclusivamente para generar los análisis solicitados. El usuario es responsable de la veracidad y legalidad de los datos que ingresa a la plataforma.</p></div>'

    + '<div class="tc-section"><h3>4. Limitación de Responsabilidad</h3><p>AHC Intelligence no se responsabiliza por decisiones tomadas en base a los análisis generados. El usuario asume plena responsabilidad por el uso de los reportes. Los análisis de mercado, due diligence y auditorías de contratos son orientativos y deben ser validados por profesionales habilitados.</p></div>'

    + '<div class="tc-section"><h3>5. Sistema de Créditos y Suscripciones</h3><p>El plan Trial otorga 150 créditos con validez de 7 días. Los planes pagos se renuevan automáticamente según el ciclo de facturación seleccionado. Los créditos no utilizados no son acumulables entre ciclos. El reembolso está sujeto a las políticas vigentes al momento de la contratación.</p></div>'

    + '<div class="tc-section"><h3>6. Propiedad Intelectual</h3><p>Todo el contenido, metodología y tecnología de la plataforma es propiedad exclusiva de AHC Intelligence. Los reportes generados son para uso interno del cliente suscriptor. Queda prohibida su redistribución comercial sin autorización escrita.</p></div>'

    + '<div class="tc-section"><h3>7. Modificaciones</h3><p>AHC Intelligence se reserva el derecho de modificar estos términos con un preaviso de 15 días. El uso continuado de la plataforma implica la aceptación de las condiciones actualizadas.</p></div>'

    + '</div>'
    + '<div class="tc-footer">'
    + '<label class="tc-check-row" onclick="document.getElementById(\'tc-btn-accept\').disabled=!this.querySelector(\'input\').checked">'
    + '<input type="checkbox" id="tc-checkbox" onchange="document.getElementById(\'tc-btn-accept\').disabled=!this.checked" />'
    + '<span>He leído y acepto los <strong>Términos y Condiciones de Uso</strong> de AHC Intelligence. Entiendo que los análisis generados son de referencia y no constituyen asesoramiento profesional formal.</span>'
    + '</label>'
    + '<div class="tc-btns">'
    + '<button class="tc-btn-decline" onclick="_rechazarTerminos()">No acepto — Salir</button>'
    + '<button id="tc-btn-accept" class="tc-btn-accept" disabled onclick="_aceptarTerminos(\'' + user.uid + '\', \'' + (user.email || "") + '\', \'' + (user.displayName || "").replace(/'/g, "") + '\')">Acepto los Términos</button>'
    + '</div>'
    + '</div>'
    + '</div>';

  document.body.appendChild(overlay);
}

function _aceptarTerminos(uid, email, nombre) {
  var btn = document.getElementById("tc-btn-accept");
  if (btn) { btn.disabled = true; btn.textContent = "Activando cuenta..."; }

  var expira = new Date();
  expira.setDate(expira.getDate() + TRIAL_DIAS);

  db.collection("usuarios").doc(uid).set({
    email:               email || "",
    nombre:              nombre || "",
    plan:                "trial",
    creditos:            TRIAL_CREDITOS,
    trial_expira:        expira,
    terminos_aceptados:  true,
    terminos_aceptados_en: firebase.firestore.FieldValue.serverTimestamp(),
    creado_en:           firebase.firestore.FieldValue.serverTimestamp(),
  }, { merge: true }).then(function() {
    var el = document.getElementById("tc-overlay");
    if (el) el.remove();
    _mostrarToastBienvenida();
  }).catch(function(e) {
    console.warn("[TC]", e);
    if (btn) { btn.disabled = false; btn.textContent = "Acepto los Términos"; }
  });
}

function _rechazarTerminos() {
  if (_unsubCreditos) { _unsubCreditos(); _unsubCreditos = null; }
  auth.signOut().then(function() {
    var el = document.getElementById("tc-overlay");
    if (el) el.remove();
  });
}

function _trialExpirado() {
  if (_userPlan !== "trial") return false;
  if (!_trialExpiraDate) return false;
  return new Date() > _trialExpiraDate;
}

function _diasRestantesTrial() {
  if (!_trialExpiraDate) return 0;
  var diff = _trialExpiraDate - new Date();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

function actualizarCreditosBadge(creditos, plan, expira) {
  var badge = document.getElementById("creditos-badge");
  if (!badge) return;
  if (plan === "institucional") {
    badge.style.display     = "inline-flex";
    badge.style.color       = "#1a56a0";
    badge.style.borderColor = "#1a56a0";
    badge.textContent       = "Ilimitado · Institucional";
    badge.style.cursor      = "default";
    badge.onclick           = null;
    return;
  }
  var color = creditos > 50 ? "#1a6e3a" : creditos > 10 ? "#8a6000" : "#b02020";
  var planLabel = { trial: "Trial", starter: "Starter", professional: "Professional", enterprise: "Enterprise" }[plan] || plan;
  var extra = "";
  if (plan === "trial" && expira) {
    var dias = _diasRestantesTrial();
    extra = dias > 0 ? " · " + dias + "d restantes" : " · EXPIRADO";
    if (dias === 0) color = "#b02020";
  }
  badge.style.display     = "inline-flex";
  badge.style.color       = color;
  badge.style.borderColor = color;
  badge.textContent       = creditos.toLocaleString() + " créditos · " + planLabel + extra;
  badge.style.cursor      = "pointer";
  badge.onclick           = function() { mostrarPaywall("manual"); };
}

function verificarCreditos(tipo) {
  var _u = auth.currentUser;
  if (_u && _u.providerData.length > 0 && _u.providerData[0].providerId === "password" && !_u.emailVerified) {
    mostrarVerificacionPendiente(_u);
    return false;
  }
  if (_userPlan === "institucional") return true;
  // Primero: trial expirado
  if (_trialExpirado()) {
    var _uu = auth.currentUser;
    var _fbKey = _uu ? "ahc_fb_" + _uu.uid : null;
    if (_fbKey && !localStorage.getItem(_fbKey) && !_feedbackDado) {
      _mostrarFeedbackModal();
    } else {
      mostrarPaywall("expired");
    }
    return false;
  }
  // Segundo: créditos insuficientes
  var costo = CREDIT_COSTS[tipo] || 50;
  if (_creditos !== null && _creditos < costo) {
    mostrarPaywall("no_credits");
    return false;
  }
  return true;
}

function verificarArchivoTrial(file, contextoError) {
  if (_userPlan !== "trial") return true;
  if (file && file.size > TRIAL_MAX_BYTES) {
    var el = document.getElementById(contextoError);
    if (el) {
      el.style.color = "#b02020";
      el.textContent = "En el plan Trial los archivos tienen un límite de " + TRIAL_MAX_MB + " MB. Suscribite para procesar documentos de mayor tamaño.";
    }
    mostrarPaywall("file_limit");
    return false;
  }
  return true;
}

// ── PAYWALL MODAL ────────────────────────────────────────────────────────────

function mostrarPaywall(motivo) {
  if (document.getElementById("paywall-overlay")) return; // ya visible

  var titulo = motivo === "manual" ? "Recargá créditos cuando quieras" : "Recargá créditos para continuar";
  var subtitulo = "";
  if (motivo === "expired")         subtitulo = "Tu período de prueba de 7 días ha finalizado.";
  else if (motivo === "no_credits") subtitulo = "Agotaste tus créditos disponibles. Elegí un pack para seguir.";
  else if (motivo === "file_limit") subtitulo = "Tu plan Trial no admite archivos mayores a " + TRIAL_MAX_MB + " MB.";

  // Inyectar estilos del modal si no existen
  if (!document.getElementById("paywall-styles")) {
    var style = document.createElement("style");
    style.id = "paywall-styles";
    style.textContent =
      "#paywall-overlay{position:fixed;inset:0;background:rgba(4,13,24,.7);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px}"
      + "#paywall-modal{background:#fff;border-radius:8px;padding:40px 44px;max-width:920px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.25);position:relative;max-height:90vh;overflow-y:auto}"
      + ".pw-close{position:absolute;top:16px;right:20px;cursor:pointer;font-size:1.3rem;color:#a0b4c8;border:none;background:none}"
      + ".pw-close:hover{color:#1a2535}"
      + ".pw-label{font-size:0.72rem;font-weight:700;color:#1a56a0;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px}"
      + ".pw-titulo{font-size:1.6rem;font-weight:700;color:#040d18;margin-bottom:8px}"
      + ".pw-subtitulo{font-size:0.95rem;color:#3a5068;margin-bottom:32px}"
      + ".pw-planes{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px}"
      + ".pw-plan{border:1px solid #c8d4e0;border-radius:6px;padding:24px 20px;text-align:center;position:relative;transition:border-color .2s}"
      + ".pw-plan:hover{border-color:#1a56a0}"
      + ".pw-plan.destacado{border:2px solid #1a56a0;border-top:4px solid #1a56a0}"
      + ".pw-badge-hot{position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#1a56a0;color:#fff;font-size:0.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:3px 12px;border-radius:20px;white-space:nowrap}"
      + ".pw-plan-nombre{font-size:0.72rem;font-weight:700;color:#3a5068;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}"
      + ".pw-precio{font-size:2rem;font-weight:800;color:#040d18;line-height:1}"
      + ".pw-precio span{font-size:0.85rem;font-weight:400;color:#3a5068}"
      + ".pw-creditos{font-size:0.82rem;color:#1a6e3a;font-weight:600;margin:8px 0 16px}"
      + ".pw-lista{text-align:left;font-size:0.8rem;color:#3a5068;line-height:1.8;margin-bottom:20px;padding:0;list-style:none}"
      + ".pw-lista li::before{content:'✓ ';color:#1a56a0;font-weight:700}"
      + ".pw-btn{display:block;width:100%;padding:11px;background:#1a56a0;color:#fff;border:none;border-radius:4px;font-size:0.88rem;font-weight:700;cursor:pointer;text-decoration:none;transition:background .15s}"
      + ".pw-btn:hover{background:#1464bf}"
      + ".pw-plan.destacado .pw-btn{background:#1a56a0}"
      + ".pw-footer{text-align:center;font-size:0.78rem;color:#a0b4c8}"
      + ".pw-footer a{color:#1a56a0;text-decoration:none}"
      + ".pp-loading{text-align:center;font-size:0.78rem;color:#a0b4c8;padding:14px 0;border:1px dashed #c8d4e0;border-radius:4px;margin-top:4px}"
      + ".pw-sep{display:flex;align-items:center;gap:14px;margin:4px 0 20px}"
      + ".pw-sep::before,.pw-sep::after{content:'';flex:1;height:1px;background:#c8d4e0}"
      + ".pw-sep-txt{font-size:0.68rem;font-weight:700;color:#3a5068;letter-spacing:2.5px;text-transform:uppercase;white-space:nowrap}"
      + ".pw-inst{background:linear-gradient(135deg,#040d18 0%,#0c1e38 100%);border:1px solid #2a4060;border-top:3px solid #5a8ab8;border-radius:6px;padding:26px 28px;display:flex;align-items:center;gap:28px;margin-bottom:24px}"
      + ".pw-inst-left{flex:0 0 auto;min-width:170px}"
      + ".pw-inst-badge{font-size:0.62rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:#7aabe0;margin-bottom:8px}"
      + ".pw-inst-nombre{font-size:1rem;font-weight:800;color:#fff;margin-bottom:8px}"
      + ".pw-inst-precio{font-size:1.7rem;font-weight:800;color:#fff;line-height:1;margin-bottom:3px}"
      + ".pw-inst-precio span{font-size:0.8rem;font-weight:400;color:#7aabe0}"
      + ".pw-inst-sub{font-size:0.72rem;color:#4a7a9e;margin-top:5px}"
      + ".pw-inst-mid{flex:1;border-left:1px solid rgba(90,138,184,.18);padding-left:24px}"
      + ".pw-inst-lista{list-style:none;padding:0;font-size:0.8rem;color:#90b4cc;line-height:2}"
      + ".pw-inst-lista li::before{content:'◆ ';color:#5a8ab8;font-size:0.55rem;vertical-align:middle}"
      + ".pw-inst-right{flex:0 0 auto;text-align:center}"
      + ".pw-inst-btn{display:block;padding:13px 22px;background:transparent;color:#fff;border:1px solid #5a8ab8;border-radius:4px;font-size:0.85rem;font-weight:700;cursor:pointer;white-space:nowrap;transition:all .2s;text-align:center}"
      + ".pw-inst-btn:hover{background:#1a4a78;border-color:#7aabe0}"
      + ".pw-inst-nota{font-size:0.7rem;color:#3a6080;margin-top:8px;max-width:160px;line-height:1.5}"
      + "@media(max-width:640px){.pw-inst{flex-direction:column;gap:16px}.pw-inst-mid{border-left:none;padding-left:0;border-top:1px solid rgba(90,138,184,.18);padding-top:16px}.pw-planes{grid-template-columns:1fr}}"
      + "#inst-lead-overlay{position:fixed;inset:0;background:rgba(2,6,12,.92);z-index:9100;display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(4px)}"
      + "#inst-lead-modal{background:#07090e;color:#fff;border:1px solid #1e3050;border-top:2px solid #2a6ab8;border-radius:4px;max-width:520px;width:100%;box-shadow:0 0 80px rgba(30,48,80,.6),0 40px 80px rgba(0,0,0,.8);position:relative;overflow:hidden;max-height:90vh;overflow-y:auto}"
      + "#inst-lead-modal::before{content:'';position:absolute;top:0;left:0;right:0;height:200px;background:radial-gradient(ellipse at 50% 0%,rgba(42,106,184,.12) 0%,transparent 70%);pointer-events:none}"
      + ".inst-mhead{padding:28px 36px 22px;border-bottom:1px solid #0e1828}"
      + ".inst-mhead-top{display:flex;align-items:center;gap:12px;margin-bottom:6px}"
      + ".inst-mhead-icon{width:36px;height:36px;border-radius:3px;background:linear-gradient(135deg,#0d2040,#1a3a60);border:1px solid #2a5080;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0}"
      + ".inst-mhead-brand{font-size:0.65rem;font-weight:800;letter-spacing:3px;text-transform:uppercase;color:#2a6ab8}"
      + ".inst-mhead-title{font-size:1.05rem;font-weight:800;color:#fff;letter-spacing:0.5px}"
      + ".inst-mhead-sub{font-size:0.78rem;color:#3a6080;line-height:1.5;margin-top:2px}"
      + ".inst-mbody{padding:24px 36px 32px}"
      + ".inst-field{margin-bottom:18px;position:relative}"
      + ".inst-field label{display:block;font-size:0.65rem;font-weight:800;color:#2a6ab8;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}"
      + ".inst-field input,.inst-field select{width:100%;background:transparent;border:none;border-bottom:1px solid #1a3050;color:#c8d8e8;padding:8px 0;font-size:0.95rem;font-family:inherit;transition:border-color .2s;border-radius:0}"
      + ".inst-field input::placeholder{color:#1e3050}"
      + ".inst-field input:focus,.inst-field select:focus{outline:none;border-bottom-color:#2a6ab8;color:#fff}"
      + ".inst-field select{cursor:pointer;-webkit-appearance:none;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%232a6ab8'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 4px center}"
      + ".inst-field select option{background:#07090e;color:#c8d8e8}"
      + ".inst-frow{display:grid;grid-template-columns:1fr 1fr;gap:20px}"
      + ".inst-divider{height:1px;background:linear-gradient(90deg,transparent,#1a3050,transparent);margin:6px 0 18px}"
      + ".inst-btn-submit{width:100%;background:linear-gradient(135deg,#0d2040 0%,#1a3a60 100%);color:#7aabe0;border:1px solid #2a5080;padding:14px;font-size:0.78rem;font-weight:800;cursor:pointer;letter-spacing:3px;text-transform:uppercase;margin-top:10px;transition:all .25s;font-family:inherit}"
      + ".inst-btn-submit:hover{background:linear-gradient(135deg,#1a3a60,#2a5a90);color:#fff;border-color:#5a9ad8;box-shadow:0 0 24px rgba(42,106,184,.3)}"
      + ".inst-lock-note{text-align:center;font-size:0.68rem;color:#1a3050;letter-spacing:1px;text-transform:uppercase;margin-top:14px}"
      + ".inst-close{position:absolute;top:14px;right:16px;border:none;background:none;cursor:pointer;font-size:1rem;color:#1e3050;line-height:1;padding:4px}"
      + ".inst-close:hover{color:#7aabe0}"
      + ".inst-confirm{text-align:center;padding:40px 36px}"
      + ".inst-confirm-icon{font-size:2rem;margin-bottom:18px;opacity:.9}"
      + ".inst-confirm-titulo{font-size:0.75rem;font-weight:800;color:#2a6ab8;letter-spacing:3px;text-transform:uppercase;margin-bottom:16px}"
      + ".inst-confirm-txt{font-size:0.88rem;color:#4a7090;line-height:1.9;max-width:380px;margin:0 auto}";
    document.head.appendChild(style);
  }

  var overlay = document.createElement("div");
  overlay.id = "paywall-overlay";
  overlay.innerHTML =
    '<div id="paywall-modal">'
    + '<button class="pw-close" onclick="cerrarPaywall()">✕</button>'
    + '<div class="pw-label">AHC Intelligence — Planes</div>'
    + '<div class="pw-titulo">' + titulo + '</div>'
    + (subtitulo ? '<div class="pw-subtitulo">' + subtitulo + '</div>' : '<div style="margin-bottom:32px"></div>')
    + '<div class="pw-planes">'

    // PACK 1.500
    + '<div class="pw-plan">'
    + '<div class="pw-plan-nombre">Pack Básico</div>'
    + '<div class="pw-precio">USD 10<span> único</span></div>'
    + '<div class="pw-creditos">1,500 créditos</div>'
    + '<ul class="pw-lista"><li>30 investigaciones KYC</li><li>20 análisis de documentos</li><li>10 contratos</li><li>Sin renovación automática</li></ul>'
    + '<div id="pp-btn-starter" class="pp-loading">Cargando...</div>'
    + '</div>'

    // PACK 5.000
    + '<div class="pw-plan destacado">'
    + '<div class="pw-badge-hot">Mejor valor</div>'
    + '<div class="pw-plan-nombre">Pack Profesional</div>'
    + '<div class="pw-precio">USD 50<span> único</span></div>'
    + '<div class="pw-creditos">5,000 créditos</div>'
    + '<ul class="pw-lista"><li>100 investigaciones KYC</li><li>60 análisis de documentos</li><li>40 contratos</li><li>Sin renovación automática</li></ul>'
    + '<div id="pp-btn-professional" class="pp-loading">Cargando...</div>'
    + '</div>'

    // PACK 25.000
    + '<div class="pw-plan">'
    + '<div class="pw-plan-nombre">Pack Enterprise</div>'
    + '<div class="pw-precio">USD 250<span> único</span></div>'
    + '<div class="pw-creditos">25,000 créditos</div>'
    + '<ul class="pw-lista"><li>600 investigaciones KYC</li><li>400 análisis de documentos</li><li>250 contratos</li><li>Sin renovación automática</li></ul>'
    + '<div id="pp-btn-enterprise" class="pp-loading">Cargando...</div>'
    + '</div>'

    + '</div>'

    // SEPARADOR + TARJETA INSTITUCIONAL
    + '<div class="pw-sep"><span class="pw-sep-txt">Soluciones Institucionales</span></div>'
    + '<div class="pw-inst">'
    +   '<div class="pw-inst-left">'
    +     '<div class="pw-inst-badge">Institutional Custom</div>'
    +     '<div class="pw-inst-nombre">Enterprise Dedicado</div>'
    +     '<div style="font-size:0.72rem;color:#4a7a9e;margin-top:4px;line-height:1.6">Trato privado · Contrato firmado<br>Facturación formal SWIFT</div>'
    +   '</div>'
    +   '<div class="pw-inst-mid">'
    +     '<ul class="pw-inst-lista">'
    +       '<li>White-Label completo bajo tu dominio corporativo</li>'
    +       '<li>Infraestructura dedicada — On-Premise / Private Cloud</li>'
    +       '<li>Créditos ilimitados · volumen corporativo sin restricción</li>'
    +       '<li>Soporte técnico 24/7 con SLA garantizado</li>'
    +       '<li>NDA + contrato firmado + facturación formal SWIFT</li>'
    +     '</ul>'
    +   '</div>'
    +   '<div class="pw-inst-right">'
    +     '<button class="pw-inst-btn" onclick="abrirFormInstitucional()">Contactar Oficial<br>de Cuentas</button>'
    +     '<div class="pw-inst-nota">Reunión técnica + borrador de NDA en 2 h</div>'
    +   '</div>'
    + '</div>'

    + '<div class="pw-footer">Pago único · Sin renovación automática · Pago seguro con tarjeta &nbsp;·&nbsp; Contratos institucionales vía SWIFT</div>'
    + '</div>';

  overlay.addEventListener("click", function(e) {
    if (e.target === overlay) cerrarPaywall();
  });

  document.body.appendChild(overlay);
  _iniciarPayPalSDK();
}

function _iniciarPayPalSDK() {
  if (window.paypal) { _renderPayPalBotones(); return; }
  if (document.getElementById("paypal-sdk-script")) {
    var poll = setInterval(function() {
      if (window.paypal) { clearInterval(poll); _renderPayPalBotones(); }
    }, 150);
    return;
  }
  var s = document.createElement("script");
  s.id  = "paypal-sdk-script";
  s.src = "https://www.paypal.com/sdk/js?client-id=" + PAYPAL_CLIENT_ID + "&intent=capture&currency=USD&components=buttons";
  s.onload  = _renderPayPalBotones;
  s.onerror = function() {
    PAYPAL_PACKS.forEach(function(p) {
      var el = document.getElementById("pp-btn-" + p.id);
      if (el) el.innerHTML = '<div style="color:#b02020;font-size:0.78rem;text-align:center;padding:8px">Error cargando PayPal. Recargá la página.</div>';
    });
  };
  document.head.appendChild(s);
}

function _renderPayPalBotones() {
  PAYPAL_PACKS.forEach(function(pack) {
    var container = document.getElementById("pp-btn-" + pack.id);
    if (!container) return;
    container.innerHTML = "";
    window.paypal.Buttons({
      fundingSource: window.paypal.FUNDING.CARD,
      style: { shape: "rect", color: "black", height: 40 },
      createOrder: function(data, actions) {
        return actions.order.create({
          purchase_units: [{
            description: pack.label + " — AHC Intelligence",
            amount: { value: pack.precio, currency_code: "USD" },
          }],
        });
      },
      onApprove: function(data, actions) {
        return actions.order.capture().then(function(details) {
          _procesarPagoPayPal(pack.id, details.id, pack.creditos);
        });
      },
      onError: function(err) {
        console.error("[PayPal]", err);
        if (container) container.innerHTML = '<div style="color:#b02020;font-size:0.78rem;text-align:center;padding:8px">Error al procesar. Intentá de nuevo.</div>';
      }
    }).render("#pp-btn-" + pack.id);
  });
}

function _procesarPagoPayPal(packId, orderId, creditos) {
  var user = firebase.auth().currentUser;
  if (!user) return;
  var overlay = document.getElementById("paywall-overlay");
  if (overlay) {
    overlay.innerHTML = '<div id="paywall-modal" style="text-align:center;padding:64px 44px;max-width:480px;width:100%">'
      + '<div style="font-size:2.2rem;margin-bottom:16px">⏳</div>'
      + '<div style="font-size:1.25rem;font-weight:700;color:#040d18;margin-bottom:10px">Acreditando ' + creditos.toLocaleString() + ' créditos...</div>'
      + '<div style="font-size:0.9rem;color:#3a5068;line-height:1.7">Verificando el pago con PayPal.<br>Los créditos aparecerán en segundos.<br>No cierres esta ventana.</div>'
      + '</div>';
  }
  db.collection("pagos_pendientes").add({
    pack_id:      packId,
    order_id:     orderId,
    creditos:     creditos,
    uid:          user.uid,
    email:        user.email || "",
    solicitado_en: firebase.firestore.FieldValue.serverTimestamp(),
  }).then(function() {
    setTimeout(cerrarPaywall, 5000);
  }).catch(function() {
    cerrarPaywall();
  });
}

function cerrarPaywall() {
  var el = document.getElementById("paywall-overlay");
  if (el) el.remove();
}

// ── FORMULARIO LEAD INSTITUCIONAL ────────────────────────────────────────────

function abrirFormInstitucional() {
  if (document.getElementById("inst-lead-overlay")) return;

  if (!document.getElementById("inst-lead-styles")) {
    var s = document.createElement("style");
    s.id = "inst-lead-styles";
    s.textContent =
      "#inst-lead-overlay{"
      + "position:fixed;inset:0;z-index:9999;"
      + "background:rgba(0,4,10,.85);"
      + "backdrop-filter:blur(6px);"
      + "display:flex;align-items:center;justify-content:center;padding:20px"
      + "}"
      + "#inst-lead-modal{"
      + "position:relative;width:100%;max-width:560px;"
      + "background:#05080f;"
      + "border:1px solid #1a2e4a;"
      + "border-top:3px solid #2a6ab8;"
      + "border-radius:6px;"
      + "box-shadow:0 0 0 1px rgba(42,106,184,.08),0 32px 80px rgba(0,0,0,.9),0 0 60px rgba(10,30,70,.5);"
      + "font-family:inherit;color:#c8d8ea;"
      + "overflow:hidden;max-height:92vh;overflow-y:auto"
      + "}"
      + ".ilm-glow{"
      + "position:absolute;top:0;left:0;right:0;height:240px;pointer-events:none;"
      + "background:radial-gradient(ellipse 80% 60% at 50% -10%,rgba(42,106,184,.18) 0%,transparent 70%)"
      + "}"
      + ".ilm-close{"
      + "position:absolute;top:16px;right:18px;"
      + "background:none;border:none;cursor:pointer;"
      + "color:#2a4a6a;font-size:1.1rem;line-height:1;padding:4px 6px;"
      + "transition:color .2s;z-index:2"
      + "}"
      + ".ilm-close:hover{color:#7aabe0}"
      + ".ilm-head{"
      + "padding:32px 36px 24px;border-bottom:1px solid #0d1e30;position:relative"
      + "}"
      + ".ilm-brand{"
      + "display:flex;align-items:center;gap:10px;margin-bottom:14px"
      + "}"
      + ".ilm-brand-dot{"
      + "width:8px;height:8px;border-radius:50%;"
      + "background:#2a6ab8;box-shadow:0 0 8px #2a6ab8;flex-shrink:0"
      + "}"
      + ".ilm-brand-label{"
      + "font-size:0.6rem;font-weight:800;letter-spacing:4px;"
      + "text-transform:uppercase;color:#2a6ab8"
      + "}"
      + ".ilm-title{"
      + "font-size:1.15rem;font-weight:800;color:#fff;"
      + "letter-spacing:.5px;line-height:1.3;margin-bottom:6px"
      + "}"
      + ".ilm-subtitle{"
      + "font-size:0.78rem;color:#304a64;line-height:1.6"
      + "}"
      + ".ilm-body{padding:28px 36px 36px}"
      + ".ilm-field{margin-bottom:22px}"
      + ".ilm-field label{"
      + "display:block;font-size:0.6rem;font-weight:800;"
      + "letter-spacing:3px;text-transform:uppercase;"
      + "color:#2a6ab8;margin-bottom:10px"
      + "}"
      + ".ilm-field input,.ilm-field select{"
      + "width:100%;background:transparent;"
      + "border:none;border-bottom:1px solid #1a2e48;"
      + "color:#c8d8ea;padding:10px 0;"
      + "font-size:0.95rem;font-family:inherit;"
      + "transition:border-color .2s,color .2s;"
      + "outline:none;border-radius:0;box-sizing:border-box"
      + "}"
      + ".ilm-field input::placeholder{color:#1e3354}"
      + ".ilm-field input:focus,.ilm-field select:focus{"
      + "border-bottom-color:#2a6ab8;color:#fff"
      + "}"
      + ".ilm-field select{"
      + "cursor:pointer;-webkit-appearance:none;appearance:none;"
      + "background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%232a6ab8'/%3E%3C/svg%3E\");"
      + "background-repeat:no-repeat;background-position:right 6px center"
      + "}"
      + ".ilm-field select option{background:#05080f;color:#c8d8ea}"
      + ".ilm-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}"
      + ".ilm-divider{"
      + "height:1px;margin:4px 0 24px;"
      + "background:linear-gradient(90deg,transparent,#1a2e48 40%,transparent)"
      + "}"
      + ".ilm-error{"
      + "font-size:0.78rem;color:#f87171;"
      + "margin-bottom:12px;display:none;"
      + "letter-spacing:.5px"
      + "}"
      + ".ilm-submit{"
      + "width:100%;padding:15px;"
      + "background:linear-gradient(135deg,#0a1e3a 0%,#163362 100%);"
      + "color:#6aa3d8;border:1px solid #1e3e6a;"
      + "font-size:0.72rem;font-weight:800;"
      + "letter-spacing:4px;text-transform:uppercase;"
      + "cursor:pointer;font-family:inherit;"
      + "transition:all .25s;border-radius:3px;margin-top:4px"
      + "}"
      + ".ilm-submit:hover{"
      + "background:linear-gradient(135deg,#163362,#1e4a88);"
      + "color:#b8d4f0;border-color:#3a6ab8;"
      + "box-shadow:0 0 28px rgba(42,106,184,.25)"
      + "}"
      + ".ilm-submit:disabled{opacity:.5;cursor:not-allowed}"
      + ".ilm-footnote{"
      + "text-align:center;font-size:0.62rem;"
      + "color:#1a2e44;letter-spacing:2px;"
      + "text-transform:uppercase;margin-top:16px"
      + "}"
      + ".ilm-confirm{text-align:center;padding:48px 36px}"
      + ".ilm-confirm-icon{font-size:2rem;margin-bottom:20px}"
      + ".ilm-confirm-label{"
      + "font-size:0.62rem;font-weight:800;color:#2a6ab8;"
      + "letter-spacing:4px;text-transform:uppercase;margin-bottom:14px"
      + "}"
      + ".ilm-confirm-txt{"
      + "font-size:0.88rem;color:#4a6a84;"
      + "line-height:1.9;max-width:360px;margin:0 auto"
      + "}"
      + ".ilm-confirm-btn{"
      + "margin-top:28px;padding:12px 36px;"
      + "background:#0d1e30;color:#6aa3d8;"
      + "border:1px solid #1a3050;border-radius:3px;"
      + "font-size:0.75rem;font-weight:800;"
      + "letter-spacing:2px;text-transform:uppercase;"
      + "cursor:pointer;font-family:inherit"
      + "}"
      + "@media(max-width:520px){"
      + "#inst-lead-modal{border-radius:4px}"
      + ".ilm-head{padding:24px 20px 18px}"
      + ".ilm-body{padding:20px 20px 28px}"
      + ".ilm-grid{grid-template-columns:1fr}"
      + "}";
    document.head.appendChild(s);
  }

  var overlay = document.createElement("div");
  overlay.id  = "inst-lead-overlay";
  overlay.innerHTML =
    '<div id="inst-lead-modal">'
    + '<div class="ilm-glow"></div>'
    + '<button class="ilm-close" onclick="_cerrarFormInstitucional()">✕</button>'
    + '<div class="ilm-head">'
    +   '<div class="ilm-brand"><div class="ilm-brand-dot"></div><div class="ilm-brand-label">AHC Intelligence · Institutional</div></div>'
    +   '<div class="ilm-title">Private Infrastructure Request</div>'
    +   '<div class="ilm-subtitle">Infraestructura corporativa dedicada · NDA + contrato firmado · SWIFT</div>'
    + '</div>'
    + '<div class="ilm-body">'
    +   '<div id="inst-lead-form">'
    +     '<div class="ilm-field">'
    +       '<label>Institución Financiera / Fondo *</label>'
    +       '<input id="inst-name" type="text" placeholder="Ej. Zurich Private Banking" autocomplete="organization" />'
    +     '</div>'
    +     '<div class="ilm-grid">'
    +       '<div class="ilm-field">'
    +         '<label>Cargo del Solicitante *</label>'
    +         '<input id="inst-role" type="text" placeholder="Ej. Chief Compliance Officer" />'
    +       '</div>'
    +       '<div class="ilm-field">'
    +         '<label>País de Regulación *</label>'
    +         '<input id="inst-country" type="text" placeholder="Ej. Suiza · FINMA" />'
    +       '</div>'
    +     '</div>'
    +     '<div class="ilm-divider"></div>'
    +     '<div class="ilm-field">'
    +       '<label>Requerimiento de Infraestructura</label>'
    +       '<select id="inst-req">'
    +         '<option value="private_cloud">Nube Privada Dedicada — AWS / GCP Aislado</option>'
    +         '<option value="on_premise">On-Premise — Servidores de la Institución</option>'
    +         '<option value="hybrid">Híbrido — Cifrado Extremo a Extremo</option>'
    +       '</select>'
    +     '</div>'
    +     '<div id="inst-error" class="ilm-error"></div>'
    +     '<button class="ilm-submit" onclick="enviarLeadInstitucional()">SOLICITAR CONEXIÓN SEGURA</button>'
    +     '<div class="ilm-footnote">🔒 &nbsp; Información tratada bajo protocolo de confidencialidad</div>'
    +   '</div>'
    + '</div>'
    + '</div>';

  overlay.addEventListener("click", function(e) { if (e.target === overlay) _cerrarFormInstitucional(); });
  document.body.appendChild(overlay);
}

function _cerrarFormInstitucional() {
  var el = document.getElementById("inst-lead-overlay");
  if (el) el.remove();
}

function enviarLeadInstitucional() {
  var nombre  = (document.getElementById("inst-name")    || {}).value || "";
  var cargo   = (document.getElementById("inst-role")    || {}).value || "";
  var pais    = (document.getElementById("inst-country") || {}).value || "";
  var infra   = (document.getElementById("inst-req")     || {}).value || "private_cloud";
  var errEl   = document.getElementById("inst-error");

  if (!nombre.trim() || !cargo.trim() || !pais.trim()) {
    if (errEl) { errEl.textContent = "Completá los campos obligatorios (*)"; errEl.style.display = "block"; }
    return;
  }
  if (errEl) errEl.style.display = "none";

  var btn = document.querySelector(".ilm-submit");
  if (btn) { btn.disabled = true; btn.textContent = "PROCESANDO..."; }

  var user = firebase.auth().currentUser;
  db.collection("leads_institucionales").add({
    institucion:                nombre.trim(),
    cargo_solicitante:          cargo.trim(),
    pais_jurisdiccion:          pais.trim(),
    infraestructura_solicitada: infra,
    status_lead:                "PENDIENTE_NDA",
    prioridad:                  "CRÍTICA_ALTA_VALOR",
    tarifa_base_cotizada:       5000.00,
    uid_solicitante:            user ? user.uid : "anonimo",
    fecha_solicitud:            firebase.firestore.FieldValue.serverTimestamp(),
  }).then(function() {
    var form = document.getElementById("inst-lead-form");
    if (form) {
      form.innerHTML =
        '<div class="ilm-confirm">'
        + '<div class="ilm-confirm-icon">🔐</div>'
        + '<div class="ilm-confirm-label">Solicitud recibida</div>'
        + '<div class="ilm-confirm-txt">'
        +   'Tu solicitud de infraestructura corporativa ha sido registrada.<br><br>'
        +   'Un ejecutivo de <strong style="color:#c8d8ea">AHC Intelligence</strong> se pondrá en contacto en las próximas <strong style="color:#c8d8ea">2 horas</strong> para coordinar una reunión técnica y el envío del borrador de NDA.'
        + '</div>'
        + '<button class="ilm-confirm-btn" onclick="_cerrarFormInstitucional()">CERRAR</button>'
        + '</div>';
    }
  }).catch(function(err) {
    console.error("[INST LEAD]", err);
    if (btn) { btn.disabled = false; btn.textContent = "SOLICITAR CONEXIÓN SEGURA"; }
    if (errEl) { errEl.textContent = "Error al enviar. Intentá de nuevo."; errEl.style.display = "block"; }
  });
}

// ── ARCHIVO / COMPLIANCE ─────────────────────────────────────────────────────

function selectArchivoForense(file) {
  if (!file) return;
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    document.getElementById("estado-investigacion").textContent = "Tipo de archivo no permitido. Solo PDF, JPG y PNG.";
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    document.getElementById("estado-investigacion").textContent = "El archivo supera el límite de 10 MB.";
    return;
  }
  _archivoSeleccionado = file;
  mostrarFilePreview(file, "drop-zone", "file-preview");
}

function limpiarArchivo() {
  _archivoSeleccionado = null;
  document.getElementById("file-input").value = "";
  document.getElementById("file-preview").style.display = "none";
  document.getElementById("drop-zone").style.display    = "block";
}

// ── ARCHIVO / CONTRATOS ──────────────────────────────────────────────────────

function selectContratoFile(file) {
  if (!file) return;
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    document.getElementById("estado-contratos").textContent = "Tipo de archivo no permitido. Solo PDF, JPG y PNG.";
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    document.getElementById("estado-contratos").textContent = "El archivo supera el límite de 25 MB.";
    return;
  }
  if (!verificarArchivoTrial(file, "estado-contratos")) return;
  _contratoSeleccionado = file;
  mostrarFilePreview(file, "drop-zone-contrato", "file-preview-contrato");
}

function limpiarContrato() {
  _contratoSeleccionado = null;
  document.getElementById("file-input-contrato").value = "";
  document.getElementById("file-preview-contrato").style.display = "none";
  document.getElementById("drop-zone-contrato").style.display    = "block";
}

function selectContratoRecibidoFile(file) {
  if (!file) return;
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    document.getElementById("estado-contratos").textContent = "Tipo de archivo no permitido. Solo PDF, JPG y PNG.";
    return;
  }
  if (file.size > 25 * 1024 * 1024) {
    document.getElementById("estado-contratos").textContent = "El archivo supera el límite de 25 MB.";
    return;
  }
  if (!verificarArchivoTrial(file, "estado-contratos")) return;
  _contratoRecibido = file;
  mostrarFilePreview(file, "drop-zone-contrato-recibido", "file-preview-contrato-recibido");
}

function limpiarContratoRecibido() {
  _contratoRecibido = null;
  document.getElementById("file-input-contrato-recibido").value = "";
  document.getElementById("file-preview-contrato-recibido").style.display = "none";
  document.getElementById("drop-zone-contrato-recibido").style.display    = "block";
}

function toggleModoContrato(modo) {
  _modoContrato = modo;
  document.querySelectorAll(".modo-btn").forEach(function(b) { b.classList.remove("active"); });
  event.currentTarget.classList.add("active");
  var fieldRec  = document.getElementById("field-contrato-recibido");
  var lblOrig   = document.getElementById("label-contrato-original");
  var btnSubmit = document.querySelector(".btn-submit");
  if (modo === "comparativo") {
    if (fieldRec)  fieldRec.style.display  = "block";
    if (lblOrig)   lblOrig.innerHTML = 'Contrato Original (el que enviaste) <span style="font-weight:400;color:var(--red-txt)">*</span>';
    if (btnSubmit) btnSubmit.textContent   = "Comparar Contratos con IA";
  } else {
    if (fieldRec)  fieldRec.style.display  = "none";
    if (lblOrig)   lblOrig.innerHTML = 'Contrato a Analizar <span style="font-weight:400;color:var(--red-txt)">*</span>';
    if (btnSubmit) btnSubmit.textContent   = "Analizar Contrato con IA";
    limpiarContratoRecibido();
  }
}

function mostrarFilePreview(file, dropZoneId, previewId) {
  var icons   = { "application/pdf": "📄", "image/png": "🖼", "image/jpeg": "🖼" };
  var icon    = icons[file.type] || "📎";
  var sizeMB  = (file.size / (1024 * 1024)).toFixed(2);
  var dropEl  = document.getElementById(dropZoneId);
  var prevEl  = document.getElementById(previewId);
  if (dropEl) dropEl.style.display = "none";
  if (prevEl) {
    prevEl.style.display = "flex";
    var removeFn = dropZoneId.includes("contrato-recibido") ? "limpiarContratoRecibido" : dropZoneId.includes("contrato") ? "limpiarContrato" : dropZoneId.includes("forensic") ? "limpiarForensicDoc" : "limpiarArchivo";
    prevEl.innerHTML =
      '<span class="file-preview-icon">' + icon + '</span>'
      + '<span class="file-preview-name">' + escHtml(file.name) + '</span>'
      + '<span class="file-preview-size">' + escHtml(sizeMB) + ' MB</span>'
      + '<span class="file-remove" onclick="' + removeFn + '()" title="Quitar">✕</span>';
  }
}

// ── ARCHIVO / FORENSE ────────────────────────────────────────────────────────

var _forenseSeleccionado = null;

function selectForensicDoc(file) {
  if (!file) return;
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    document.getElementById("estado-forensic").textContent = "Tipo de archivo no permitido. Solo PDF, JPG y PNG.";
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    document.getElementById("estado-forensic").textContent = "El archivo supera el límite de 10 MB.";
    return;
  }
  if (!verificarArchivoTrial(file, "estado-forensic")) return;
  _forenseSeleccionado = file;
  mostrarFilePreview(file, "drop-zone-forensic", "file-preview-forensic");
}

function limpiarForensicDoc() {
  _forenseSeleccionado = null;
  var inp = document.getElementById("file-input-forensic");
  if (inp) inp.value = "";
  var pv = document.getElementById("file-preview-forensic");
  var dz = document.getElementById("drop-zone-forensic");
  if (pv) pv.style.display = "none";
  if (dz) dz.style.display = "block";
}

// ── SUBIR ARCHIVO A STORAGE ──────────────────────────────────────────────────

async function subirArchivo(user, tareaId, file, carpeta) {
  if (!file || !storage) return null;
  var path = carpeta + "/" + user.uid + "/" + tareaId + "/" + file.name;
  var ref  = storage.ref(path);
  await ref.put(file);
  return { path: path, nombre: file.name, tipo: file.type };
}

// ── COMPLIANCE ───────────────────────────────────────────────────────────────

function toggleTipoEntidad(tipo) {
  _tipoEntidad = tipo;
  ["persona", "empresa", "inmueble"].forEach(function(t) {
    document.getElementById("fields-" + t).style.display = t === tipo ? "" : "none";
  });
  document.querySelectorAll(".tipo-btn").forEach(function(btn) {
    btn.classList.toggle("active", btn.getAttribute("onclick").indexOf("'" + tipo + "'") >= 0);
  });
  var submitKeys = { persona: "submit.persona", empresa: "submit.empresa", inmueble: "submit.inmueble" };
  document.getElementById("btn-submit-investigacion").textContent = t(submitKeys[tipo] || "submit.persona");
}

async function enviarInvestigacion(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!user) { alert(t("valid.login")); return; }
  if (!verificarCreditos("compliance")) return;

  // Cancelar listener anterior antes de iniciar nueva búsqueda
  if (_unsubCompliance) { _unsubCompliance(); _unsubCompliance = null; }

  if (_tipoEntidad === "empresa") {
    _datosCliente = {
      tipo_entidad: "empresa",
      nombre:       document.getElementById("empresa_nombre").value.trim(),
      documento:    document.getElementById("empresa_rut").value.trim(),
      nacionalidad: document.getElementById("empresa_pais").value.trim(),
      paises_clave: document.getElementById("empresa_paises_clave").value.split(",").map(function(p){ return p.trim(); }),
    };
  } else if (_tipoEntidad === "inmueble") {
    _datosCliente = {
      tipo_entidad: "inmueble",
      nombre:       document.getElementById("inmueble_descripcion").value.trim(),
      documento:    document.getElementById("inmueble_direccion").value.trim(),
      titular:      document.getElementById("inmueble_titular").value.trim(),
      nacionalidad: document.getElementById("inmueble_pais").value.trim(),
      paises_clave: [],
    };
  } else {
    _datosCliente = {
      tipo_entidad: "persona",
      nombre:       document.getElementById("nombre").value.trim(),
      documento:    document.getElementById("documento").value.trim(),
      nacionalidad: document.getElementById("nacionalidad").value.trim(),
      paises_clave: document.getElementById("paises_clave").value.split(",").map(function(p){ return p.trim(); }),
    };
  }

  if (!_datosCliente.nombre) { alert(t("valid.req")); return; }

  var estado = document.getElementById("estado-investigacion");
  estado.className = "estado-msg activo";
  estado.style.color = "";
  estado.textContent = t("status.creando");

  var datos = Object.assign({
    tipo: "compliance", status: "PENDIENTE", uid: user.uid,
    creado_en: firebase.firestore.FieldValue.serverTimestamp(),
  }, _datosCliente);

  var ref = await db.collection("tareas_pendientes").add(datos);
  _tareaActivaId = ref.id;

  if (_archivoSeleccionado) {
    estado.innerHTML = '<span class="ahc-spinner"></span>' + t("status.subiendo");
    try {
      var info = await subirArchivo(user, ref.id, _archivoSeleccionado, "documentos");
      if (info) await ref.update({ archivo_storage_path: info.path, archivo_nombre: info.nombre, archivo_tipo: info.tipo });
      estado.innerHTML = '<span class="ahc-spinner"></span>' + t("status.subido");
    } catch(e) {
      console.warn("[STORAGE]", e);
      estado.innerHTML = '<span class="ahc-spinner"></span>' + t("status.sin_doc");
    }
  } else {
    estado.innerHTML = '<span class="ahc-spinner"></span>' + t("status.procesando");
  }

  document.getElementById("reporte-container").style.display = "none";
  document.getElementById("placeholder-msg").style.display   = "none";
  _mostrarLoadingPanel(t("status.procesando"), t("loading.sublabel"));
  escucharResultadoCompliance(ref.id);
}

// ── MERCADOS ─────────────────────────────────────────────────────────────────

async function enviarConsultaMercados(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!verificarCreditos("markets")) return;

  var datos = {
    tipo: "markets", status: "PENDIENTE", uid: user.uid,
    activo:        (document.querySelector('input[name="activo"]:checked') || {}).value || "Oro (XAU/USD)",
    perfil_riesgo: (document.querySelector('input[name="perfil_riesgo"]:checked') || {}).value || "Moderado",
    monto_usd:     parseFloat(document.getElementById("monto_usd").value),
    horizonte:     document.getElementById("horizonte").value,
    creado_en:     firebase.firestore.FieldValue.serverTimestamp(),
  };

  var ref = await db.collection("tareas_pendientes").add(datos);
  document.getElementById("estado-mercados").innerHTML = '<span class="ahc-spinner"></span>Procesando consulta...';
  escucharResultadoMercados(ref.id);
}

// ── CONTRATOS ────────────────────────────────────────────────────────────────

async function enviarAnalisisContrato(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!verificarCreditos("contracts")) return;

  var estado = document.getElementById("estado-contratos");
  if (!_contratoSeleccionado) {
    estado.style.color = "#b02020";
    estado.textContent = "Debe adjuntar el contrato antes de continuar.";
    return;
  }
  if (_modoContrato === "comparativo" && !_contratoRecibido) {
    estado.style.color = "#b02020";
    estado.textContent = "En modo comparativo debe adjuntar ambos contratos.";
    return;
  }

  estado.style.color = "";
  estado.className   = "estado-msg activo";
  estado.textContent = "Subiendo contrato...";

  var datos = {
    tipo:              "contracts",
    modo:              _modoContrato,
    status:            "PENDIENTE",
    uid:               user.uid,
    rol_cliente:       document.getElementById("rol_cliente").value,
    notas_adicionales: (document.getElementById("notas_adicionales") || {}).value || "",
    creado_en:         firebase.firestore.FieldValue.serverTimestamp(),
  };

  var ref = await db.collection("tareas_pendientes").add(datos);
  _tareaActivaId = ref.id;

  try {
    var info = await subirArchivo(user, ref.id, _contratoSeleccionado, "contratos");
    if (info) await ref.update({ archivo_storage_path: info.path, archivo_nombre: info.nombre, archivo_tipo: info.tipo });
    estado.textContent = _modoContrato === "comparativo" ? "Contrato original subido..." : "Contrato subido. Analizando...";
  } catch(e) {
    console.warn("[STORAGE]", e);
    estado.textContent = "Procesando...";
  }

  if (_modoContrato === "comparativo" && _contratoRecibido) {
    try {
      estado.textContent = "Subiendo contrato recibido...";
      var info2 = await subirArchivo(user, ref.id + "_v2", _contratoRecibido, "contratos");
      if (info2) await ref.update({ archivo2_storage_path: info2.path, archivo2_nombre: info2.nombre });
      estado.textContent = "Contratos subidos. Comparando...";
    } catch(e) {
      console.warn("[STORAGE v2]", e);
      estado.textContent = "Comparando contratos...";
    }
  }

  document.getElementById("reporte-container").style.display = "none";
  document.getElementById("placeholder-msg").style.display   = "flex";
  var modoCaptura = _modoContrato;
  escucharResultadoContratos(ref.id, modoCaptura);
}

// ── LISTENERS ────────────────────────────────────────────────────────────────

function escucharResultadoCompliance(tareaId) {
  // Capturar copia del cliente en este momento para evitar que una nueva búsqueda
  // sobreescriba _datosCliente antes de que este listener complete
  var datosClienteSnapshot = Object.assign({}, _datosCliente);
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      _ocultarLoadingPanel();
      var el = document.getElementById("estado-investigacion");
      el.textContent = t("status.completado"); el.className = "estado-msg";
      renderizarReporteCompliance(data.resultado, datosClienteSnapshot);
      _unsubCompliance = null;
      unsub();
    } else if (data.status === "ERROR") {
      _ocultarLoadingPanel();
      var errEl = document.getElementById("estado-investigacion");
      errEl.textContent = t("status.error") + " " + data.error; errEl.className = "estado-msg";
      document.getElementById("placeholder-msg").style.display = "flex";
      _unsubCompliance = null;
      unsub();
    }
  });
  _unsubCompliance = unsub;
}

function escucharResultadoMercados(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      document.getElementById("estado-mercados").textContent = "Análisis completado.";
      if (window._renderMercados) window._renderMercados(data.resultado);
      else { var pre = document.getElementById("resultado-json"); if (pre) { pre.style.display = "block"; pre.textContent = JSON.stringify(data.resultado, null, 2); } }
      unsub();
    } else if (data.status === "ERROR") {
      document.getElementById("estado-mercados").textContent = "Error: " + data.error; unsub();
    } else {
      var em = document.getElementById("estado-mercados");
      if (em && !em.querySelector(".ahc-spinner")) em.innerHTML = '<span class="ahc-spinner"></span>' + (em.textContent || "Procesando...");
    }
  });
}

function escucharResultadoContratos(tareaId, modo) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      var el = document.getElementById("estado-contratos");
      el.textContent = "Análisis completado."; el.className = "estado-msg";
      if (modo === "comparativo") {
        renderizarReporteComparativo(data.resultado);
      } else {
        renderizarReporteContrato(data.resultado);
      }
      unsub();
    } else if (data.status === "ERROR") {
      document.getElementById("estado-contratos").textContent = "Error: " + data.error; unsub();
    } else {
      var ec = document.getElementById("estado-contratos");
      if (ec && !ec.querySelector(".ahc-spinner")) ec.innerHTML = '<span class="ahc-spinner"></span>' + (ec.textContent || "Procesando...");
    }
  });
}

// ── FORENSE ──────────────────────────────────────────────────────────────────

async function enviarAnalisisForensic(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!verificarCreditos("forensic")) return;

  var estado = document.getElementById("estado-forensic");
  if (!_forenseSeleccionado) {
    estado.style.color = "#b02020";
    estado.textContent = "Debe adjuntar un documento antes de continuar.";
    return;
  }

  estado.style.color = "";
  estado.className   = "estado-msg activo";
  estado.textContent = "Subiendo documento...";

  var datos = {
    tipo:      "forensic",
    status:    "PENDIENTE",
    uid:       user.uid,
    creado_en: firebase.firestore.FieldValue.serverTimestamp(),
  };

  var ref = await db.collection("tareas_pendientes").add(datos);
  _tareaActivaId = ref.id;

  try {
    var info = await subirArchivo(user, ref.id, _forenseSeleccionado, "documentos_forense");
    if (info) await ref.update({ archivo_storage_path: info.path, archivo_nombre: info.nombre, archivo_tipo: info.tipo });
    estado.textContent = "Documento subido. Analizando capas forenses...";
  } catch(e) {
    console.warn("[STORAGE]", e);
    estado.textContent = "Analizando...";
  }

  document.getElementById("reporte-container").style.display = "none";
  document.getElementById("placeholder-msg").style.display   = "flex";
  escucharResultadoForensic(ref.id);
}

function escucharResultadoForensic(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      var el = document.getElementById("estado-forensic");
      el.textContent = "Análisis completado."; el.className = "estado-msg";
      renderizarReporteForensic(data.resultado);
      unsub();
    } else if (data.status === "ERROR") {
      document.getElementById("estado-forensic").textContent = "Error: " + data.error;
      unsub();
    }
  });
}

function renderizarReporteForensic(f) {
  var container = document.getElementById("reporte-container");
  if (!container || !f) return;

  var esMock = f._modo === "SIMULADO";
  var ahora  = new Date().toLocaleString("es-UY", { dateStyle: "long", timeStyle: "short" });
  var archivo = (_forenseSeleccionado && _forenseSeleccionado.name) || "Documento";

  document.getElementById("r-archivo-nombre").innerHTML =
    archivo + (esMock ? ' <span class="mock-badge">SIMULADO</span>' : "");
  document.getElementById("r-fecha").textContent = ahora;

  var autent = f.documento_autentico;
  var score  = parseFloat(f.score_confianza_antifraude) || 0;
  var color  = score >= 80 ? "#1a6e3a" : score >= 50 ? "#8a6000" : "#b02020";

  if (autent === true)
    document.getElementById("r-forense-verdict").innerHTML = '<div class="forense-verdict forense-autentico">✓ Documento Auténtico</div>';
  else if (autent === false)
    document.getElementById("r-forense-verdict").innerHTML = '<div class="forense-verdict forense-alterado">⚠ Posible Alteración Detectada</div>';
  else
    document.getElementById("r-forense-verdict").innerHTML = '<div class="forense-verdict forense-pendiente">— Veredicto Pendiente</div>';

  document.getElementById("r-score-fill").style.width      = score + "%";
  document.getElementById("r-score-fill").style.background = color;
  document.getElementById("r-score-val").style.color       = color;
  document.getElementById("r-score-val").textContent       = score.toFixed(1) + " / 100";

  var meta   = f.metadata_local || {};
  document.getElementById("r-forense-meta").innerHTML =
    '<div class="meta-item"><strong>Software / Creador</strong>' + (meta.creador_detectado || "—") + '</div>'
    + '<div class="meta-item"><strong>Fecha de Creación</strong>' + (meta.fecha_creacion || "—") + '</div>'
    + '<div class="meta-item"><strong>Fecha de Modificación</strong>' + (meta.fecha_modificacion || "—") + '</div>'
    + '<div class="meta-item"><strong>Señales Locales</strong>' + ((meta.señales_sospechosas || []).length || "0") + ' detectadas</div>';

  var anom = f.anomalias_detectadas || [];
  document.getElementById("r-forense-anomalias").innerHTML = anom.length === 0
    ? '<div class="anomalia-row"><div class="dot ok"></div><span>Sin anomalías detectadas.</span></div>'
    : anom.map(function(a) {
        var ok = a.toLowerCase().indexOf("sin anomal") >= 0;
        return '<div class="anomalia-row"><div class="dot ' + (ok ? "ok" : "") + '"></div><span>' + a + '</span></div>';
      }).join("");

  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

function exportarPDFForensic() {
  var archivo  = document.getElementById("r-archivo-nombre").innerText.replace(/SIMULADO/g,"").trim();
  var fecha    = document.getElementById("r-fecha").textContent;
  var verdict  = document.getElementById("r-forense-verdict").innerHTML;
  var scoreTxt = document.getElementById("r-score-val").textContent;
  var scorePct = document.getElementById("r-score-fill").style.width;
  var scoreCl  = document.getElementById("r-score-fill").style.background;
  var metaHTML = document.getElementById("r-forense-meta").innerHTML;
  var anomHTML = document.getElementById("r-forense-anomalias").innerHTML;

  _abrirVentanaPDF(
    "Análisis Forense Documental — 4 Capas", archivo, "Forense", fecha, verdict,
    "<div class='grid full'><div class='sec'>"
    + "<div class='sec-titulo'>Score de Confianza Antifraude</div>"
    + "<div style='display:flex;align-items:center;gap:12px;margin-top:8px'>"
    + "<div style='flex:1;height:10px;background:#eee;border-radius:4px;overflow:hidden'>"
    + "<div style='height:100%;width:" + scorePct + ";background:" + scoreCl + ";border-radius:4px'></div></div>"
    + "<span style='font-weight:800;font-size:1rem;color:" + scoreCl + "'>" + scoreTxt + "</span></div>"
    + "</div></div>"
    + "<div class='grid' style='margin-top:14px'>"
    + "<div class='sec'><div class='sec-titulo'>Metadatos del Documento</div>" + metaHTML + "</div>"
    + "<div class='sec'><div class='sec-titulo'>Anomalías Detectadas</div>" + anomHTML + "</div></div>"
  );
}

// ── RENDER COMPLIANCE ────────────────────────────────────────────────────────

function renderizarReporteCompliance(r, cliente) {
  var container = document.getElementById("reporte-container");
  if (!container) return;

  var esMock = !!r._modo;
  var locale = _lang === "en" ? "en-US" : "es-UY";
  var ahora  = new Date().toLocaleString(locale, { dateStyle: "long", timeStyle: "short" });

  document.getElementById("r-nombre").innerHTML =
    escHtml(r.nombre_investigado || cliente.nombre || "—") +
    (esMock ? '<span class="mock-badge">SIMULADO</span>' : "");
  document.getElementById("r-documento").textContent = r.documento || cliente.documento || "—";
  document.getElementById("r-fecha").textContent = ahora;

  var tipoEntidad = r.tipo_entidad || cliente.tipo_entidad || "persona";
  var badgeMap = {
    APROBADO:    ["badge-aprobado",  t("badge.aprobado")],
    ALERTA_RIESGO: ["badge-alerta", t("badge.alerta")],
    BLOQUEADO:   ["badge-bloqueado", t("badge.bloqueado")]
  };
  var bd = badgeMap[r.status_evaluacion] || ["badge-alerta", r.status_evaluacion];
  document.getElementById("r-badge").innerHTML = '<span class="badge ' + bd[0] + '">' + escHtml(bd[1]) + '</span>';

  var docLabelEl = document.getElementById("r-doc-label");
  if (docLabelEl) docLabelEl.textContent = tipoEntidad === "empresa" ? t("doc.label.empresa") : tipoEntidad === "inmueble" ? t("doc.label.inmueble") : t("r.doc.label");
  var entidadesTituloEl = document.getElementById("r-entidades-titulo");
  if (entidadesTituloEl) entidadesTituloEl.textContent = t("r.entidades." + tipoEntidad) || t("r.entidades.persona");

  document.getElementById("r-resumen").textContent = r.resumen_ejecutivo || "—";

  var empEl = document.getElementById("r-empresas");
  if (r.empresas_vinculadas && r.empresas_vinculadas.length) {
    empEl.innerHTML = r.empresas_vinculadas.map(function(e){
      return '<div class="empresa-card"><div class="empresa-nombre">' + escHtml(e.nombre_empresa) + '</div>'
        + '<div class="empresa-pais">' + escHtml(e.pais) + '</div>'
        + '<div class="empresa-socios"><strong>' + escHtml((e.socios_detectados||[]).join(", ")) + '</strong></div></div>';
    }).join("");
  } else { empEl.innerHTML = '<p style="color:#555;font-size:0.9rem">' + t("no.entidades") + '</p>'; }

  var alertEl = document.getElementById("r-alertas");
  if (r.alertas_ofac_crimen && r.alertas_ofac_crimen.length) {
    alertEl.innerHTML = r.alertas_ofac_crimen.map(function(a){
      var ok = a.toLowerCase().indexOf("ninguna") >= 0 || a.toLowerCase().indexOf("descartado") >= 0 || a.toLowerCase().indexOf("none") >= 0;
      return '<div class="alerta-row"><div class="dot ' + (ok?"ok":"") + '"></div><span>' + escHtml(a) + '</span></div>';
    }).join("");
  } else { alertEl.innerHTML = '<div class="alerta-row"><div class="dot ok"></div><span>' + t("no.alertas") + '</span></div>'; }

  var fuentesEl = document.getElementById("r-fuentes");
  if (r.fuentes && r.fuentes.length) {
    fuentesEl.innerHTML = r.fuentes.map(function(f){ return '<a class="url-link" href="' + escHtml(safeUrl(f.url)) + '" target="_blank" rel="noopener">' + escHtml(f.titulo||f.url) + '</a>'; }).join("");
  } else if (esMock) {
    fuentesEl.innerHTML =
      '<a class="url-link" href="https://www.ofac.treas.gov/SDN-List" target="_blank" rel="noopener">OFAC SDN List — U.S. Treasury</a>'
      + '<a class="url-link" href="https://www.un.org/securitycouncil/sanctions/information" target="_blank" rel="noopener">UN Security Council — Sanctions</a>'
      + '<a class="url-link" href="https://www.fatf-gafi.org/en/countries.html" target="_blank" rel="noopener">FATF/GAFI — High-risk countries</a>'
      + '<p class="url-nota">' + (_lang === "en" ? "Real URLs will appear when Gemini API is active." : "Las URLs reales aparecerán cuando Gemini API esté activo.") + '</p>';
  } else { fuentesEl.innerHTML = '<p style="color:#555;font-size:0.9rem">' + t("no.fuentes") + '</p>'; }

  var paisesEl = document.getElementById("r-paises");
  if (r.paises_rastreados_efectivos && r.paises_rastreados_efectivos.length) {
    paisesEl.innerHTML = r.paises_rastreados_efectivos.map(function(p){ return '<span class="pais-tag">' + escHtml(p) + '</span>'; }).join("");
  } else { paisesEl.innerHTML = '<p style="color:#555;font-size:0.9rem">—</p>'; }

  renderizarForense(r.analisis_forense_documental);

  if (r.conclusion_asesor) document.getElementById("r-conclusion").value = r.conclusion_asesor;

  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

function renderizarForense(f) {
  var seccion = document.getElementById("seccion-forense");
  if (!f || !seccion) return;
  seccion.style.display = "block";

  var verdictEl = document.getElementById("r-forense-verdict");
  if (f.documento_autentico === true)       verdictEl.innerHTML = '<div class="forense-verdict forense-autentico">' + t("forense.autentico") + '</div>';
  else if (f.documento_autentico === false) verdictEl.innerHTML = '<div class="forense-verdict forense-alterado">'  + t("forense.alterado")  + '</div>';
  else                                      verdictEl.innerHTML = '<div class="forense-verdict forense-pendiente">' + t("forense.pendiente") + '</div>';

  var score   = parseFloat(f.score_confianza_antifraude) || 0;
  var color   = score >= 80 ? "#1a6e3a" : score >= 50 ? "#8a6000" : "#b02020";
  var fillEl  = document.getElementById("r-score-fill");
  var scoreEl = document.getElementById("r-score-val");
  fillEl.style.width = score + "%"; fillEl.style.background = color;
  scoreEl.style.color = color; scoreEl.textContent = score.toFixed(1) + " / 100";

  var meta   = f.metadata_local || {};
  var metaEl = document.getElementById("r-forense-meta");
  metaEl.innerHTML =
    '<div class="meta-item"><strong>Software / Creador</strong>' + escHtml(meta.creador_detectado||"—") + '</div>'
    + '<div class="meta-item"><strong>Fecha de Creación</strong>' + escHtml(meta.fecha_creacion||"—") + '</div>'
    + '<div class="meta-item"><strong>Fecha de Modificación</strong>' + escHtml(meta.fecha_modificacion||"—") + '</div>'
    + '<div class="meta-item"><strong>Señales Locales</strong>' + escHtml((meta.señales_sospechosas||[]).length||"0") + ' detectadas</div>';

  var anomEl = document.getElementById("r-forense-anomalias");
  var anom   = f.anomalias_detectadas || [];
  anomEl.innerHTML = anom.length === 0
    ? '<div class="anomalia-row"><div class="dot ok"></div><span>Sin anomalías detectadas.</span></div>'
    : anom.map(function(a){
        var ok = a.toLowerCase().indexOf("sin anomal") >= 0;
        return '<div class="anomalia-row"><div class="dot ' + (ok?"ok":"") + '"></div><span>' + escHtml(a) + '</span></div>';
      }).join("");
}

// ── RENDER CONTRATOS ─────────────────────────────────────────────────────────

function renderizarReporteContrato(r) {
  var container = document.getElementById("reporte-container");
  if (!container) return;

  var esMock = !!r._modo;
  var ahora  = new Date().toLocaleString("es-UY", { dateStyle: "long", timeStyle: "short" });

  document.getElementById("r-tipo-contrato").innerHTML =
    escHtml(r.tipo_contrato || "Contrato") + (esMock ? '<span class="mock-badge">SIMULADO</span>' : "");
  document.getElementById("r-fecha").textContent = ahora;

  var partes = r.partes_detectadas || [];
  document.getElementById("r-partes-count").textContent = partes.length + " parte(s) identificada(s)";

  var recMap = {
    "FIRMAR":        ["badge-rec badge-firmar",    "✓ APTO PARA FIRMAR"],
    "REVISAR_ANTES": ["badge-rec badge-revisar",   "⚠ REVISAR ANTES DE FIRMAR"],
    "NO_FIRMAR":     ["badge-rec badge-no-firmar", "✕ NO FIRMAR — RIESGO ALTO"],
  };
  var rec = recMap[r.recomendacion_general] || ["badge-rec badge-revisar", r.recomendacion_general];
  document.getElementById("r-rec-badge").innerHTML = '<span class="' + rec[0] + '">' + escHtml(rec[1]) + '</span>';

  document.getElementById("r-resumen").textContent = r.resumen_ejecutivo || "—";

  var partesEl = document.getElementById("r-partes");
  if (partes.length) {
    partesEl.innerHTML = partes.map(function(p){
      return '<div class="parte-row"><span class="parte-nombre">' + escHtml(p.nombre) + '</span>'
        + '<span class="parte-rol">' + escHtml(p.rol) + '</span></div>';
    }).join("");
  } else { partesEl.innerHTML = '<p style="color:#555;font-size:0.9rem">No se detectaron partes.</p>'; }

  var clausulasEl = document.getElementById("r-clausulas");
  var clas = r.clausulas_problematicas || [];
  if (clas.length) {
    clausulasEl.innerHTML = clas.map(function(c){
      var sevClass = c.severidad === "ALTA" ? "sev-alta" : c.severidad === "MEDIA" ? "sev-media" : "sev-baja";
      return '<div class="clausula-card">'
        + '<div class="clausula-header">'
        + '<div class="clausula-nombre">' + escHtml(c.clausula) + '</div>'
        + '<span class="sev-badge ' + sevClass + '">' + escHtml(c.severidad) + '</span>'
        + '</div>'
        + (c.texto_detectado ? '<div class="clausula-texto">&ldquo;' + escHtml(c.texto_detectado) + '&rdquo;</div>' : '')
        + '<div class="clausula-riesgo">' + escHtml(c.riesgo) + '</div>'
        + '</div>';
    }).join("");
  } else { clausulasEl.innerHTML = '<p style="color:#555;font-size:0.9rem">No se detectaron cláusulas problemáticas.</p>'; }

  var vaciosEl = document.getElementById("r-vacios");
  var vacios = r.vacios_legales || [];
  vaciosEl.innerHTML = vacios.length
    ? vacios.map(function(v){ return '<div class="item-row"><div class="item-dot dot-amber"></div><span>' + escHtml(v) + '</span></div>'; }).join("")
    : '<div class="item-row"><div class="item-dot dot-green"></div><span>Sin vacíos legales detectados.</span></div>';

  var riesgosEl = document.getElementById("r-riesgos");
  var riesgos = r.riesgos_comerciales || [];
  riesgosEl.innerHTML = riesgos.length
    ? riesgos.map(function(r){ return '<div class="item-row"><div class="item-dot dot-red"></div><span>' + escHtml(r) + '</span></div>'; }).join("")
    : '<div class="item-row"><div class="item-dot dot-green"></div><span>Sin riesgos comerciales identificados.</span></div>';

  var favorEl = document.getElementById("r-favorables");
  var favor = r.clausulas_favorables || [];
  favorEl.innerHTML = favor.length
    ? favor.map(function(f){ return '<div class="item-row"><div class="item-dot dot-green"></div><span>' + escHtml(f) + '</span></div>'; }).join("")
    : '<div class="item-row"><div class="item-dot dot-accent"></div><span>No se detectaron cláusulas explícitamente favorables.</span></div>';

  if (r.notas_asesor) document.getElementById("r-notas-asesor").value = r.notas_asesor;

  document.getElementById("reporte-individual").style.display  = "block";
  document.getElementById("reporte-comparativo").style.display = "none";
  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

function renderizarReporteComparativo(r) {
  var container = document.getElementById("reporte-container");
  if (!container) return;

  var esMock = !!(r && r._modo);
  var ahora  = new Date().toLocaleString("es-UY", { dateStyle: "long", timeStyle: "short" });

  document.getElementById("r-tipo-contrato").innerHTML =
    "Análisis Comparativo de Contrato" + (esMock ? '<span class="mock-badge">SIMULADO</span>' : "");
  document.getElementById("r-fecha").textContent = ahora;
  document.getElementById("r-partes-count").textContent = "";

  var recMap = {
    "ACEPTAR":  ["badge-rec badge-aceptar",  "✓ ACEPTAR — SIN CAMBIOS CRÍTICOS"],
    "NEGOCIAR": ["badge-rec badge-negociar", "⚠ NEGOCIAR ANTES DE FIRMAR"],
    "RECHAZAR": ["badge-rec badge-rechazar", "✕ RECHAZAR — CAMBIOS GRAVES"],
  };
  var rec = recMap[r.recomendacion] || ["badge-rec badge-negociar", r.recomendacion || "—"];
  document.getElementById("r-rec-badge").innerHTML = '<span class="' + rec[0] + '">' + escHtml(rec[1]) + '</span>';

  document.getElementById("rc-resumen").textContent = r.resumen_cambios || "—";

  var impactoClass = function(imp) {
    if (!imp) return "impacto-neu";
    var i = imp.toUpperCase();
    return i === "FAVORABLE" ? "impacto-fav" : i === "DESFAVORABLE" ? "impacto-des" : "impacto-neu";
  };

  var modEl = document.getElementById("rc-modificadas");
  var mods  = r.clausulas_modificadas || [];
  if (mods.length) {
    modEl.innerHTML = mods.map(function(c) {
      return '<div class="diff-card">'
        + '<div class="diff-header">'
        + '<div class="diff-id">' + escHtml(c.clausula) + '</div>'
        + '<span class="impacto-badge ' + impactoClass(c.impacto) + '">' + escHtml(c.impacto || "NEUTRAL") + '</span>'
        + '</div>'
        + '<div class="diff-blocks">'
        + '<div class="diff-original"><div class="diff-block-label">Original</div>' + escHtml(c.texto_original || "—") + '</div>'
        + '<div class="diff-nuevo"><div class="diff-block-label">Modificado</div>' + escHtml(c.texto_nuevo || "—") + '</div>'
        + '</div>'
        + (c.descripcion ? '<div class="diff-desc">' + escHtml(c.descripcion) + '</div>' : '')
        + '</div>';
    }).join("");
  } else { modEl.innerHTML = '<p style="color:#555;font-size:0.9rem">No se detectaron cláusulas modificadas.</p>'; }

  var agrEl = document.getElementById("rc-agregadas");
  var agr   = r.clausulas_agregadas || [];
  if (agr.length) {
    agrEl.innerHTML = agr.map(function(c) {
      return '<div class="clausula-card">'
        + '<div class="clausula-header">'
        + '<div class="clausula-nombre">' + escHtml(c.clausula) + '</div>'
        + '<span class="impacto-badge ' + impactoClass(c.impacto) + '">' + escHtml(c.impacto || "NEUTRAL") + '</span>'
        + '</div>'
        + (c.texto ? '<div class="clausula-texto">&ldquo;' + escHtml(c.texto) + '&rdquo;</div>' : '')
        + '</div>';
    }).join("");
  } else { agrEl.innerHTML = '<div class="item-row"><div class="item-dot dot-green"></div><span>No se agregaron nuevas cláusulas.</span></div>'; }

  var elimEl = document.getElementById("rc-eliminadas");
  var elim   = r.clausulas_eliminadas || [];
  if (elim.length) {
    elimEl.innerHTML = elim.map(function(c) {
      return '<div class="clausula-card">'
        + '<div class="clausula-header">'
        + '<div class="clausula-nombre">' + escHtml(c.clausula) + '</div>'
        + '<span class="impacto-badge ' + impactoClass(c.impacto) + '">' + escHtml(c.impacto || "NEUTRAL") + '</span>'
        + '</div>'
        + (c.texto ? '<div class="clausula-texto">&ldquo;' + escHtml(c.texto) + '&rdquo;</div>' : '')
        + '</div>';
    }).join("");
  } else { elimEl.innerHTML = '<div class="item-row"><div class="item-dot dot-green"></div><span>No se eliminaron cláusulas.</span></div>'; }

  if (r.notas_asesor) document.getElementById("r-notas-asesor").value = r.notas_asesor;

  document.getElementById("reporte-individual").style.display  = "none";
  document.getElementById("reporte-comparativo").style.display = "block";
  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

// ── GUARDAR ──────────────────────────────────────────────────────────────────

async function guardarConclusion() {
  var btn   = document.querySelector(".btn-guardar");
  var texto = document.getElementById("r-conclusion").value.trim();
  if (!_tareaActivaId || !texto) return;
  btn.textContent = "Guardando..."; btn.disabled = true;
  await db.collection("tareas_pendientes").doc(_tareaActivaId).update({
    "resultado.conclusion_asesor": texto,
    "conclusion_guardada_en": firebase.firestore.FieldValue.serverTimestamp(),
  });
  btn.textContent = "Guardado";
  setTimeout(function(){ btn.textContent = "Guardar Conclusión"; btn.disabled = false; }, 2500);
}

async function guardarNotasContrato() {
  var btn   = document.querySelector(".btn-guardar");
  var texto = document.getElementById("r-notas-asesor").value.trim();
  if (!_tareaActivaId || !texto) return;
  btn.textContent = "Guardando..."; btn.disabled = true;
  await db.collection("tareas_pendientes").doc(_tareaActivaId).update({
    "resultado.notas_asesor": texto,
    "notas_guardadas_en": firebase.firestore.FieldValue.serverTimestamp(),
  });
  btn.textContent = "Guardado";
  setTimeout(function(){ btn.textContent = "Guardar Notas"; btn.disabled = false; }, 2500);
}

// ── EXPORTAR PDF — COMPLIANCE ────────────────────────────────────────────────

function exportarPDF() {
  var nombre     = (document.getElementById("r-nombre").innerText || "").replace(/SIMULADO/g, "").trim();
  var documento  = document.getElementById("r-documento").textContent;
  var fecha      = document.getElementById("r-fecha").textContent;
  var badge      = document.getElementById("r-badge").innerHTML;
  var resumen    = document.getElementById("r-resumen").textContent;
  var empresas   = document.getElementById("r-empresas").innerHTML;
  var alertas    = document.getElementById("r-alertas").innerHTML;
  var fuentes    = document.getElementById("r-fuentes").innerHTML;
  var paises     = document.getElementById("r-paises").innerHTML;
  var conclusion = document.getElementById("r-conclusion").value || "Sin conclusión registrada.";

  var forenseSeccion = document.getElementById("seccion-forense");
  var forenseHTML = "";
  if (forenseSeccion && forenseSeccion.style.display !== "none") {
    var verdict  = document.getElementById("r-forense-verdict").innerHTML;
    var scoreTxt = document.getElementById("r-score-val").textContent;
    var scorePct = document.getElementById("r-score-fill").style.width;
    var scoreCl  = document.getElementById("r-score-fill").style.background;
    var metaHTML = document.getElementById("r-forense-meta").innerHTML;
    var anomHTML = document.getElementById("r-forense-anomalias").innerHTML;
    forenseHTML = "<div class='sec' style='margin-top:14px;page-break-inside:avoid'>"
      + "<div class='sec-titulo'>Análisis Forense Documental — 4 Capas</div>" + verdict
      + "<div style='display:flex;align-items:center;gap:12px;margin:10px 0'>"
      + "<div style='flex:1;height:8px;background:#eee;border-radius:4px;overflow:hidden'>"
      + "<div style='height:100%;width:" + scorePct + ";background:" + scoreCl + ";border-radius:4px'></div></div>"
      + "<span style='font-weight:700;font-size:9.5pt;color:" + scoreCl + "'>" + scoreTxt + "</span></div>"
      + "<div style='display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px'>"
      + "<div><div class='sec-titulo' style='font-size:7pt'>Metadatos</div><div style='font-size:8.5pt;color:#555'>" + metaHTML + "</div></div>"
      + "<div><div class='sec-titulo' style='font-size:7pt'>Anomalías</div>" + anomHTML + "</div></div></div>";
  }

  _abrirVentanaPDF(
    "Informe de Debida Diligencia — KYC / AML", nombre, documento, fecha, badge,
    "<div class='grid full'><div class='sec'><div class='sec-titulo'>Resumen Ejecutivo</div><p>" + escHtml(resumen) + "</p></div></div>"
    + "<div class='grid' style='margin-top:14px'>"
    + "<div class='sec'><div class='sec-titulo'>Entidades Vinculadas</div>" + empresas + "</div>"
    + "<div class='sec'><div class='sec-titulo'>OFAC / Sanciones</div>" + alertas + "</div></div>"
    + "<div class='grid' style='margin-top:14px'>"
    + "<div class='sec'><div class='sec-titulo'>Fuentes</div>" + fuentes + "</div>"
    + "<div class='sec'><div class='sec-titulo'>Jurisdicciones</div>" + paises + "</div></div>"
    + forenseHTML
    + "<div class='concl'><div class='sec-titulo'>Conclusión del Asesor</div><div class='concl-text'>" + escHtml(conclusion) + "</div></div>"
  );
}

// ── EXPORTAR PDF — CONTRATOS ─────────────────────────────────────────────────

function exportarPDFContrato() {
  var tipo       = (document.getElementById("r-tipo-contrato").innerText || "").replace(/SIMULADO/g,"").trim();
  var fecha      = document.getElementById("r-fecha").textContent;
  var recBadge   = document.getElementById("r-rec-badge").innerHTML;
  var resumen    = document.getElementById("r-resumen").textContent;
  var partes     = document.getElementById("r-partes").innerHTML;
  var clausulas  = document.getElementById("r-clausulas").innerHTML;
  var vacios     = document.getElementById("r-vacios").innerHTML;
  var riesgos    = document.getElementById("r-riesgos").innerHTML;
  var favorables = document.getElementById("r-favorables").innerHTML;
  var notas      = document.getElementById("r-notas-asesor").value || "Sin notas registradas.";

  _abrirVentanaPDF(
    "Auditoría Legal Inteligente — Análisis de Contrato", tipo, "Análisis contrato", fecha, recBadge,
    "<div class='grid full'><div class='sec'><div class='sec-titulo'>Resumen Ejecutivo</div><p>" + escHtml(resumen) + "</p></div></div>"
    + "<div class='grid' style='margin-top:14px'>"
    + "<div class='sec'><div class='sec-titulo'>Partes del Contrato</div>" + partes + "</div>"
    + "<div class='sec'><div class='sec-titulo'>Vacíos Legales</div>" + vacios + "</div></div>"
    + "<div class='grid full' style='margin-top:14px'><div class='sec'><div class='sec-titulo'>Cláusulas Problemáticas</div>" + clausulas + "</div></div>"
    + "<div class='grid' style='margin-top:14px'>"
    + "<div class='sec'><div class='sec-titulo'>Riesgos Comerciales</div>" + riesgos + "</div>"
    + "<div class='sec'><div class='sec-titulo'>Cláusulas Favorables</div>" + favorables + "</div></div>"
    + "<div class='concl'><div class='sec-titulo'>Notas del Asesor</div><div class='concl-text'>" + escHtml(notas) + "</div></div>"
  );
}

function _abrirVentanaPDF(subtitulo, nombre, docNum, fecha, badgeHtml, bodyHtml) {
  var pw = window.open("", "_blank", "width=900,height=700");
  pw.document.open();
  pw.document.write("<!DOCTYPE html><html><head><meta charset='UTF-8'>"
    + "<title>" + escHtml(nombre) + "</title><style>"
    + "@page{margin:18mm 16mm;size:A4}*{box-sizing:border-box;margin:0;padding:0}"
    + "body{font-family:'Segoe UI',sans-serif;color:#111;background:#fff;font-size:10.5pt}"
    + ".header{border-bottom:2px solid #222;padding-bottom:16px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-start}"
    + ".subtitulo{font-size:7pt;color:#888;text-transform:uppercase;letter-spacing:2px;margin-bottom:4px}"
    + ".nombre{font-size:18pt;font-weight:800;color:#000}"
    + ".meta{font-size:8pt;color:#666;margin-top:6px;line-height:1.8}.meta strong{color:#333}"
    + ".grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;page-break-inside:avoid}"
    + ".full{grid-template-columns:1fr}"
    + ".sec{background:#fafafa;border:1px solid #ddd;border-radius:6px;padding:14px 16px;page-break-inside:avoid}"
    + ".sec-titulo{font-size:7pt;color:#555;text-transform:uppercase;letter-spacing:2px;margin-bottom:10px;border-bottom:1px solid #e0e0e0;padding-bottom:5px}"
    + ".sec p{font-size:9.5pt;color:#333;line-height:1.6}"
    + ".empresa-card,.clausula-card{background:#fff;border:1px solid #e0e0e0;border-left:3px solid #1a56a0;border-radius:4px;padding:10px 12px;margin-bottom:8px}"
    + ".empresa-nombre,.clausula-nombre{font-weight:700;color:#000;font-size:9.5pt}"
    + ".empresa-pais{font-size:8pt;color:#888;margin-top:2px}"
    + ".empresa-socios{font-size:8.5pt;color:#555;margin-top:5px}.empresa-socios strong{color:#333}"
    + ".clausula-header{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px}"
    + ".sev-badge{padding:2px 8px;border-radius:3px;font-size:7pt;font-weight:700;letter-spacing:1px;white-space:nowrap}"
    + ".sev-alta{background:#fde8e8;color:#b02020}.sev-media{background:#fff3cc;color:#8a6000}.sev-baja{background:#d4f0e0;color:#1a6e3a}"
    + ".clausula-texto{font-size:7.5pt;color:#777;font-style:italic;border-left:3px solid #ddd;padding-left:8px;margin-bottom:6px}"
    + ".clausula-riesgo{font-size:8.5pt;color:#333}"
    + ".parte-row{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid #eee;align-items:center}"
    + ".parte-row:last-child{border-bottom:none}.parte-nombre{font-weight:600;font-size:9pt;flex:1}.parte-rol{font-size:7.5pt;color:#888;background:#f0f0f0;padding:2px 8px;border-radius:3px}"
    + ".alerta-row,.item-row,.anomalia-row{display:flex;align-items:flex-start;gap:10px;padding:7px 0;border-bottom:1px solid #eee}"
    + ".alerta-row:last-child,.item-row:last-child,.anomalia-row:last-child{border-bottom:none}"
    + ".alerta-row span,.item-row span,.anomalia-row span{font-size:9.5pt;color:#333;line-height:1.5}"
    + ".dot,.item-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:4px}"
    + ".dot{background:#e0a000}.dot.ok{background:#2a7a2a}"
    + ".dot-red{background:#b02020}.dot-amber{background:#8a6000}.dot-green{background:#1a6e3a}.dot-accent{background:#1a56a0}"
    + ".url-link{display:block;padding:6px 10px;border:1px solid #ddd;border-radius:4px;color:#1a56a0;font-size:8pt;text-decoration:none;margin-bottom:6px;word-break:break-all}"
    + ".url-nota{font-size:7.5pt;color:#aaa;margin-top:5px}"
    + ".pais-tag{display:inline-block;background:#eee;border:1px solid #ddd;border-radius:3px;padding:3px 10px;font-size:8pt;color:#555;margin:2px}"
    + ".badge,.badge-rec{display:inline-block;padding:5px 14px;border-radius:4px;font-size:8pt;font-weight:700}"
    + ".badge-aprobado{background:#d4f0e0;color:#1a6e3a;border-left:3px solid #1a6e3a}"
    + ".badge-alerta{background:#fff3cc;color:#8a6000;border-left:3px solid #8a6000}"
    + ".badge-bloqueado{background:#fde8e8;color:#b02020;border-left:3px solid #b02020}"
    + ".badge-firmar{background:#d4f0e0;color:#1a6e3a;border-left:3px solid #1a6e3a}"
    + ".badge-revisar{background:#fff3cc;color:#8a6000;border-left:3px solid #8a6000}"
    + ".badge-no-firmar{background:#fde8e8;color:#b02020;border-left:3px solid #b02020}"
    + ".forense-verdict,.forense-autentico,.forense-alterado,.forense-pendiente{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;border-radius:4px;font-size:8pt;font-weight:700;margin-bottom:8px}"
    + ".forense-autentico{background:#d4f0e0;color:#1a6e3a;border-left:3px solid #1a6e3a}"
    + ".forense-alterado{background:#fde8e8;color:#b02020;border-left:3px solid #b02020}"
    + ".forense-pendiente{background:#fff3cc;color:#8a6000;border-left:3px solid #8a6000}"
    + ".meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:8pt;color:#555}"
    + ".meta-item strong{color:#333;font-weight:600;display:block;font-size:7pt;text-transform:uppercase;margin-bottom:2px}"
    + ".mock-badge{display:none}"
    + ".concl{background:#fafafa;border:1px solid #ddd;border-radius:6px;padding:14px 16px;margin-top:14px;page-break-inside:avoid}"
    + ".concl-text{font-size:9.5pt;color:#333;line-height:1.7;white-space:pre-wrap;min-height:60px}"
    + ".footer{margin-top:20px;padding-top:8px;border-top:1px solid #ddd;font-size:7.5pt;color:#aaa;display:flex;justify-content:space-between}"
    + "</style></head><body>"
    + "<div class='header'><div>"
    + "<div class='subtitulo'>" + escHtml(subtitulo) + "</div>"
    + "<div class='nombre'>" + escHtml(nombre) + "</div>"
    + "<div class='meta'>Ref: <strong>" + escHtml(docNum) + "</strong> &nbsp;|&nbsp; Generado: <strong>" + escHtml(fecha) + "</strong></div>"
    + "</div><div>" + badgeHtml + "</div></div>"
    + bodyHtml
    + "<div class='footer'><span>AHC Intelligence — Informe Confidencial</span><span>" + escHtml(fecha) + "</span></div>"
    + "</body></html>"
  );
  pw.document.close();
  pw.focus();
  setTimeout(function(){ pw.print(); }, 400);
}

// ── LEGAL CHAT ───────────────────────────────────────────────────────────────

var _chatHistorial      = [];   // { rol: "user"|"assistant", texto: string }[]
var _chatArchivo        = null; // File object
var _chatArchivoPath    = null; // Firebase Storage path (set after upload)
var _chatArchivoNombre  = null;
var _chatProcesando     = false;
var _chatConvId         = null; // Storage path prefix for this conversation

function adjuntarDocChat(file) {
  if (!file) return;
  if (file.size > 25 * 1024 * 1024) { alert("Archivo mayor a 25 MB."); return; }
  if (!verificarArchivoTrial(file, null)) return;
  _chatArchivo = file;
  _chatArchivoPath = null; // will upload on first send

  var dropEl = document.getElementById("drop-zone-chat");
  var docEl  = document.getElementById("doc-activo");
  var nombreEl = document.getElementById("doc-activo-nombre");
  var metaEl   = document.getElementById("doc-activo-meta");
  if (dropEl)  dropEl.style.display  = "none";
  if (docEl)   docEl.style.display   = "block";
  if (nombreEl) nombreEl.textContent = file.name;
  if (metaEl)   metaEl.textContent   = (file.size / (1024*1024)).toFixed(2) + " MB";

  // chip en input
  var chipEl = document.getElementById("doc-chip-input");
  if (chipEl) {
    chipEl.style.display = "inline-flex";
    chipEl.innerHTML = '<span class="doc-chip">📎 ' + escHtml(file.name) + ' <span class="doc-chip-remove" onclick="quitarDocChat()">✕</span></span>';
  }
  document.getElementById("file-input-chat").value = "";
}

function quitarDocChat() {
  _chatArchivo = null;
  _chatArchivoPath = null;
  _chatArchivoNombre = null;
  var dropEl = document.getElementById("drop-zone-chat");
  var docEl  = document.getElementById("doc-activo");
  var chipEl = document.getElementById("doc-chip-input");
  if (dropEl) dropEl.style.display = "block";
  if (docEl)  docEl.style.display  = "none";
  if (chipEl) chipEl.style.display = "none";
}

function nuevaConversacion() {
  _chatHistorial   = [];
  _chatArchivoPath = null;
  _chatConvId      = null;
  quitarDocChat();
  var msgsEl = document.getElementById("chat-messages");
  if (msgsEl) {
    msgsEl.innerHTML =
      '<div class="chat-empty" id="chat-empty">'
      + '<svg width="56" height="56" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>'
      + '<div class="chat-empty-title">Asesor Legal disponible</div>'
      + '<p>Adjuntá un documento y escribí tu consulta.<br>El asesor responde en segundos.</p>'
      + '</div>';
  }
  var inputEl = document.getElementById("chat-input");
  if (inputEl) inputEl.focus();
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

async function enviarMensajeChat() {
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (_chatProcesando) return;
  if (!verificarCreditos("legal_chat")) return;

  var inputEl = document.getElementById("chat-input");
  var mensaje = inputEl ? inputEl.value.trim() : "";
  if (!mensaje) return;

  // Limpiar input
  inputEl.value = "";
  inputEl.style.height = "auto";

  // Quitar pantalla vacía
  var emptyEl = document.getElementById("chat-empty");
  if (emptyEl) emptyEl.remove();

  // Mostrar mensaje del usuario
  _agregarBurbuja("user", mensaje, _chatArchivoNombre && !_chatArchivoPath ? _chatArchivoNombre : null);

  // Mostrar typing
  _chatProcesando = true;
  document.getElementById("btn-enviar-chat").disabled = true;
  var typing = document.getElementById("typing-indicator");
  if (typing) { typing.style.display = "flex"; _scrollChat(); }

  try {
    // Subir documento si es la primera vez que se usa en esta conversación
    if (_chatArchivo && !_chatArchivoPath && storage) {
      if (!_chatConvId) _chatConvId = "conv_" + Date.now();
      var storagePath = "chat_docs/" + user.uid + "/" + _chatConvId + "/" + _chatArchivo.name;
      var storageRef  = storage.ref(storagePath);
      await storageRef.put(_chatArchivo);
      _chatArchivoPath   = storagePath;
      _chatArchivoNombre = _chatArchivo.name;
    }

    // Crear tarea en Firestore
    var datos = {
      tipo:     "legal_chat",
      status:   "PENDIENTE",
      uid:      user.uid,
      mensaje:  mensaje,
      historial: _chatHistorial.slice(), // copia del historial actual
      creado_en: firebase.firestore.FieldValue.serverTimestamp(),
    };
    if (_chatArchivoPath) {
      datos.archivo_storage_path = _chatArchivoPath;
      datos.archivo_nombre       = _chatArchivoNombre;
    }

    var ref = await db.collection("tareas_pendientes").add(datos);

    // Agregar mensaje del usuario al historial local
    _chatHistorial.push({ rol: "user", texto: mensaje });

    // Escuchar respuesta
    _escucharRespuestaChat(ref.id);

  } catch(e) {
    console.error("[CHAT]", e);
    if (typing) typing.style.display = "none";
    _chatProcesando = false;
    document.getElementById("btn-enviar-chat").disabled = false;
    _agregarBurbuja("assistant", "Error al enviar la consulta: " + e.message);
  }
}

function _escucharRespuestaChat(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      var typing = document.getElementById("typing-indicator");
      if (typing) typing.style.display = "none";
      var respuesta = (data.resultado || {}).respuesta || "Sin respuesta.";
      _agregarBurbuja("assistant", respuesta);
      _chatHistorial.push({ rol: "assistant", texto: respuesta });
      _chatProcesando = false;
      document.getElementById("btn-enviar-chat").disabled = false;
      unsub();
    } else if (data.status === "ERROR") {
      var typing = document.getElementById("typing-indicator");
      if (typing) typing.style.display = "none";
      _agregarBurbuja("assistant", "Error del asesor: " + (data.error || "sin detalle"));
      _chatProcesando = false;
      document.getElementById("btn-enviar-chat").disabled = false;
      unsub();
    }
  });
}

function _agregarBurbuja(rol, texto, docNombre) {
  var msgsEl = document.getElementById("chat-messages");
  if (!msgsEl) return;

  var isUser   = rol === "user";
  var avatarTx = isUser ? "TU" : "AHC";
  var docTag   = docNombre
    ? '<div class="msg-doc-tag">📎 ' + docNombre + '</div>'
    : "";

  var div = document.createElement("div");
  div.className = "msg " + rol;
  div.innerHTML =
    '<div class="msg-avatar">' + avatarTx + '</div>'
    + '<div class="bubble">' + docTag + _escaparHTML(texto) + '</div>';

  msgsEl.appendChild(div);
  _scrollChat();
}

function _scrollChat() {
  var msgsEl = document.getElementById("chat-messages");
  if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
}

function _escaparHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// ── MARKET STRATEGY CHAT (02-A) ───────────────────────────────────────────────

var _strategyHistorial  = [];
var _strategyProcesando = false;

function nuevaConversacionStrategy() {
  _strategyHistorial = [];
  var msgsEl = document.getElementById("chat-messages");
  if (msgsEl) {
    msgsEl.innerHTML = _strategyWelcomeBubble();
  }
  var inputEl = document.getElementById("chat-input");
  if (inputEl) { inputEl.value = ""; inputEl.style.height = "auto"; inputEl.focus(); }
}

function _strategyWelcomeBubble() {
  return '<div class="msg assistant">'
    + '<div class="msg-avatar">AHC</div>'
    + '<div class="bubble">'
    + _escaparHTML("Bienvenido al **Configurador de Portafolios — AHC Intelligence**.\n\nPara diseñar la estrategia óptima, necesito tres datos clave:\n\n1. **Capital disponible** (en USD)\n2. **Horizonte de inversión** (ej: 12 meses, 3 años)\n3. **Objetivo de retorno o nivel de riesgo** que el cliente está dispuesto a asumir\n\nPodés darme todo en un mensaje o ir respondiendo de a uno.\n\n*Análisis de referencia — no constituye asesoramiento financiero formal.*")
    + '</div></div>';
}

function autoResizeStrategy(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

async function enviarMensajeStrategy() {
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (_strategyProcesando) return;
  if (!verificarCreditos("market_strategy")) return;

  var inputEl = document.getElementById("chat-input");
  var mensaje = inputEl ? inputEl.value.trim() : "";
  if (!mensaje) return;

  inputEl.value = ""; inputEl.style.height = "auto";
  _agregarBurbujaStrategy("user", mensaje);
  _strategyProcesando = true;
  document.getElementById("btn-enviar-chat").disabled = true;
  var typing = document.getElementById("typing-indicator");
  if (typing) { typing.style.display = "flex"; _scrollStrategyChat(); }

  try {
    var datos = {
      tipo:      "market_strategy",
      status:    "PENDIENTE",
      uid:       user.uid,
      mensaje:   mensaje,
      historial: _strategyHistorial.slice(),
      creado_en: firebase.firestore.FieldValue.serverTimestamp(),
    };
    var ref = await db.collection("tareas_pendientes").add(datos);
    _strategyHistorial.push({ rol: "user", texto: mensaje });
    _escucharRespuestaStrategy(ref.id);
  } catch(e) {
    if (typing) typing.style.display = "none";
    _strategyProcesando = false;
    document.getElementById("btn-enviar-chat").disabled = false;
    _agregarBurbujaStrategy("assistant", "Error al enviar: " + e.message);
  }
}

function _escucharRespuestaStrategy(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    var typing = document.getElementById("typing-indicator");
    if (data.status === "COMPLETADO") {
      if (typing) typing.style.display = "none";
      var resp = (data.resultado || {}).respuesta || "Sin respuesta.";
      _agregarBurbujaStrategy("assistant", resp);
      _strategyHistorial.push({ rol: "assistant", texto: resp });
      _strategyProcesando = false;
      document.getElementById("btn-enviar-chat").disabled = false;
      unsub();
    } else if (data.status === "ERROR") {
      if (typing) typing.style.display = "none";
      _agregarBurbujaStrategy("assistant", "Error: " + (data.error || "sin detalle"));
      _strategyProcesando = false;
      document.getElementById("btn-enviar-chat").disabled = false;
      unsub();
    }
  });
}

function _agregarBurbujaStrategy(rol, texto) {
  var msgsEl = document.getElementById("chat-messages");
  if (!msgsEl) return;
  var div = document.createElement("div");
  div.className = "msg " + rol;
  div.innerHTML = '<div class="msg-avatar">' + (rol === "user" ? "TU" : "AHC") + '</div>'
    + '<div class="bubble">' + _escaparHTML(texto) + '</div>';
  msgsEl.appendChild(div);
  _scrollStrategyChat();
}

function _scrollStrategyChat() {
  var msgsEl = document.getElementById("chat-messages");
  if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
}

// ── MARKET ASSET ANALYSIS (02-B) ──────────────────────────────────────────────

async function enviarAnalisisActivo(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!verificarCreditos("market_asset")) return;

  var consulta = (document.getElementById("consulta-activo") || {}).value || "";
  if (!consulta.trim()) {
    document.getElementById("estado-activo").textContent = "Ingresá una consulta antes de continuar.";
    return;
  }

  var estado = document.getElementById("estado-activo");
  estado.style.color = ""; estado.className = "estado-msg activo";
  estado.textContent = "Consultando datos de mercado en tiempo real...";

  var ref = await db.collection("tareas_pendientes").add({
    tipo:      "market_asset",
    status:    "PENDIENTE",
    uid:       user.uid,
    consulta:  consulta.trim(),
    creado_en: firebase.firestore.FieldValue.serverTimestamp(),
  });
  _tareaActivaId = ref.id;

  document.getElementById("reporte-container").style.display = "none";
  document.getElementById("placeholder-msg").style.display   = "flex";
  escucharResultadoActivo(ref.id);
}

function escucharResultadoActivo(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      document.getElementById("estado-activo").textContent = "Análisis completado.";
      document.getElementById("estado-activo").className = "estado-msg";
      renderizarAnalisisActivo(data.resultado);
      unsub();
    } else if (data.status === "ERROR") {
      document.getElementById("estado-activo").textContent = "Error: " + data.error;
      unsub();
    }
  });
}

function renderizarAnalisisActivo(r) {
  var container = document.getElementById("reporte-container");
  if (!container || !r) return;

  var esMock = !!r._modo;
  var ahora  = new Date().toLocaleString("es-UY", { dateStyle: "long", timeStyle: "short" });

  document.getElementById("r-activo-nombre").innerHTML =
    (r.activo_consultado || "—") + (esMock ? ' <span class="mock-badge">SIMULADO</span>' : "");
  document.getElementById("r-fecha").textContent     = ahora;
  document.getElementById("r-precio-ref").textContent = r.precio_referencia || "—";

  var vDict = {
    COMPRAR: ["verd-comprar", "▲ COMPRAR"],
    ESPERAR: ["verd-esperar", "◆ ESPERAR"],
    VENDER:  ["verd-vender",  "▼ VENDER"],
    NEUTRAL: ["verd-neutral", "● NEUTRAL"],
  };
  var vd = vDict[r.veredicto] || ["verd-esperar", r.veredicto || "—"];
  document.getElementById("r-veredicto-badge").innerHTML = '<span class="veredicto-badge ' + vd[0] + '">' + vd[1] + '</span>';

  var tec = r.contexto_tecnico || {};
  document.getElementById("r-tec-tendencia").textContent   = tec.tendencia || "—";
  document.getElementById("r-tec-soporte").textContent     = tec.soporte_clave || "—";
  document.getElementById("r-tec-resistencia").textContent = tec.resistencia_clave || "—";
  document.getElementById("r-tec-volatilidad").textContent = tec.volatilidad || "—";
  document.getElementById("r-tec-analisis").textContent    = tec.analisis || "—";

  var fund = r.contexto_fundamental || {};
  document.getElementById("r-fund-tasas").textContent  = fund.tasas_interes || "—";
  document.getElementById("r-fund-analisis").textContent = fund.analisis || "—";
  var eventosEl = document.getElementById("r-fund-eventos");
  var eventos = fund.eventos_macro || [];
  eventosEl.innerHTML = eventos.length
    ? eventos.map(function(e) { return '<div class="evento-row">• ' + escHtml(e) + '</div>'; }).join("")
    : '<div class="evento-row" style="color:#a0b4c8">Sin eventos registrados.</div>';

  var mrr = r.matriz_riesgo_retorno || {};
  document.getElementById("r-esc-base").textContent    = mrr.escenario_base || "—";
  document.getElementById("r-esc-alcista").textContent = mrr.escenario_alcista || "—";
  document.getElementById("r-esc-bajista").textContent = mrr.escenario_bajista || "—";
  document.getElementById("r-ratio-rr").textContent    = mrr.ratio_riesgo_retorno || "—";

  document.getElementById("r-conclusion").textContent = r.conclusion || "—";

  var advEl = document.getElementById("r-advertencias");
  var adv = r.advertencias || [];
  advEl.innerHTML = adv.length
    ? adv.map(function(a) { return '<div class="adv-row"><span class="adv-dot">⚠</span>' + escHtml(a) + '</div>'; }).join("")
    : '<div class="adv-row">Sin advertencias específicas.</div>';

  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

// ── MARKET AUDIT (02-C) ───────────────────────────────────────────────────────

async function enviarAuditoriaCartera(event) {
  event.preventDefault();
  var user = auth.currentUser;
  if (!user) { alert("Debes iniciar sesión."); return; }
  if (!verificarCreditos("market_audit")) return;

  var composicion = (document.getElementById("composicion-cartera") || {}).value || "";
  if (!composicion.trim()) {
    document.getElementById("estado-auditoria").textContent = "Describí la composición de la cartera antes de continuar.";
    return;
  }

  var estado = document.getElementById("estado-auditoria");
  estado.style.color = ""; estado.className = "estado-msg activo";
  estado.textContent = "Auditando cartera con datos de mercado actuales...";

  var ref = await db.collection("tareas_pendientes").add({
    tipo:        "market_audit",
    status:      "PENDIENTE",
    uid:         user.uid,
    composicion: composicion.trim(),
    plazo:       (document.getElementById("plazo-cartera") || {}).value || "Mediano plazo (1–3 años)",
    notas:       (document.getElementById("notas-cartera") || {}).value || "",
    creado_en:   firebase.firestore.FieldValue.serverTimestamp(),
  });
  _tareaActivaId = ref.id;

  document.getElementById("reporte-container").style.display = "none";
  document.getElementById("placeholder-msg").style.display   = "flex";
  escucharResultadoAuditoria(ref.id);
}

function escucharResultadoAuditoria(tareaId) {
  var unsub = db.collection("tareas_pendientes").doc(tareaId).onSnapshot(function(doc) {
    var data = doc.data();
    if (!data) return;
    if (data.status === "COMPLETADO") {
      document.getElementById("estado-auditoria").textContent = "Auditoría completada.";
      document.getElementById("estado-auditoria").className = "estado-msg";
      renderizarAuditoriaCartera(data.resultado);
      unsub();
    } else if (data.status === "ERROR") {
      document.getElementById("estado-auditoria").textContent = "Error: " + data.error;
      unsub();
    }
  });
}

function renderizarAuditoriaCartera(r) {
  var container = document.getElementById("reporte-container");
  if (!container || !r) return;

  var esMock = !!r._modo;
  var ahora  = new Date().toLocaleString("es-UY", { dateStyle: "long", timeStyle: "short" });

  document.getElementById("r-fecha").textContent = ahora;
  document.getElementById("r-resumen-ejecutivo").textContent = r.resumen_ejecutivo || "—";

  var score   = parseFloat(r.score_salud_cartera) || 0;
  var color   = score >= 75 ? "#1a6e3a" : score >= 50 ? "#8a6000" : "#b02020";
  var scoreEl = document.getElementById("r-score-val");
  var fillEl  = document.getElementById("r-score-fill");
  if (scoreEl) { scoreEl.textContent = score.toFixed(1); scoreEl.style.color = color; }
  if (fillEl)  { fillEl.style.width = score + "%"; fillEl.style.background = color; }
  var labelEl = document.getElementById("r-score-label");
  if (labelEl) {
    labelEl.textContent = score >= 75 ? "Salud buena" : score >= 50 ? "Requiere optimización" : "Riesgo elevado";
    labelEl.style.color = color;
  }

  var alertasEl = document.getElementById("r-alertas");
  var alertas = r.alertas_desviacion || [];
  if (alertas.length) {
    alertasEl.innerHTML = alertas.map(function(a) {
      var sc = a.severidad === "ALTA" ? "sev-alta" : a.severidad === "MEDIA" ? "sev-media" : "sev-baja";
      return '<div class="alerta-card">'
        + '<div class="alerta-header">'
        + '<span class="alerta-activo">' + a.activo + '</span>'
        + '<span class="sev-badge ' + sc + '">' + a.severidad + '</span>'
        + '</div>'
        + '<div class="alerta-problema">' + (a.problema || "") + '</div>'
        + '<div class="alerta-desc">' + a.descripcion + '</div>'
        + '</div>';
    }).join("");
  } else {
    alertasEl.innerHTML = '<div class="item-ok">✓ Sin alertas de desviación detectadas.</div>';
  }

  var rebalEl = document.getElementById("r-rebalanceo");
  var rebal = r.propuesta_rebalanceo || [];
  if (rebal.length) {
    rebalEl.innerHTML = rebal.map(function(p) {
      var acClass = p.accion === "REDUCIR" ? "acc-reducir" : p.accion === "AUMENTAR" ? "acc-aumentar" : p.accion === "LIQUIDAR" ? "acc-liquidar" : "acc-mantener";
      return '<div class="rebal-row">'
        + '<span class="acc-badge ' + acClass + '">' + p.accion + '</span>'
        + '<div class="rebal-detail">'
        + '<div class="rebal-activo">' + p.activo + ' <span class="rebal-cambio">' + (p.cambio || "") + '</span></div>'
        + '<div class="rebal-razon">' + p.razon + '</div>'
        + '</div></div>';
    }).join("");
  } else {
    rebalEl.innerHTML = '<div class="item-ok">✓ No se requieren acciones de rebalanceo.</div>';
  }

  var compEl = document.getElementById("r-composicion-sugerida");
  var comp = r.composicion_sugerida || [];
  if (comp.length) {
    compEl.innerHTML = comp.map(function(c) {
      return '<div class="comp-row"><span class="comp-activo">' + c.activo + '</span><span class="comp-pct">' + c.porcentaje + '</span></div>';
    }).join("");
  } else { compEl.innerHTML = "—"; }

  document.getElementById("r-conclusion-macro").textContent = r.conclusion_macro || "—";

  if (esMock) {
    var mockBadges = document.querySelectorAll(".mock-badge-audit");
    mockBadges.forEach(function(el) { el.style.display = "inline"; });
  }

  document.getElementById("placeholder-msg").style.display = "none";
  container.style.display = "block";
  container.scrollIntoView({ behavior: "smooth" });
}

// ── FEEDBACK POST-TRIAL ───────────────────────────────────────────────────────

function _mostrarFeedbackModal() {
  if (document.getElementById("fb-overlay")) { mostrarPaywall("expired"); return; }
  _fbEstrellas = 0;
  if (!document.getElementById("fb-styles")) {
    var s = document.createElement("style");
    s.id  = "fb-styles";
    s.textContent =
      "#fb-overlay{position:fixed;inset:0;background:rgba(4,13,24,.78);z-index:9700;display:flex;align-items:center;justify-content:center;padding:20px}"
      + "#fb-modal{background:#fff;border-radius:8px;padding:40px;max-width:480px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.28);font-family:'Segoe UI',system-ui,sans-serif}"
      + ".fb-label{font-size:0.68rem;font-weight:700;color:#1a56a0;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:10px}"
      + ".fb-titulo{font-size:1.2rem;font-weight:700;color:#040d18;margin-bottom:6px}"
      + ".fb-subtitulo{font-size:0.85rem;color:#3a5068;margin-bottom:24px;line-height:1.6}"
      + ".fb-stars{display:flex;gap:8px;margin-bottom:20px;cursor:pointer}"
      + ".fb-star{font-size:2rem;color:#d0d8e4;transition:color .1s;user-select:none}"
      + ".fb-star.on{color:#f5a623}"
      + ".fb-field{margin-bottom:16px}"
      + ".fb-field label{display:block;font-size:0.72rem;font-weight:700;color:#3a5068;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px}"
      + ".fb-field textarea{width:100%;padding:10px 12px;border:1.5px solid #c8d4e0;border-radius:4px;font-size:0.9rem;font-family:inherit;color:#040d18;resize:vertical;min-height:90px;box-sizing:border-box;transition:border-color .15s}"
      + ".fb-field textarea:focus{outline:none;border-color:#1a56a0;box-shadow:0 0 0 3px rgba(26,86,160,.08)}"
      + ".fb-field input{width:100%;padding:10px 12px;border:1.5px solid #c8d4e0;border-radius:4px;font-size:0.9rem;font-family:inherit;color:#040d18;box-sizing:border-box;transition:border-color .15s}"
      + ".fb-field input:focus{outline:none;border-color:#1a56a0;box-shadow:0 0 0 3px rgba(26,86,160,.08)}"
      + ".fb-error{font-size:0.8rem;color:#b02020;margin-bottom:12px;display:none}"
      + ".fb-btns{display:flex;gap:12px;margin-top:8px}"
      + ".fb-btn-p{flex:1;padding:12px;background:#1a56a0;color:#fff;border:none;border-radius:4px;font-size:0.9rem;font-weight:700;cursor:pointer;font-family:inherit;transition:background .15s}"
      + ".fb-btn-p:hover{background:#1464bf}"
      + ".fb-btn-p:disabled{opacity:.55;cursor:not-allowed}"
      + ".fb-btn-s{padding:12px 18px;background:transparent;color:#7a90a4;border:none;border-radius:4px;font-size:0.88rem;cursor:pointer;font-family:inherit}"
      + ".fb-btn-s:hover{color:#3a5068}"
      + "@media(max-width:480px){#fb-modal{padding:28px 20px}}";
    document.head.appendChild(s);
  }
  var overlay = document.createElement("div");
  overlay.id  = "fb-overlay";
  overlay.innerHTML =
    '<div id="fb-modal">'
    + '<div class="fb-label">AHC Intelligence</div>'
    + '<div class="fb-titulo">¿Cómo fue tu experiencia?</div>'
    + '<div class="fb-subtitulo">Tu período de prueba terminó. Antes de ver los planes, nos gustaría saber qué te pareció.</div>'
    + '<div class="fb-stars" id="fb-stars-wrap">'
    +   '<span class="fb-star" data-v="1">★</span>'
    +   '<span class="fb-star" data-v="2">★</span>'
    +   '<span class="fb-star" data-v="3">★</span>'
    +   '<span class="fb-star" data-v="4">★</span>'
    +   '<span class="fb-star" data-v="5">★</span>'
    + '</div>'
    + '<div class="fb-field">'
    +   '<label for="fb-texto">Tu comentario <span style="font-weight:400;text-transform:none;letter-spacing:0">(opcional)</span></label>'
    +   '<textarea id="fb-texto" placeholder="Contanos qué te pareció, qué mejorarías o qué fue lo más útil..."></textarea>'
    + '</div>'
    + '<div class="fb-field">'
    +   '<label for="fb-nombre">Tu nombre o empresa <span style="font-weight:400;text-transform:none;letter-spacing:0">(opcional — se muestra en la web si aprobamos tu reseña)</span></label>'
    +   '<input type="text" id="fb-nombre" placeholder="Ej: Rafael N., Asesor Financiero" />'
    + '</div>'
    + '<div id="fb-error" class="fb-error">Seleccioná al menos una estrella.</div>'
    + '<div class="fb-btns">'
    +   '<button id="fb-submit-btn" class="fb-btn-p" onclick="_enviarFeedback()">Enviar y ver planes →</button>'
    +   '<button class="fb-btn-s" onclick="_saltarFeedback()">Saltar</button>'
    + '</div>'
    + '</div>';
  overlay.addEventListener("click", function(e) {
    if (e.target === overlay) _saltarFeedback();
  });
  document.body.appendChild(overlay);

  // Stars interaction
  var stars = overlay.querySelectorAll(".fb-star");
  stars.forEach(function(star) {
    star.addEventListener("mouseenter", function() {
      var v = parseInt(star.getAttribute("data-v"));
      stars.forEach(function(s) {
        s.classList.toggle("on", parseInt(s.getAttribute("data-v")) <= v);
      });
    });
    star.addEventListener("click", function() {
      _fbEstrellas = parseInt(star.getAttribute("data-v"));
      stars.forEach(function(s) {
        s.classList.toggle("on", parseInt(s.getAttribute("data-v")) <= _fbEstrellas);
      });
    });
  });
  var wrap = overlay.querySelector("#fb-stars-wrap");
  if (wrap) wrap.addEventListener("mouseleave", function() {
    stars.forEach(function(s) {
      s.classList.toggle("on", parseInt(s.getAttribute("data-v")) <= _fbEstrellas);
    });
  });
}

async function _enviarFeedback() {
  if (_fbEstrellas === 0) {
    var errEl = document.getElementById("fb-error");
    if (errEl) errEl.style.display = "block";
    return;
  }
  var btn = document.getElementById("fb-submit-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Enviando..."; }
  var texto  = (document.getElementById("fb-texto")  ? document.getElementById("fb-texto").value  : "").trim();
  var nombre = (document.getElementById("fb-nombre") ? document.getElementById("fb-nombre").value : "").trim();
  var user   = auth.currentUser;
  try {
    await db.collection("feedback").add({
      uid:           user ? user.uid   : "",
      email:         user ? user.email : "",
      nombre_publico: nombre,
      texto:         texto,
      estrellas:     _fbEstrellas,
      aprobado:      false,
      creado_en:     firebase.firestore.FieldValue.serverTimestamp(),
    });
    if (user) localStorage.setItem("ahc_fb_" + user.uid, "1");
  } catch (e) {
    console.warn("[FEEDBACK]", e);
  }
  _cerrarFeedbackModal();
  mostrarPaywall("expired");
}

function _saltarFeedback() {
  _cerrarFeedbackModal();
  mostrarPaywall("expired");
}

function _cerrarFeedbackModal() {
  _feedbackDado = true;
  var el = document.getElementById("fb-overlay");
  if (el) el.remove();
}

// ── TESTIMONIOS (solo index.html) ─────────────────────────────────────────────

function _cargarTestimonios() {
  var grid = document.getElementById("testimonios-grid");
  if (!grid) return;
  db.collection("feedback")
    .where("aprobado", "==", true)
    .orderBy("creado_en", "desc")
    .limit(6)
    .get()
    .then(function(snap) {
      if (snap.empty) {
        var sec = document.getElementById("testimonios-section");
        if (sec) sec.style.display = "none";
        return;
      }
      grid.innerHTML = snap.docs.map(function(doc) {
        var d = doc.data();
        var stars = [1,2,3,4,5].map(function(i) {
          return '<span class="t-star' + (i <= d.estrellas ? " on" : "") + '">★</span>';
        }).join("");
        return '<div class="t-card">'
          + '<div class="t-stars">' + stars + '</div>'
          + (d.texto ? '<div class="t-texto">&ldquo;' + escHtml(d.texto) + '&rdquo;</div>' : '')
          + (d.nombre_publico ? '<div class="t-nombre">— ' + escHtml(d.nombre_publico) + '</div>' : '')
          + '</div>';
      }).join("");
    })
    .catch(function() {
      var sec = document.getElementById("testimonios-section");
      if (sec) sec.style.display = "none";
    });
}

if (document.getElementById("testimonios-grid")) _cargarTestimonios();

// ── AUTH ─────────────────────────────────────────────────────────────────────

// ── Toast de bienvenida post-registro ──────────────────────────────────────

function _mostrarToastBienvenida() {
  if (document.getElementById("ahc-toast")) return;
  if (!document.getElementById("ahc-toast-style")) {
    var s = document.createElement("style");
    s.id  = "ahc-toast-style";
    s.textContent =
      "@keyframes _ahc_in{from{transform:translate(-50%,20px);opacity:0}to{transform:translate(-50%,0);opacity:1}}"
      + "#ahc-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);"
      + "background:#1a6e3a;color:#fff;padding:14px 24px;border-radius:6px;"
      + "font-size:0.88rem;font-weight:600;box-shadow:0 8px 28px rgba(0,0,0,.22);"
      + "z-index:10000;animation:_ahc_in .35s ease;max-width:90vw;text-align:center}";
    document.head.appendChild(s);
  }
  var el = document.createElement("div");
  el.id  = "ahc-toast";
  el.textContent = "¡Listo! Ya tenés tus créditos gratis para empezar. Subí tu primer documento.";
  document.body.appendChild(el);
  setTimeout(function() { if (el.parentNode) el.remove(); }, 5500);
}

// ── Verificación de email (solo usuarios email/contraseña) ─────────────────

function mostrarVerificacionPendiente(user) {
  if (document.getElementById("verify-overlay")) return;
  if (!document.getElementById("verify-styles")) {
    var s = document.createElement("style");
    s.id  = "verify-styles";
    s.textContent =
      "#verify-overlay{position:fixed;inset:0;background:rgba(4,13,24,.78);z-index:9600;display:flex;align-items:center;justify-content:center;padding:20px}"
      + "#verify-modal{background:#fff;border-radius:8px;padding:44px 40px;max-width:440px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.28);text-align:center;font-family:'Segoe UI',system-ui,sans-serif}"
      + ".vy-icon{font-size:2.8rem;margin-bottom:20px;line-height:1}"
      + ".vy-titulo{font-size:1.3rem;font-weight:700;color:#040d18;margin-bottom:12px}"
      + ".vy-txt{font-size:0.88rem;color:#3a5068;line-height:1.7;margin-bottom:8px}"
      + ".vy-email{font-weight:700;color:#1a56a0}"
      + ".vy-btns{display:flex;gap:12px;margin-top:28px;flex-wrap:wrap}"
      + ".vy-btn-p{flex:1;padding:12px;background:#1a56a0;color:#fff;border:none;border-radius:4px;font-size:0.88rem;font-weight:700;cursor:pointer;transition:background .15s;font-family:inherit}"
      + ".vy-btn-p:hover{background:#1464bf}"
      + ".vy-btn-p:disabled{opacity:.55;cursor:not-allowed}"
      + ".vy-btn-s{flex:1;padding:12px;background:transparent;color:#3a5068;border:1.5px solid #c8d4e0;border-radius:4px;font-size:0.88rem;font-weight:600;cursor:pointer;font-family:inherit;transition:border-color .15s}"
      + ".vy-btn-s:hover{border-color:#1a56a0;color:#1a56a0}"
      + ".vy-btn-s:disabled{opacity:.55;cursor:not-allowed}"
      + ".vy-msg{font-size:0.78rem;margin-top:16px;line-height:1.5;min-height:1.2em}"
      + ".vy-logout{font-size:0.78rem;color:#a0b4c8;margin-top:16px;text-decoration:underline;cursor:pointer}"
      + ".vy-logout:hover{color:#3a5068}"
      + "@media(max-width:480px){#verify-modal{padding:32px 20px}.vy-btns{flex-direction:column}}";
    document.head.appendChild(s);
  }
  var email = user.email || "";
  var overlay = document.createElement("div");
  overlay.id  = "verify-overlay";
  overlay.innerHTML =
    '<div id="verify-modal">'
    + '<div class="vy-icon">✉</div>'
    + '<div class="vy-titulo">Verificá tu email para empezar</div>'
    + '<div class="vy-txt">Te enviamos un correo a <span class="vy-email">' + escHtml(email) + '</span>.<br>Hacé click en el enlace y volvé acá para activar tus créditos.</div>'
    + '<div id="vy-status" class="vy-msg" style="color:#7a90a4"></div>'
    + '<div class="vy-btns">'
    +   '<button id="vy-check-btn" class="vy-btn-p" onclick="_checkVerificado()">Ya verifiqué</button>'
    +   '<button id="vy-resend-btn" class="vy-btn-s" onclick="_reenviarVerificacion()">Reenviar correo</button>'
    + '</div>'
    + '<div class="vy-logout" onclick="_cerrarSesionVerificacion()">¿No es tu email? Cerrar sesión</div>'
    + '</div>';
  document.body.appendChild(overlay);
}

async function _checkVerificado() {
  var btn = document.getElementById("vy-check-btn");
  var msg = document.getElementById("vy-status");
  if (btn) { btn.disabled = true; btn.textContent = "Verificando..."; }
  try {
    await auth.currentUser.reload();
    if (auth.currentUser.emailVerified) {
      var el = document.getElementById("verify-overlay");
      if (el) el.remove();
      iniciarEscuchaCreditos(auth.currentUser);
    } else {
      if (msg) { msg.style.color = "#b02020"; msg.textContent = "El email todavía no fue verificado. Revisá tu bandeja (y la carpeta de spam)."; }
      if (btn) { btn.disabled = false; btn.textContent = "Ya verifiqué"; }
    }
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = "Ya verifiqué"; }
  }
}

async function _reenviarVerificacion() {
  var btn = document.getElementById("vy-resend-btn");
  var msg = document.getElementById("vy-status");
  if (btn) btn.disabled = true;
  try {
    await auth.currentUser.sendEmailVerification();
    if (msg) { msg.style.color = "#1a6e3a"; msg.textContent = "✓ Correo reenviado. Revisá tu bandeja de entrada."; }
    if (btn) btn.textContent = "✓ Reenviado";
    setTimeout(function() {
      var b = document.getElementById("vy-resend-btn");
      if (b) { b.disabled = false; b.textContent = "Reenviar correo"; }
    }, 30000);
  } catch (e) {
    if (msg) { msg.style.color = "#b02020"; msg.textContent = "No se pudo reenviar. Esperá un momento e intentá de nuevo."; }
    if (btn) btn.disabled = false;
  }
}

function _cerrarSesionVerificacion() {
  if (_unsubCreditos) { _unsubCreditos(); _unsubCreditos = null; }
  auth.signOut().then(function() {
    var el = document.getElementById("verify-overlay");
    if (el) el.remove();
  });
}

// ── Modal de autenticación ─────────────────────────────────────────────────

var _authModo = "register";

function loginGoogle() {
  abrirModalAuth();
}

function _triggerGoogleSignIn() {
  cerrarModalAuth();
  var provider = new firebase.auth.GoogleAuthProvider();
  auth.signInWithPopup(provider).catch(function(e) {
    console.warn("[AUTH] Google:", e.message);
  });
}

function cerrarModalAuth() {
  var el = document.getElementById("auth-modal-overlay");
  if (el) el.remove();
}

function abrirModalAuth() {
  if (document.getElementById("auth-modal-overlay")) return;
  if (!document.getElementById("auth-modal-styles")) {
    var s = document.createElement("style");
    s.id  = "auth-modal-styles";
    s.textContent =
      "#auth-modal-overlay{position:fixed;inset:0;background:rgba(4,13,24,.72);z-index:9500;display:flex;align-items:center;justify-content:center;padding:20px}"
      + "#auth-modal{background:#fff;border-radius:8px;padding:36px 40px;max-width:420px;width:100%;box-shadow:0 24px 60px rgba(0,0,0,.28);position:relative;font-family:'Segoe UI',system-ui,sans-serif}"
      + ".am-close{position:absolute;top:14px;right:16px;background:none;border:none;cursor:pointer;font-size:1.1rem;color:#a0b4c8;line-height:1;padding:4px}"
      + ".am-close:hover{color:#1a2535}"
      + ".am-label{font-size:0.68rem;font-weight:700;color:#1a56a0;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:10px}"
      + ".am-titulo{font-size:1.28rem;font-weight:700;color:#040d18;margin-bottom:6px;line-height:1.3}"
      + ".am-subtitulo{font-size:0.82rem;color:#3a5068;margin-bottom:24px;line-height:1.5}"
      + ".am-btn-google{width:100%;padding:12px;background:#fff;border:1.5px solid #c8d4e0;border-radius:4px;font-size:0.9rem;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;color:#1a2535;transition:border-color .15s,box-shadow .15s;font-family:inherit}"
      + ".am-btn-google:hover{border-color:#1a56a0;box-shadow:0 0 0 3px rgba(26,86,160,.08)}"
      + ".am-google-icon{width:18px;height:18px;flex-shrink:0}"
      + ".am-sep{display:flex;align-items:center;gap:12px;margin:20px 0}"
      + ".am-sep::before,.am-sep::after{content:'';flex:1;height:1px;background:#e0e8f0}"
      + ".am-sep-txt{font-size:0.72rem;color:#7a90a4;letter-spacing:1px;text-transform:uppercase;flex-shrink:0}"
      + ".am-field{margin-bottom:16px}"
      + ".am-field label{display:block;font-size:0.72rem;font-weight:700;color:#3a5068;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px}"
      + ".am-field input{width:100%;padding:10px 12px;border:1.5px solid #c8d4e0;border-radius:4px;font-size:0.9rem;font-family:inherit;color:#040d18;background:#fff;transition:border-color .15s;box-sizing:border-box}"
      + ".am-field input:focus{outline:none;border-color:#1a56a0;box-shadow:0 0 0 3px rgba(26,86,160,.08)}"
      + ".am-error{font-size:0.8rem;color:#b02020;margin-bottom:12px;display:none;line-height:1.4}"
      + ".am-error.ok{color:#1a6e3a}"
      + ".am-btn-submit{width:100%;padding:12px;background:#1a56a0;color:#fff;border:none;border-radius:4px;font-size:0.9rem;font-weight:700;cursor:pointer;transition:background .15s;font-family:inherit;margin-bottom:16px}"
      + ".am-btn-submit:hover{background:#1464bf}"
      + ".am-btn-submit:disabled{opacity:.55;cursor:not-allowed}"
      + ".am-toggle{text-align:center;font-size:0.82rem;color:#3a5068;margin-bottom:8px}"
      + ".am-toggle a{color:#1a56a0;text-decoration:none;cursor:pointer;font-weight:600}"
      + ".am-toggle a:hover{text-decoration:underline}"
      + ".am-reset{text-align:center;font-size:0.78rem}"
      + ".am-reset a{color:#7a90a4;text-decoration:underline;cursor:pointer}"
      + ".am-reset a:hover{color:#1a56a0}"
      + "@media(max-width:480px){#auth-modal{padding:28px 20px}}";
    document.head.appendChild(s);
  }
  _authModo = "register";
  var overlay = document.createElement("div");
  overlay.id  = "auth-modal-overlay";
  overlay.innerHTML =
    '<div id="auth-modal">'
    + '<button class="am-close" onclick="cerrarModalAuth()">✕</button>'
    + '<div class="am-label">AHC Intelligence</div>'
    + '<div id="am-titulo" class="am-titulo">Registrate gratis y empezá</div>'
    + '<div id="am-subtitulo" class="am-subtitulo">Tus créditos quedan listos al instante · Sin tarjeta</div>'
    + '<button class="am-btn-google" onclick="_triggerGoogleSignIn()">'
    +   '<svg class="am-google-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
    +   '<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>'
    +   '<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>'
    +   '<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>'
    +   '<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>'
    +   '</svg>'
    +   'Continuar con Google'
    + '</button>'
    + '<div class="am-sep"><span class="am-sep-txt">o</span></div>'
    + '<div class="am-field">'
    +   '<label for="auth-email">Email</label>'
    +   '<input type="email" id="auth-email" placeholder="tu@email.com" autocomplete="email" />'
    + '</div>'
    + '<div class="am-field">'
    +   '<label for="auth-pwd">Contraseña</label>'
    +   '<input type="password" id="auth-pwd" placeholder="Mínimo 6 caracteres" autocomplete="new-password" />'
    + '</div>'
    + '<div id="am-error" class="am-error"></div>'
    + '<button id="am-submit-btn" class="am-btn-submit" onclick="_submitEmailAuth()">Crear cuenta</button>'
    + '<div class="am-toggle" id="am-toggle-txt">¿Ya tenés cuenta? <a onclick="_toggleAuthModo()">Iniciá sesión</a></div>'
    + '<div class="am-reset"><a onclick="_resetPassword()">¿Olvidaste tu contraseña?</a></div>'
    + '</div>';
  overlay.addEventListener("click", function(e) {
    if (e.target === overlay) cerrarModalAuth();
  });
  document.body.appendChild(overlay);
  setTimeout(function() {
    var inp = document.getElementById("auth-email");
    if (inp) inp.focus();
    var pwd = document.getElementById("auth-pwd");
    if (pwd) pwd.addEventListener("keydown", function(e) {
      if (e.key === "Enter") _submitEmailAuth();
    });
  }, 120);
}

function _toggleAuthModo() {
  _authModo = _authModo === "register" ? "login" : "register";
  var titulo    = document.getElementById("am-titulo");
  var subtitulo = document.getElementById("am-subtitulo");
  var btn       = document.getElementById("am-submit-btn");
  var toggle    = document.getElementById("am-toggle-txt");
  var pwd       = document.getElementById("auth-pwd");
  var err       = document.getElementById("am-error");
  if (err) { err.style.display = "none"; err.className = "am-error"; }
  if (_authModo === "login") {
    if (titulo)    titulo.textContent    = "Iniciá sesión";
    if (subtitulo) subtitulo.textContent = "Bienvenido de nuevo a AHC Intelligence.";
    if (btn)       btn.textContent       = "Iniciar sesión";
    if (pwd)     { pwd.placeholder = "Tu contraseña"; pwd.autocomplete = "current-password"; }
    if (toggle)    toggle.innerHTML = '¿No tenés cuenta? <a onclick="_toggleAuthModo()">Registrate gratis</a>';
  } else {
    if (titulo)    titulo.textContent    = "Registrate gratis y empezá";
    if (subtitulo) subtitulo.textContent = "Tus créditos quedan listos al instante · Sin tarjeta";
    if (btn)       btn.textContent       = "Crear cuenta";
    if (pwd)     { pwd.placeholder = "Mínimo 6 caracteres"; pwd.autocomplete = "new-password"; }
    if (toggle)    toggle.innerHTML = '¿Ya tenés cuenta? <a onclick="_toggleAuthModo()">Iniciá sesión</a>';
  }
}

async function _submitEmailAuth() {
  var emailEl = document.getElementById("auth-email");
  var pwdEl   = document.getElementById("auth-pwd");
  var errEl   = document.getElementById("am-error");
  var btn     = document.getElementById("am-submit-btn");
  var email   = (emailEl ? emailEl.value : "").trim();
  var pwd     = pwdEl ? pwdEl.value : "";
  if (!email || !pwd) {
    if (errEl) { errEl.className = "am-error"; errEl.textContent = "Completá email y contraseña."; errEl.style.display = "block"; }
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = _authModo === "register" ? "Creando cuenta..." : "Ingresando..."; }
  if (errEl) errEl.style.display = "none";
  try {
    if (_authModo === "register") {
      var cred = await auth.createUserWithEmailAndPassword(email, pwd);
      await cred.user.sendEmailVerification();
    } else {
      await auth.signInWithEmailAndPassword(email, pwd);
    }
    cerrarModalAuth();
  } catch (e) {
    if (errEl) { errEl.className = "am-error"; errEl.textContent = _traducirErrorFirebase(e.code); errEl.style.display = "block"; }
    if (btn)   { btn.disabled = false; btn.textContent = _authModo === "register" ? "Crear cuenta" : "Iniciar sesión"; }
  }
}

async function _resetPassword() {
  var emailEl = document.getElementById("auth-email");
  var errEl   = document.getElementById("am-error");
  var email   = (emailEl ? emailEl.value : "").trim();
  if (!email) {
    if (errEl) { errEl.className = "am-error"; errEl.textContent = "Ingresá tu email arriba para recuperar tu contraseña."; errEl.style.display = "block"; }
    if (emailEl) emailEl.focus();
    return;
  }
  try {
    await auth.sendPasswordResetEmail(email);
    if (errEl) { errEl.className = "am-error ok"; errEl.textContent = "✓ Te enviamos un correo para restablecer tu contraseña."; errEl.style.display = "block"; }
  } catch (e) {
    if (errEl) { errEl.className = "am-error"; errEl.textContent = _traducirErrorFirebase(e.code); errEl.style.display = "block"; }
  }
}

function _traducirErrorFirebase(code) {
  var msgs = {
    "auth/email-already-in-use": "Ya existe una cuenta con ese email. Usá 'Iniciá sesión'.",
    "auth/invalid-email":        "El formato del email no es válido.",
    "auth/weak-password":        "La contraseña debe tener al menos 6 caracteres.",
    "auth/user-not-found":       "No encontramos una cuenta con ese email.",
    "auth/wrong-password":       "Contraseña incorrecta.",
    "auth/too-many-requests":    "Demasiados intentos. Esperá unos minutos e intentá de nuevo.",
    "auth/invalid-credential":   "Email o contraseña incorrectos.",
    "auth/network-request-failed": "Error de conexión. Verificá tu internet.",
    "auth/popup-closed-by-user": "Se cerró el popup antes de completar el inicio de sesión.",
  };
  return msgs[code] || "Error al autenticar. Intentá de nuevo.";
}

function logout() {
  if (_unsubCreditos) { _unsubCreditos(); _unsubCreditos = null; }
  auth.signOut();
}

auth.onAuthStateChanged(function(user) {
  var loginBtn    = document.getElementById("btn-login");
  var logoutBtn   = document.getElementById("btn-logout");
  var userInfo    = document.getElementById("user-info");
  var creditBadge = document.getElementById("creditos-badge");

  var heroCta = document.getElementById("hero-cta-wrap");

  if (user) {
    if (loginBtn)  loginBtn.style.display  = "none";
    if (logoutBtn) logoutBtn.style.display = "inline-block";
    if (heroCta)   heroCta.style.display   = "none";
    var nombre = user.displayName || (user.email ? user.email.split("@")[0] : "");
    if (userInfo) userInfo.textContent = "Hola, " + nombre;

    // Email/contraseña sin verificar → overlay bloqueante hasta confirmar
    var esEmailPwd = user.providerData.length > 0 && user.providerData[0].providerId === "password";
    if (esEmailPwd && !user.emailVerified) {
      mostrarVerificacionPendiente(user);
      return;
    }

    iniciarEscuchaCreditos(user);
  } else {
    if (loginBtn)    loginBtn.style.display    = "inline-block";
    if (logoutBtn)   logoutBtn.style.display   = "none";
    if (heroCta)     heroCta.style.display     = "";
    if (userInfo)    userInfo.textContent       = "";
    if (creditBadge) creditBadge.style.display = "none";
    _creditos = null;
  }
});
