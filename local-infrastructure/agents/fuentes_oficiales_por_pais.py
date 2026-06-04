"""
Fuentes oficiales de compliance por país.
Cada entrada contiene las URLs y descripciones de los registros/diarios oficiales
que Gemini debe priorizar al investigar entidades en ese país.
"""

FUENTES_POR_PAIS: dict[str, list[dict]] = {

    # ── URUGUAY ────────────────────────────────────────────────────────────────
    "uruguay": [
        {"nombre": "IMPO — Diario Oficial",           "url": "https://www.impo.com.uy",                "descripcion": "Diario Oficial de Uruguay: publicaciones legales, sociedades, resoluciones"},
        {"nombre": "DGI — Registro contribuyentes",   "url": "https://www.dgi.gub.uy",                 "descripcion": "Dirección General Impositiva: consulta RUT, situación fiscal"},
        {"nombre": "BCU — Registros financieros",     "url": "https://www.bcu.gub.uy",                 "descripcion": "Banco Central del Uruguay: instituciones financieras, cambiarias, emisoras"},
        {"nombre": "SENACLAFT",                       "url": "https://www.senaclaft.gub.uy",           "descripcion": "Secretaría ALD/CFT: sanciones, resoluciones antilavado"},
        {"nombre": "Poder Judicial Uruguay",          "url": "https://www.poderjudicial.gub.uy",       "descripcion": "Consulta de causas judiciales, procesados, sentencias"},
        {"nombre": "Registros BPS / Comercio",        "url": "https://www.registros.gub.uy",           "descripcion": "Registro de Comercio, personas jurídicas, propiedades"},
        {"nombre": "AIN — Auditoría Interna Nación",  "url": "https://www.ain.gub.uy",                 "descripcion": "Control de sociedades anónimas, estados contables"},
    ],

    # ── ARGENTINA ──────────────────────────────────────────────────────────────
    "argentina": [
        {"nombre": "Boletín Oficial Argentina",       "url": "https://www.boletinoficial.gob.ar",      "descripcion": "Diario oficial: leyes, decretos, sociedades, quiebras"},
        {"nombre": "AFIP — Padrón CUIT",              "url": "https://www.afip.gob.ar",                "descripcion": "Administración Federal de Ingresos Públicos: consulta CUIT, situación fiscal"},
        {"nombre": "UIF — Sanciones ALD",             "url": "https://www.uif.gob.ar",                 "descripcion": "Unidad de Información Financiera: resoluciones, sanciones antilavado, PEPs"},
        {"nombre": "IGJ — Personas Jurídicas",        "url": "https://www.igj.gob.ar",                 "descripcion": "Inspección General de Justicia: sociedades, directores, razones sociales"},
        {"nombre": "BCRA — Entidades financieras",    "url": "https://www.bcra.gob.ar",                "descripcion": "Banco Central: financieras habilitadas, inhabilitados, deudores"},
        {"nombre": "Poder Judicial — CIJ",            "url": "https://www.cij.gov.ar",                 "descripcion": "Centro de Información Judicial: causas penales, resoluciones"},
        {"nombre": "Registro Prendario / Propiedad",  "url": "https://www.jus.gob.ar",                 "descripcion": "Ministerio de Justicia: registro de la propiedad, prendas"},
    ],

    # ── PARAGUAY ──────────────────────────────────────────────────────────────
    "paraguay": [
        {"nombre": "Gaceta Oficial Paraguay",         "url": "https://www.gacetaoficial.gov.py",       "descripcion": "Gaceta Oficial: leyes, decretos, resoluciones, sociedades"},
        {"nombre": "SET — Registro tributario",       "url": "https://www.set.gov.py",                 "descripcion": "Subsecretaría de Estado de Tributación: RUC, situación fiscal"},
        {"nombre": "BCP — Entidades financieras",     "url": "https://www.bcp.gov.py",                 "descripcion": "Banco Central del Paraguay: instituciones, cambios, sanciones"},
        {"nombre": "SEPRELAD — ALD",                  "url": "https://www.seprelad.gov.py",            "descripcion": "Secretaría Prevención Lavado de Activos: alertas, resoluciones"},
        {"nombre": "Poder Judicial Paraguay",         "url": "https://www.pj.gov.py",                  "descripcion": "Consulta de expedientes y causas judiciales"},
        {"nombre": "DGRP — Personas Jurídicas",       "url": "https://www.dgrp.gov.py",                "descripcion": "Dirección General de Registros Públicos: sociedades, inmuebles"},
    ],

    # ── BRASIL ────────────────────────────────────────────────────────────────
    "brasil": [
        {"nombre": "Diário Oficial da União",         "url": "https://www.in.gov.br",                  "descripcion": "Diário Oficial Federal: atos oficiais, sanções, empresas"},
        {"nombre": "Receita Federal — CNPJ",          "url": "https://www.gov.br/receitafederal",      "descripcion": "CNPJ: consulta empresas, situación fiscal, socios"},
        {"nombre": "COAF — Lavagem de dinheiro",      "url": "https://www.gov.br/coaf",                "descripcion": "Conselho de Controle de Atividades Financeiras: alertas ALD"},
        {"nombre": "BCB — Banco Central Brasil",      "url": "https://www.bcb.gov.br",                 "descripcion": "Banco Central: instituições financeiras, câmbio, sanciones"},
        {"nombre": "CGU — Cadastro sanções",          "url": "https://www.cgu.gov.br",                 "descripcion": "Controladoria Geral: empresas sancionadas, CEIS, CNEP"},
        {"nombre": "Tribunal de Justiça",             "url": "https://www.cnj.jus.br",                 "descripcion": "Conselho Nacional de Justiça: consulta processos, execuções"},
    ],

    # ── CHILE ─────────────────────────────────────────────────────────────────
    "chile": [
        {"nombre": "Diario Oficial Chile",            "url": "https://www.diariooficial.interior.gob.cl", "descripcion": "Diario Oficial: leyes, decretos, sociedades, quiebras"},
        {"nombre": "SII — RUT empresas",              "url": "https://www.sii.cl",                     "descripcion": "Servicio de Impuestos Internos: RUT, situación tributaria"},
        {"nombre": "UAF — Sanciones ALD",             "url": "https://www.uaf.cl",                     "descripcion": "Unidad de Análisis Financiero: resoluciones antilavado, PEPs"},
        {"nombre": "CMF — Entidades financieras",     "url": "https://www.cmfchile.cl",                "descripcion": "Comisión Mercado Financiero: bancos, aseguradoras, valores"},
        {"nombre": "Poder Judicial Chile",            "url": "https://www.pjud.cl",                    "descripcion": "Consulta de causas civiles y penales"},
        {"nombre": "Registro Comercio — SRCI",        "url": "https://www.registrocivil.cl",           "descripcion": "Registro de Comercio, personas jurídicas, propiedades"},
    ],

    # ── PERÚ ──────────────────────────────────────────────────────────────────
    "peru": [
        {"nombre": "El Peruano — Diario Oficial",     "url": "https://www.elperuano.pe",               "descripcion": "Diario Oficial El Peruano: normas, avisos judiciales, sociedades"},
        {"nombre": "SUNAT — RUC",                     "url": "https://www.sunat.gob.pe",               "descripcion": "RUC: situación fiscal, representantes legales"},
        {"nombre": "UIF-Perú — ALD",                  "url": "https://www.sbs.gob.pe/uif",             "descripcion": "Unidad de Inteligencia Financiera: alertas, sanciones, reportes"},
        {"nombre": "SBS — Entidades supervisadas",    "url": "https://www.sbs.gob.pe",                 "descripcion": "Superintendencia Banca y Seguros: financieras autorizadas, sanciones"},
        {"nombre": "Poder Judicial Perú",             "url": "https://www.pj.gob.pe",                  "descripcion": "Consulta de expedientes judiciales"},
        {"nombre": "SUNARP — Registros Públicos",     "url": "https://www.sunarp.gob.pe",              "descripcion": "Registros Públicos: sociedades, inmuebles, prendas"},
    ],

    # ── COLOMBIA ──────────────────────────────────────────────────────────────
    "colombia": [
        {"nombre": "Diario Oficial Colombia",         "url": "https://www.diariooficial.gov.co",       "descripcion": "Diario Oficial: leyes, decretos, resoluciones, actos administrativos"},
        {"nombre": "DIAN — NIT empresas",             "url": "https://www.dian.gov.co",                "descripcion": "DIAN: NIT, situación tributaria, obligaciones"},
        {"nombre": "UIAF — ALD Colombia",             "url": "https://www.uiaf.gov.co",                "descripcion": "Unidad de Información y Análisis Financiero: reportes, alertas"},
        {"nombre": "Superfinanciera",                 "url": "https://www.superfinanciera.gov.co",     "descripcion": "Superintendencia Financiera: entidades, sanciones, investigaciones"},
        {"nombre": "Cámara de Comercio",              "url": "https://www.confecamaras.org.co",        "descripcion": "Registro Mercantil: sociedades, representantes, socios"},
        {"nombre": "Rama Judicial Colombia",          "url": "https://www.ramajudicial.gov.co",        "descripcion": "Consulta de procesos judiciales"},
    ],

    # ── ECUADOR ───────────────────────────────────────────────────────────────
    "ecuador": [
        {"nombre": "Registro Oficial Ecuador",        "url": "https://www.registroficial.gob.ec",      "descripcion": "Registro Oficial: leyes, decretos, resoluciones"},
        {"nombre": "SRI — RUC Ecuador",               "url": "https://www.sri.gob.ec",                 "descripcion": "RUC: situación tributaria, representantes"},
        {"nombre": "UAFE — ALD Ecuador",              "url": "https://www.uafe.gob.ec",                "descripcion": "Unidad de Análisis Financiero: reportes antilavado, sanciones"},
        {"nombre": "Superintendencia Compañías",      "url": "https://www.supercias.gob.ec",           "descripcion": "Registro de sociedades, directores, balances"},
        {"nombre": "Función Judicial Ecuador",        "url": "https://www.funcionjudicial.gob.ec",     "descripcion": "Consulta de causas judiciales"},
    ],

    # ── BOLIVIA ───────────────────────────────────────────────────────────────
    "bolivia": [
        {"nombre": "Gaceta Oficial Bolivia",          "url": "https://www.gacetaoficialdebolivia.gob.bo", "descripcion": "Gaceta Oficial: leyes, decretos, resoluciones"},
        {"nombre": "SIN — NIT Bolivia",               "url": "https://www.impuestos.gob.bo",           "descripcion": "Servicio de Impuestos Nacionales: NIT, situación fiscal"},
        {"nombre": "UIF Bolivia — ALD",               "url": "https://www.uif.gob.bo",                 "descripcion": "Unidad de Investigaciones Financieras: alertas, sanciones"},
        {"nombre": "ASFI — Entidades financieras",    "url": "https://www.asfi.gob.bo",                "descripcion": "Autoridad de Supervisión del Sistema Financiero"},
        {"nombre": "Fundempresa — Registro Comercio", "url": "https://www.fundempresa.org.bo",         "descripcion": "Registro de Comercio de Bolivia: empresas, directores"},
    ],

    # ── ESPAÑA ────────────────────────────────────────────────────────────────
    "españa": [
        {"nombre": "BOE — Boletín Oficial Estado",    "url": "https://www.boe.es",                     "descripcion": "BOE: leyes, decretos, sanciones, anuncios judiciales"},
        {"nombre": "AEAT — CIF/NIF empresas",         "url": "https://www.agenciatributaria.es",       "descripcion": "Agencia Tributaria: CIF, situación fiscal, IAE"},
        {"nombre": "SEPBLAC — ALD España",            "url": "https://www.sepblac.es",                 "descripcion": "Servicio Ejecutivo Prevención Blanqueo: resoluciones, sanciones"},
        {"nombre": "Registro Mercantil Central",      "url": "https://www.rmc.es",                     "descripcion": "Registro Mercantil: sociedades, directores, depositados"},
        {"nombre": "CNMV — Mercado valores",          "url": "https://www.cnmv.es",                    "descripcion": "Comisión Nacional Mercado Valores: sanciones, entidades"},
        {"nombre": "Poder Judicial España",           "url": "https://www.poderjudicial.es",           "descripcion": "Consulta de resoluciones judiciales"},
    ],

    # ── PANAMÁ ────────────────────────────────────────────────────────────────
    "panama": [
        {"nombre": "Gaceta Oficial Panamá",           "url": "https://www.gacetaoficial.gob.pa",       "descripcion": "Gaceta Oficial: leyes, decretos, avisos corporativos"},
        {"nombre": "DGI Panamá — RUC",                "url": "https://www.dgi.gob.pa",                 "descripcion": "Dirección General de Ingresos: RUC, situación fiscal"},
        {"nombre": "UAF Panamá — ALD",                "url": "https://www.uaf.gob.pa",                 "descripcion": "Unidad de Análisis Financiero: alertas antilavado, sanciones"},
        {"nombre": "SBP — Entidades financieras",     "url": "https://www.superbancos.gob.pa",         "descripcion": "Superintendencia de Bancos de Panamá"},
        {"nombre": "Registro Público Panamá",         "url": "https://www.registro-publico.gob.pa",    "descripcion": "Registro Público: sociedades, directores, propiedades"},
        {"nombre": "Poder Judicial Panamá",           "url": "https://www.organojudicial.gob.pa",      "descripcion": "Consulta de procesos judiciales"},
    ],

    # ── MÉXICO ────────────────────────────────────────────────────────────────
    "mexico": [
        {"nombre": "DOF — Diario Oficial Federación", "url": "https://www.dof.gob.mx",                 "descripcion": "Diario Oficial: leyes, decretos, avisos, licitaciones"},
        {"nombre": "SAT — RFC",                       "url": "https://www.sat.gob.mx",                 "descripcion": "RFC: situación fiscal de personas y empresas"},
        {"nombre": "FINTRAC / UIF México",            "url": "https://www.uif.shcp.gob.mx",            "descripcion": "Unidad de Inteligencia Financiera: listas negras, sanciones ALD"},
        {"nombre": "CNBV — Entidades financieras",    "url": "https://www.cnbv.gob.mx",                "descripcion": "Comisión Nacional Bancaria: instituciones autorizadas, sanciones"},
        {"nombre": "RPC — Registro Público Comercio", "url": "https://www.rpc.economia.gob.mx",        "descripcion": "Registro Público de Comercio: razones sociales, socios"},
        {"nombre": "Poder Judicial México",           "url": "https://www.dgepj.cjf.gob.mx",          "descripcion": "Consulta de juicios federales"},
    ],
}

# Alias de normalización: cómo el usuario podría escribir el nombre del país
_ALIAS: dict[str, str] = {
    "uy": "uruguay", "ar": "argentina", "py": "paraguay",
    "br": "brasil", "brazil": "brasil",
    "cl": "chile",
    "pe": "peru", "perú": "peru",
    "co": "colombia",
    "ec": "ecuador",
    "bo": "bolivia",
    "es": "españa", "spain": "españa", "espana": "españa",
    "pa": "panama", "panamá": "panama",
    "mx": "mexico", "méxico": "mexico",
}


def obtener_fuentes(pais: str) -> list[dict]:
    """Devuelve la lista de fuentes oficiales para el país dado (insensible a mayúsculas/acentos)."""
    clave = pais.strip().lower()
    clave = _ALIAS.get(clave, clave)
    return FUENTES_POR_PAIS.get(clave, [])


def formatear_fuentes_para_prompt(paises: list[str]) -> str:
    """
    Dado un listado de países, retorna un bloque de texto listo para insertar
    en un prompt de Gemini indicando las fuentes oficiales a priorizar.
    """
    bloques = []
    paises_sin_fuentes = []

    for pais in paises:
        fuentes = obtener_fuentes(pais)
        if fuentes:
            lineas = [f"   • {f['nombre']} ({f['url']}): {f['descripcion']}" for f in fuentes]
            bloques.append(f"  [{pais.upper()}]\n" + "\n".join(lineas))
        else:
            paises_sin_fuentes.append(pais)

    if not bloques and not paises_sin_fuentes:
        return ""

    texto = "FUENTES OFICIALES PRIORITARIAS A CONSULTAR (busca dentro de estos sitios):\n"
    texto += "\n".join(bloques)

    if paises_sin_fuentes:
        texto += f"\n  [OTROS PAÍSES: {', '.join(paises_sin_fuentes)}] — busca en Diario Oficial, registro de comercio y autoridad ALD/FT de cada país."

    return texto
