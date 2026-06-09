"""
Exportación del Legajo de Cumplimiento en PDF — Módulo 7.

Genera un PDF estructurado, auditoriable e íntegro con toda la evidencia del proceso KYC/AML.

GARANTÍAS DE INTEGRIDAD:
  - Cada legajo tiene un ID único y timestamp UTC.
  - Se calcula un hash SHA-256 del contenido (datos serializados como JSON canónico).
  - El hash se imprime en la última página y se registra en el audit_log.
  - Para verificar integridad: re-serializar los datos y comparar el hash.

SEPARACIÓN DE VISTAS (no tipping off):
  - Sección 6 (alertas internas) lleva cabecera "USO INTERNO — CONFIDENCIAL".
  - Esta sección NUNCA debe entregarse al cliente ni a terceros no autorizados.

Marco legal: SENACLAFT, Ley 19.574, Ley 18.331 (protección de datos).
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

from .audit_log import registrar as audit_registrar

ENCODING = "utf-8"

# Colores institucionales AHC
COLOR_PRIMARIO    = colors.HexColor("#1a3a5c")   # azul oscuro
COLOR_SECUNDARIO  = colors.HexColor("#2e7d32")   # verde
COLOR_ALTO_RIESGO = colors.HexColor("#c62828")   # rojo
COLOR_WARN        = colors.HexColor("#f57f17")   # naranja/amarillo
COLOR_CONF        = colors.HexColor("#b71c1c")   # rojo oscuro — sección confidencial
COLOR_FONDO_TABLA = colors.HexColor("#e8eaf6")
COLOR_FONDO_CONF  = colors.HexColor("#fce4ec")


# ─── Estructura de datos del legajo ───────────────────────────────────────────

@dataclass
class LegajoDatos:
    """
    Agrupa toda la evidencia del proceso KYC/AML para generar el legajo PDF.
    declaracion_fiscal_presente: MÓDULO 4 — el legajo no se completa sin este documento.
    """
    nombre_cliente:               str
    datos_formulario:             dict[str, Any]
    screening_ofac:               dict[str, Any]
    screening_pep:                dict[str, Any]
    evaluacion_riesgo:            dict[str, Any]
    investigador_id:              str
    # Campos de legajo unificado (con defaults para compatibilidad hacia atrás)
    id_cliente:                    str = ""
    estado:                        str = "SIN_ALERTAS_AUTOMATICAS"
    decision_oficial_cumplimiento: Any = None
    nota_legal:                    str = ""
    vigencia_hasta:                str = ""
    validacion_cruzada:            dict[str, Any] | None = None
    # Campos opcionales originales
    declaracion_fiscal_presente:  bool = False
    declaracion_fiscal_archivo:   str | None = None
    analisis_fondos:              dict[str, Any] | None = None
    alertas_internas:             list[dict[str, Any]] = field(default_factory=list)
    notas_investigador:           str = ""


@dataclass
class ResultadoExportacion:
    pdf_bytes:    bytes
    legajo_id:    str
    data_hash:    str
    timestamp:    str
    completo:     bool
    faltantes:    list[str]
    audit_hash:   str
    id_cliente:   str = ""
    estado:       str = "SIN_ALERTAS_AUTOMATICAS"


# ─── Helpers de contenido ─────────────────────────────────────────────────────

def _color_riesgo(nivel: str) -> colors.Color:
    mapa = {"alto": COLOR_ALTO_RIESGO, "moderado": COLOR_WARN, "bajo": COLOR_SECUNDARIO}
    return mapa.get(nivel.lower(), COLOR_PRIMARIO)


def _hash_datos(datos: LegajoDatos) -> str:
    """SHA-256 del JSON canónico de los datos del legajo."""
    payload = {
        "nombre_cliente":              datos.nombre_cliente,
        "id_cliente":                  datos.id_cliente,
        "estado":                      datos.estado,
        "vigencia_hasta":              datos.vigencia_hasta,
        "datos_formulario":            datos.datos_formulario,
        "screening_ofac":              datos.screening_ofac,
        "screening_pep":               datos.screening_pep,
        "evaluacion_riesgo":           datos.evaluacion_riesgo,
        "declaracion_fiscal_presente": datos.declaracion_fiscal_presente,
        "analisis_fondos":             datos.analisis_fondos,
    }
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode(ENCODING)).hexdigest()


def _validar_completitud(datos: LegajoDatos) -> list[str]:
    """Verifica que el legajo tenga todos los documentos requeridos."""
    faltantes: list[str] = []
    if not datos.nombre_cliente:
        faltantes.append("Nombre del cliente")
    if not datos.datos_formulario:
        faltantes.append("Formulario de debida diligencia")
    if not datos.declaracion_fiscal_presente:
        faltantes.append("Declaración Jurada de Regularidad Fiscal (Módulo 4 — obligatorio)")
    if not datos.screening_ofac:
        faltantes.append("Screening OFAC")
    if not datos.evaluacion_riesgo:
        faltantes.append("Evaluación de riesgo")
    return faltantes


# ─── Construcción del PDF ─────────────────────────────────────────────────────

def _estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Title"],
            textColor=COLOR_PRIMARIO, fontSize=16, spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", parent=base["Heading2"],
            textColor=COLOR_PRIMARIO, fontSize=12, spaceBefore=10, spaceAfter=4,
        ),
        "seccion_conf": ParagraphStyle(
            "seccion_conf", parent=base["Heading2"],
            textColor=COLOR_CONF, fontSize=12, spaceBefore=10, spaceAfter=4,
        ),
        "normal": ParagraphStyle(
            "normal", parent=base["Normal"], fontSize=9, spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=7, textColor=colors.grey,
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Code"], fontSize=7, textColor=colors.darkslategray,
        ),
        "alerta": ParagraphStyle(
            "alerta", parent=base["Normal"],
            textColor=COLOR_ALTO_RIESGO, fontSize=9, fontName="Helvetica-Bold",
        ),
        "ok": ParagraphStyle(
            "ok", parent=base["Normal"],
            textColor=COLOR_SECUNDARIO, fontSize=9, fontName="Helvetica-Bold",
        ),
    }


def _hr(story: list, color: colors.Color = colors.lightgrey) -> None:
    story.append(HRFlowable(width="100%", thickness=0.5, color=color, spaceAfter=4, spaceBefore=4))


def _tabla_dict(datos: dict, estilos: dict, max_val_len: int = 80) -> Table:
    """Convierte un dict plano a una tabla de dos columnas."""
    filas = []
    for k, v in datos.items():
        val = str(v)[:max_val_len] if v is not None else "—"
        filas.append([
            Paragraph(str(k), estilos["small"]),
            Paragraph(val, estilos["normal"]),
        ])
    if not filas:
        filas = [["—", "—"]]
    t = Table(filas, colWidths=[5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), COLOR_FONDO_TABLA),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",(0, 0), (-1, -1), 4),
        ("RIGHTPADDING",(0, 0),(-1, -1), 4),
    ]))
    return t


def _seccion_estado_evaluacion(datos: LegajoDatos, story: list, estilos: dict) -> None:
    """Sección 0 — Estado de evaluación, vigencia y postura legal. Primer elemento visible."""
    # Color según estado
    color_estado = COLOR_ALTO_RIESGO if datos.estado == "ALERTAS_PENDIENTES_REVISION" else COLOR_SECUNDARIO
    story.append(Paragraph(
        f"Estado de evaluación automática: <b>{datos.estado}</b>",
        ParagraphStyle("estado", parent=estilos["normal"], textColor=color_estado,
                       fontName="Helvetica-Bold", fontSize=11),
    ))
    story.append(Paragraph(
        "decision_oficial_cumplimiento: SIN DECISIÓN AUTOMÁTICA — "
        "la determinación final es exclusiva del oficial de cumplimiento humano.",
        ParagraphStyle("decision", parent=estilos["small"], textColor=COLOR_PRIMARIO),
    ))
    if datos.vigencia_hasta:
        story.append(Paragraph(
            f"<b>Vigencia de esta evaluación:</b> {datos.vigencia_hasta} "
            "(vencida = re-screenear, no implica baja del cliente)",
            estilos["small"],
        ))
    if datos.nota_legal:
        story.append(Paragraph(datos.nota_legal, estilos["small"]))
    _hr(story, color_estado)


def _seccion_ofac(datos: LegajoDatos, story: list, estilos: dict) -> None:
    story.append(Paragraph("2. Resultado Screening SANCIONES (OFAC / ONU)", estilos["subtitulo"]))
    ts_consulta = datos.screening_ofac.get("timestamp", "no registrado")
    pub_ofac    = datos.screening_ofac.get("publicacion_ofac", "—")
    listas_al   = datos.screening_ofac.get("listas_actualizadas_al", "—")
    story.append(Paragraph(
        f"<b>Timestamp consulta:</b> {ts_consulta}",
        estilos["normal"],
    ))
    story.append(Paragraph(
        f"<b>Listas descargadas:</b> {listas_al} &nbsp;|&nbsp; <b>Publicación OFAC:</b> {pub_ofac}",
        estilos["small"],
    ))
    riesgo = datos.screening_ofac.get("ofac", {}).get("riesgo", "desconocido")
    color_r = _color_riesgo(riesgo)
    story.append(Paragraph(
        f"Nivel de riesgo OFAC: <b>{riesgo.upper()}</b>",
        ParagraphStyle("r", parent=estilos["normal"], textColor=color_r, fontName="Helvetica-Bold"),
    ))
    coincidencias = datos.screening_ofac.get("ofac", {}).get("coincidencias", [])
    if coincidencias:
        filas = [["Nombre en lista", "Score", "Lista", "Programas", "Fuente"]]
        for c in coincidencias[:10]:
            filas.append([
                c.get("nombre", "")[:35],
                str(c.get("score", "")),
                c.get("lista", ""),
                ", ".join(c.get("programas", [])),
                c.get("fuente", "")[:40],
            ])
        t = Table(filas, colWidths=[4.5*cm, 1.5*cm, 2.5*cm, 3*cm, 5.5*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARIO),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, -1), 7),
            ("GRID",       (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_FONDO_TABLA]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Sin coincidencias sobre el umbral configurado.", estilos["ok"]))
    _hr(story)


def _seccion_pep(datos: LegajoDatos, story: list, estilos: dict) -> None:
    story.append(Paragraph("3. Posibles indicios PEP / Adverse Media", estilos["subtitulo"]))
    # Timestamp: está en cada item como fecha_busqueda; tomar del primero
    posibles = datos.screening_pep.get("posibles_coincidencias", [])
    fecha_busqueda = posibles[0].get("fecha_busqueda", "—") if posibles else "—"
    story.append(Paragraph(
        f"<b>Fecha de búsqueda en fuentes abiertas:</b> {fecha_busqueda}",
        estilos["small"],
    ))
    story.append(Paragraph(
        datos.screening_pep.get("nota", ""),
        estilos["small"],
    ))
    if posibles:
        for p in posibles[:8]:
            confianza = p.get("confianza", "bajo")
            c_color = {"alto": COLOR_ALTO_RIESGO, "medio": COLOR_WARN, "bajo": colors.grey}.get(confianza, colors.grey)
            story.append(Paragraph(
                f"<b>[{confianza.upper()}]</b> {p.get('titulo', '')} — {p.get('fuente_nombre', '')}",
                ParagraphStyle("ph", parent=estilos["normal"], textColor=c_color),
            ))
            story.append(Paragraph(
                p.get("extracto", "")[:200],
                estilos["small"],
            ))
            story.append(Paragraph(p.get("url", ""), estilos["mono"]))
            story.append(Spacer(1, 0.2 * cm))
    else:
        story.append(Paragraph("Sin indicios en fuentes abiertas.", estilos["ok"]))
    _hr(story)


def _seccion_riesgo(datos: LegajoDatos, story: list, estilos: dict) -> None:
    """
    Compatible con el formato de MatrizRiesgo.evaluar():
      riesgo, total_ponderado, version_matriz, config_hash, bloqueado, motivo_bloqueo, detalle
    """
    story.append(Paragraph("4. Calificacion de Riesgo", estilos["subtitulo"]))
    er      = datos.evaluacion_riesgo
    nivel   = er.get("riesgo", "Desconocido")
    c_nivel = _color_riesgo(nivel)

    # Línea de resumen
    bloqueado = er.get("bloqueado", False)
    bloqueo_txt = " | <b>BLOQUEO: SI</b>" if bloqueado else ""
    story.append(Paragraph(
        f"Calificacion: <b>{nivel}</b> | "
        f"Puntaje ponderado: {er.get('total_ponderado', '—')} | "
        f"Matriz v{er.get('version_matriz', '—')} | "
        f"Evaluado: {er.get('timestamp', '—')}"
        f"{bloqueo_txt}",
        ParagraphStyle("rv", parent=estilos["normal"], textColor=c_nivel),
    ))

    # Motivo de bloqueo si corresponde
    if bloqueado and er.get("motivo_bloqueo"):
        story.append(Paragraph(er["motivo_bloqueo"], estilos["alerta"]))

    # Advertencia por respuestas no encontradas en tabla
    faltantes = er.get("respuestas_no_encontradas", [])
    if faltantes:
        story.append(Paragraph(
            f"Advertencia: {len(faltantes)} factor(es) no encontrado(s) en la matriz — "
            + ", ".join(f["factor"] for f in faltantes),
            estilos["alerta"],
        ))

    # Tabla de detalle por factor
    detalle = er.get("detalle", [])
    if detalle:
        filas = [["Factor", "Respuesta", "Puntaje", "Peso", "Ponderado", "Bloqueo"]]
        for d in detalle:
            es_bloqueo = d.get("bloqueo", False)
            puntaje_str = str(d.get("puntaje", "—"))
            if not d.get("en_tabla", True):
                puntaje_str += " (?)"
            filas.append([
                d.get("factor", ""),
                str(d.get("respuesta", ""))[:30],
                puntaje_str,
                str(d.get("peso", "")),
                str(d.get("ponderado", "")),
                "SI" if es_bloqueo else "—",
            ])
        t = Table(filas, colWidths=[4.5*cm, 4.5*cm, 1.8*cm, 1.5*cm, 2*cm, 1.8*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), COLOR_PRIMARIO),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("GRID",          (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, COLOR_FONDO_TABLA]),
            # Resaltar filas de bloqueo en rojo claro
            *[
                ("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor("#ffcdd2"))
                for i, d in enumerate(detalle) if d.get("bloqueo")
            ],
        ]))
        story.append(t)

    # Hash de config para trazabilidad auditorial
    if er.get("config_hash"):
        story.append(Paragraph(
            f"Hash config matriz: {er['config_hash'][:24]}...",
            estilos["small"],
        ))
    if er.get("notas"):
        story.append(Paragraph(f"Notas: {er['notas']}", estilos["small"]))
    _hr(story)


def _seccion_fondos(datos: LegajoDatos, story: list, estilos: dict) -> None:
    story.append(Paragraph("5. Analisis de Origen de Fondos", estilos["subtitulo"]))
    af = datos.analisis_fondos
    if not af:
        story.append(Paragraph("No se realizó análisis de fondos para este legajo.", estilos["small"]))
        _hr(story)
        return
    bandera = af.get("bandera_incongruencia", False)
    estilo_flag = estilos["alerta"] if bandera else estilos["ok"]
    story.append(Paragraph(
        f"{'INCONGRUENCIA DETECTADA' if bandera else 'Sin incongruencia detectada'}",
        estilo_flag,
    ))
    story.append(Paragraph(af.get("descripcion_bandera", ""), estilos["normal"]))
    story.append(Paragraph(af.get("nota", ""), estilos["small"]))
    _hr(story)


def _seccion_alertas_internas(datos: LegajoDatos, story: list, estilos: dict) -> None:
    """
    Sección CONFIDENCIAL — USO INTERNO.
    Contiene señales de alerta que NUNCA deben ser visibles para el cliente.
    """
    story.append(PageBreak())
    story.append(Paragraph(
        "SECCION CONFIDENCIAL — USO INTERNO EXCLUSIVO",
        ParagraphStyle(
            "conf_header",
            parent=estilos["normal"],
            textColor=colors.white,
            backColor=COLOR_CONF,
            fontSize=11,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=6,
        ),
    ))
    story.append(Paragraph(
        "NO TIPPING OFF: Esta sección es estrictamente confidencial. "
        "No entregar al cliente ni a terceros no autorizados. "
        "Ley 19.574, Art. 20.",
        ParagraphStyle("conf_note", parent=estilos["small"], textColor=COLOR_CONF),
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("6. Senales de Alerta Internas", estilos["seccion_conf"]))

    alertas = datos.alertas_internas
    if not alertas:
        story.append(Paragraph("No se detectaron señales de alerta en este caso.", estilos["ok"]))
    else:
        for a in alertas:
            story.append(Paragraph(
                f"[{a.get('tipo', '').upper()}] {a.get('descripcion', '')}",
                estilos["alerta"],
            ))
            story.append(Paragraph(
                f"Sugerencia: {a.get('sugerencia', '')}",
                estilos["normal"],
            ))
            evidencia = a.get("evidencia", [])
            if evidencia:
                for ev in evidencia[:5]:
                    story.append(Paragraph(f"  • {ev}", estilos["small"]))
            story.append(Spacer(1, 0.2 * cm))


def _pagina_integridad(
    legajo_id: str,
    data_hash: str,
    timestamp: str,
    faltantes: list[str],
    story: list,
    estilos: dict,
) -> None:
    story.append(PageBreak())
    story.append(Paragraph("VERIFICACION DE INTEGRIDAD Y AUDITORIA", estilos["subtitulo"]))
    _hr(story, COLOR_PRIMARIO)
    story.append(Paragraph(f"ID del legajo:    {legajo_id}", estilos["normal"]))
    story.append(Paragraph(f"Generado (UTC):   {timestamp}", estilos["normal"]))
    story.append(Paragraph("Hash SHA-256 del contenido (datos serializados):", estilos["small"]))
    story.append(Paragraph(data_hash, estilos["mono"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Para verificar integridad: re-serializar los datos del legajo como JSON canónico "
        "(sort_keys=True) y calcular SHA-256. El resultado debe coincidir con el hash anterior.",
        estilos["small"],
    ))
    _hr(story)
    if faltantes:
        story.append(Paragraph("LEGAJO INCOMPLETO — Documentos faltantes:", estilos["alerta"]))
        for f in faltantes:
            story.append(Paragraph(f"  • {f}", estilos["alerta"]))
    else:
        story.append(Paragraph("Legajo completo — todos los documentos requeridos presentes.", estilos["ok"]))


def _generar_pdf(datos: LegajoDatos, legajo_id: str, data_hash: str, faltantes: list[str]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=f"Legajo KYC/AML — {datos.nombre_cliente}",
        author="AHC Intelligence",
    )
    estilos = _estilos()
    story: list[Any] = []

    # ── Encabezado ────────────────────────────────────────────────────────────
    timestamp = datetime.utcnow().isoformat() + "Z"
    story.append(Paragraph("AHC INTELLIGENCE", estilos["titulo"]))
    story.append(Paragraph("Legajo de Cumplimiento KYC/AML", estilos["subtitulo"]))
    story.append(Paragraph(
        f"ID: {legajo_id} &nbsp;|&nbsp; Generado: {timestamp} &nbsp;|&nbsp; "
        f"Investigador: {datos.investigador_id}",
        estilos["small"],
    ))
    _hr(story, COLOR_PRIMARIO)

    # ── Sección 0: Estado de evaluación y postura legal ───────────────────────
    _seccion_estado_evaluacion(datos, story, estilos)

    # ── Sección 1: Datos del cliente ──────────────────────────────────────────
    story.append(Paragraph("1. Datos del Cliente", estilos["subtitulo"]))
    story.append(Paragraph(f"<b>Nombre/Denominación:</b> {datos.nombre_cliente}", estilos["normal"]))

    decl_text = (
        f"Declaracion Fiscal: <b>{'PRESENTE' if datos.declaracion_fiscal_presente else 'FALTA — LEGAJO INCOMPLETO'}</b>"
        + (f" ({datos.declaracion_fiscal_archivo})" if datos.declaracion_fiscal_archivo else "")
    )
    decl_style = estilos["ok"] if datos.declaracion_fiscal_presente else estilos["alerta"]
    story.append(Paragraph(decl_text, decl_style))

    if datos.datos_formulario:
        story.append(Spacer(1, 0.2 * cm))
        story.append(_tabla_dict(datos.datos_formulario, estilos))
    _hr(story)

    # ── Sección 2: Screening OFAC ─────────────────────────────────────────────
    _seccion_ofac(datos, story, estilos)

    # ── Sección 3: PEP / Adverse Media ───────────────────────────────────────
    _seccion_pep(datos, story, estilos)

    # ── Sección 4: Riesgo ─────────────────────────────────────────────────────
    _seccion_riesgo(datos, story, estilos)

    # ── Sección 5: Fondos ─────────────────────────────────────────────────────
    _seccion_fondos(datos, story, estilos)

    # ── Notas del investigador ────────────────────────────────────────────────
    if datos.notas_investigador:
        story.append(Paragraph("Notas del Investigador", estilos["subtitulo"]))
        story.append(Paragraph(datos.notas_investigador, estilos["normal"]))
        _hr(story)

    # ── Sección 6: Alertas internas (CONFIDENCIAL) ────────────────────────────
    _seccion_alertas_internas(datos, story, estilos)

    # ── Página de integridad ──────────────────────────────────────────────────
    _pagina_integridad(legajo_id, data_hash, timestamp, faltantes, story, estilos)

    doc.build(story)
    return buf.getvalue()


# ─── API pública ──────────────────────────────────────────────────────────────

def exportar_legajo(
    datos: LegajoDatos,
    usuario_id: str | None = None,
    ip_addr: str | None = None,
) -> ResultadoExportacion:
    """
    Genera el Legajo de Cumplimiento en PDF con garantías de integridad auditoriable.

    El legajo se genera siempre — si faltan documentos requeridos, se marca como
    INCOMPLETO con los items faltantes detallados. El compliance officer decide
    si proceder con un legajo incompleto queda bajo su responsabilidad.

    Toda generación queda registrada en el audit_log con el hash del contenido.

    Returns:
        ResultadoExportacion con pdf_bytes, legajo_id, data_hash, completo, faltantes.
    """
    legajo_id = (
        datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        + "_"
        + uuid.uuid4().hex[:8].upper()
    )
    timestamp = datetime.utcnow().isoformat() + "Z"

    faltantes  = _validar_completitud(datos)
    completo   = len(faltantes) == 0
    data_hash  = _hash_datos(datos)

    pdf_bytes = _generar_pdf(datos, legajo_id, data_hash, faltantes)

    # Registrar en audit log — cada exportación queda trazada
    audit_hash = audit_registrar(
        accion="generar_legajo",
        usuario_id=usuario_id or datos.investigador_id,
        recurso=legajo_id,
        detalles={
            "nombre_cliente":  datos.nombre_cliente,
            "completo":        completo,
            "faltantes":       faltantes,
            "data_hash":       data_hash,
            "pdf_size_bytes":  len(pdf_bytes),
            "config_riesgo_v": datos.evaluacion_riesgo.get("config_version", "—"),
        },
        ip_addr=ip_addr,
    )

    return ResultadoExportacion(
        pdf_bytes=pdf_bytes,
        legajo_id=legajo_id,
        data_hash=data_hash,
        timestamp=timestamp,
        completo=completo,
        faltantes=faltantes,
        audit_hash=audit_hash,
        id_cliente=datos.id_cliente,
        estado=datos.estado,
    )
