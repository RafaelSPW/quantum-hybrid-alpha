import os
import sys
import io
import re
import json
import math
import tempfile
from pathlib import Path
from google import genai
from google.genai import types
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cambiar a False cuando el saldo de Gemini esté activo
MOCK_MODE = False

SUSPICIOUS_CREATORS = [
    "photoshop", "illustrator", "canva", "gimp", "affinity",
    "inkscape", "pixelmator", "paint.net", "corel", "snapseed",
    "lightroom", "procreate", "midjourney", "stable diffusion", "dall-e",
]


def _mock_resultado(datos_cliente: dict) -> dict:
    return {
        "nombre_investigado": datos_cliente['nombre'],
        "documento": datos_cliente['documento'],
        "status_evaluacion": "ALERTA_RIESGO",
        "resumen_ejecutivo": (
            f"Se registra actividad societaria a nombre de {datos_cliente['nombre']} "
            f"(Doc: {datos_cliente['documento']}) en Uruguay, con participación en dos sociedades comerciales "
            f"constituidas entre 2018 y 2021. Se constata actividad comercial documentada en Suecia "
            f"a través de una empresa vinculada. No se hallaron registros en las bases OFAC ni en las "
            f"listas de sanciones del Consejo de Seguridad de la ONU para los países rastreados."
        ),
        "empresas_vinculadas": [
            {
                "nombre_empresa": "Inversiones del Sur S.A. [MOCK]",
                "pais": "Uruguay",
                "socios_detectados": ["Carlos Alberto Méndez", "María López Ríos"],
            },
            {
                "nombre_empresa": "Nordic Trade AB [MOCK]",
                "pais": "Suecia",
                "socios_detectados": ["Erik Johansson"],
            },
        ],
        "alertas_ofac_crimen": [
            "Homónimo detectado en base OFAC — descartado por divergencia documental",
            "Ninguna coincidencia confirmada en listas ONU",
        ],
        "paises_rastreados_efectivos": ["Argentina", "Uruguay", "Suecia"],
        "_modo": "SIMULADO — activar MOCK_MODE=False cuando haya saldo Gemini",
    }


def _mock_forense(nombre_archivo: str, metadata: dict) -> dict:
    señales = metadata.get("señales_sospechosas", []) if metadata else []
    return {
        "documento_autentico": len(señales) == 0,
        "score_confianza_antifraude": 91.5 if len(señales) == 0 else 52.0,
        "anomalias_detectadas": señales if señales else ["[SIMULADO] Sin anomalías detectadas — activar API para análisis multimodal completo"],
        "metadata_local": metadata or {},
        "_modo": "SIMULADO",
    }


class QuantumComplianceAgent:
    def __init__(self, api_key: str):
        if not MOCK_MODE:
            self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    # ─── CAPA 1: Metadatos locales ────────────────────────────────────────────

    def _analizar_metadatos_local(self, archivo_path: str) -> dict:
        resultado = {
            "creador_detectado": "Desconocido",
            "fecha_creacion": None,
            "fecha_modificacion": None,
            "señales_sospechosas": [],
        }
        try:
            ext = Path(archivo_path).suffix.lower()
            if ext == ".pdf":
                self._metadatos_pdf(archivo_path, resultado)
            elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
                self._metadatos_imagen(archivo_path, resultado)
        except Exception as e:
            resultado["señales_sospechosas"].append(f"Error al leer metadatos: {e}")
        return resultado

    def _metadatos_pdf(self, archivo_path: str, r: dict):
        try:
            with open(archivo_path, "rb") as f:
                raw = f.read(12288).decode("latin-1", errors="ignore")

            for field, key in [("/Creator", "creador_detectado"), ("/Producer", "creador_detectado")]:
                m = re.search(rf'{re.escape(field)}\s*\(([^)]+)\)', raw)
                if m and (r[key] == "Desconocido" or field == "/Creator"):
                    r[key] = m.group(1).strip()

            m = re.search(r'/CreationDate\s*\(([^)]+)\)', raw)
            if m:
                r["fecha_creacion"] = m.group(1)[:14]
            m = re.search(r'/ModDate\s*\(([^)]+)\)', raw)
            if m:
                r["fecha_modificacion"] = m.group(1)[:14]

            creator_lower = r["creador_detectado"].lower()
            for s in SUSPICIOUS_CREATORS:
                if s in creator_lower:
                    r["señales_sospechosas"].append(
                        f"PDF generado con software de edición de imágenes: '{r['creador_detectado']}'"
                    )
                    break

            if r["fecha_creacion"] and r["fecha_modificacion"] and \
               r["fecha_creacion"] != r["fecha_modificacion"]:
                r["señales_sospechosas"].append(
                    f"Fecha de modificación ({r['fecha_modificacion']}) difiere de la de creación ({r['fecha_creacion']})"
                )
        except Exception as e:
            r["señales_sospechosas"].append(f"No se pudo analizar PDF: {e}")

    def _metadatos_imagen(self, archivo_path: str, r: dict):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(archivo_path)
            exif_raw = img._getexif() if hasattr(img, "_getexif") else None
            if exif_raw:
                for tag_id, val in exif_raw.items():
                    tag = TAGS.get(tag_id, "")
                    if tag == "Software":
                        r["creador_detectado"] = str(val)
                        for s in SUSPICIOUS_CREATORS:
                            if s in str(val).lower():
                                r["señales_sospechosas"].append(
                                    f"Imagen procesada con software de edición: '{val}'"
                                )
                                break
                    elif tag == "DateTime":
                        r["fecha_creacion"] = str(val)
                    elif tag == "DateTimeDigitized":
                        r["fecha_modificacion"] = str(val)

            ela = self._ela_analysis(archivo_path, img)
            if ela:
                r["señales_sospechosas"].append(ela)

        except ImportError:
            r["señales_sospechosas"].append("Pillow no disponible — análisis de imagen omitido")
        except Exception as e:
            r["señales_sospechosas"].append(f"Error en análisis de imagen: {e}")

    def _ela_analysis(self, archivo_path: str, img) -> str | None:
        """
        Error Level Analysis simplificado.
        Recomprime el JPEG a calidad conocida y mide la diferencia pixel a pixel.
        Zonas editadas retienen menos compresión acumulada → pico de diferencia localizado.
        """
        try:
            from PIL import Image, ImageChops
            if img.format not in ("JPEG",):
                return None
            img_rgb = img.convert("RGB")
            buf = io.BytesIO()
            img_rgb.save(buf, format="JPEG", quality=95)
            buf.seek(0)
            recomp = Image.open(buf).convert("RGB")
            diff = ImageChops.difference(img_rgb, recomp)
            px = list(diff.getdata())
            vals = [math.sqrt(r**2 + g**2 + b**2) for r, g, b in px]
            avg = sum(vals) / len(vals)
            mx = max(vals)
            if mx > 55 and mx > avg * 9:
                return (
                    f"ELA: posible zona con edición digital detectada "
                    f"(distorsión localizada máx={mx:.1f} vs prom={avg:.2f})"
                )
        except Exception:
            pass
        return None

    # ─── CAPAS 2-4: Gemini multimodal ─────────────────────────────────────────

    def _analizar_forense_gemini(self, archivo_path: str, metadata: dict) -> dict:
        ext = Path(archivo_path).suffix.lower()
        mime_map = {
            ".pdf":  "application/pdf",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
            ".tiff": "image/tiff",
            ".tif":  "image/tiff",
        }
        mime = mime_map.get(ext, "application/octet-stream")

        with open(archivo_path, "rb") as f:
            file_bytes = f.read()

        señales_previas = metadata.get("señales_sospechosas", [])
        creador = metadata.get("creador_detectado", "Desconocido")

        prompt = f"""
Eres un experto en autenticación forense de documentos legales y financieros.

Metadatos locales ya extraídos (Capa 1):
- Software creador: {creador}
- Señales previas: {señales_previas if señales_previas else "ninguna"}

Analiza VISUALMENTE el documento adjunto con las siguientes capas:

CAPA 2 — TIPOGRAFÍA Y KERNING:
Verifica si el tipo de letra, tamaño y espaciado entre caracteres (kerning) es uniforme
en los campos críticos: Nombre, Número de Documento, Fechas y Montos.
Reporta cualquier zona donde la tipografía sea visualmente distinta al resto del documento
(ej: "Fuente sans-serif detectada sobre soporte oficial con fuente serif en campo Nombre").

CAPA 3 — ARTEFACTOS DE COMPRESIÓN Y PIXELES:
Busca parches visuales, bordes con halos de ruido diferente al fondo (efecto ELA visual),
desalineaciones en líneas de seguridad, guillochés o fondos de pantógrafo cortados o reemplazados.

CAPA 4 — DETECCIÓN DE IA Y PLANTILLAS FALSAS:
Identifica si el documento fue generado o alterado con IA generativa:
bordes de texto ligeramente difuminados, micro-textos que no son legibles o no tienen sentido,
firmas que carecen de presión de trazo variable, patrones de seguridad generados artificialmente.

REGLA: Reporta ÚNICAMENTE lo que puedes observar. Si el documento parece auténtico, indícalo.
No especules sobre intenciones, solo describe anomalías visuales concretas.

Devuelve ESTRICTAMENTE este JSON (sin texto adicional):
{{
    "documento_autentico": true o false,
    "score_confianza_antifraude": número entre 0.0 y 100.0,
    "anomalias_detectadas": ["descripción concreta de cada anomalía, o 'Sin anomalías detectadas'"]
}}
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part(inline_data=types.Blob(mime_type=mime, data=file_bytes)),
                types.Part(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        resultado = json.loads(response.text)
        resultado["metadata_local"] = metadata
        return resultado

    # ─── Investigación principal ──────────────────────────────────────────────

    def analizar_forense_standalone(self, archivo_path: str) -> dict:
        """Capa 1-4 forense sin investigación KYC. Para el módulo Análisis Forense."""
        metadata = self._analizar_metadatos_local(archivo_path)
        señales = metadata.get("señales_sospechosas", [])
        print(f"[FORENSE] Creador: {metadata['creador_detectado']} | Señales locales: {len(señales)}")

        if MOCK_MODE:
            return _mock_forense(os.path.basename(archivo_path), metadata)

        print("[FORENSE] Capas 2-4: Análisis multimodal con Gemini...")
        resultado = self._analizar_forense_gemini(archivo_path, metadata)
        print(f"[FORENSE] Score antifraude: {resultado.get('score_confianza_antifraude')}")
        return resultado

    def ejecutar_investigacion_profunda(self, datos_cliente: dict, archivo_path: str = None) -> dict:
        from database.local_cache import buscar_reporte_compliance, guardar_reporte_compliance

        # Cache hit solo si hay documento y el resultado previo no era simulado
        doc_id = datos_cliente.get("documento", "").strip()
        if not archivo_path and doc_id:
            cache = buscar_reporte_compliance(doc_id)
            if cache:
                if "SIMULADO" in str(cache.get("_modo", "")):
                    print("[CACHE] Resultado previo era SIMULADO — descartando, re-analizando con API real.")
                else:
                    print("[CACHE] Cliente encontrado. Retornando datos históricos locales.")
                    return cache

        # Capa 1 siempre local (gratis)
        metadata = None
        if archivo_path and os.path.exists(archivo_path):
            print("[FORENSE] Capa 1: Analizando metadatos del archivo...")
            metadata = self._analizar_metadatos_local(archivo_path)
            señales = metadata.get("señales_sospechosas", [])
            print(f"[FORENSE] Creador: {metadata['creador_detectado']} | Señales locales: {len(señales)}")

        if MOCK_MODE:
            print("[MOCK] Generando respuesta simulada (sin créditos Gemini)...")
            resultado = _mock_resultado(datos_cliente)
            if archivo_path:
                resultado["analisis_forense_documental"] = _mock_forense(
                    os.path.basename(archivo_path), metadata
                )
            guardar_reporte_compliance(datos_cliente["documento"], datos_cliente["nombre"], resultado)
            print("[DATABASE] Guardando reporte mock en base de datos local... [OK]")
            return resultado

        # ── Llamada 1: KYC con Google Search ──────────────────────────────────
        print("[API GEMINI] Iniciando rastreo KYC transfronterizo...")

        doc_str    = datos_cliente.get('documento', '').strip() or "No proporcionado"
        paises_raw = datos_cliente.get('paises_clave', [])
        paises_str = ", ".join([p for p in paises_raw if p]) or "No especificados — rastrear por nacionalidad"

        kyc_prompt = f"""
Eres un Agente de Inteligencia Financiera Avanzado y Compliance Legal.
Tu misión es investigar a la siguiente persona natural y construir su árbol de riesgo:

- Nombre Completo: {datos_cliente['nombre']}
- Documento/Pasaporte: {doc_str}
- Nacionalidad: {datos_cliente['nacionalidad']}
- Países con intereses comerciales declarados: {paises_str}

INSTRUCCIONES OBLIGATORIAS:
1. Usa Google Search para rastrear nombre + documento en el país de origen.
2. Si encuentras vinculaciones en otros países (gacetas, registros de comercio), expande la búsqueda
   para identificar: empresas asociadas, socios, activos, vínculos con PEPs.
3. Contrasta con listas OFAC, ONU, antecedentes de lavado de activos o crimen organizado.
4. Descarta homónimos que no coincidan con documento o perfil.

REGLA CRÍTICA — "resumen_ejecutivo":
- Solo hechos constatados: qué se encontró, dónde y cuándo.
- PROHIBIDO: recomendaciones, juicios de valor, frases como "se recomienda" o "se sugiere".

Genera JSON estrictamente con esta estructura:
{{
    "status_evaluacion": "APROBADO" | "ALERTA_RIESGO" | "BLOQUEADO",
    "resumen_ejecutivo": "...",
    "empresas_vinculadas": [{{"nombre_empresa": "...", "pais": "...", "socios_detectados": ["..."]}}],
    "alertas_ofac_crimen": ["..."],
    "paises_rastreados_efectivos": ["..."]
}}
"""

        kyc_response = self.client.models.generate_content(
            model=self.model_name,
            contents=kyc_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            ),
        )
        raw = kyc_response.text.strip()
        import re as _re
        m = _re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        resultado = json.loads(m.group(1) if m else raw)

        # ── Llamada 2: Forense multimodal (si hay archivo) ─────────────────────
        if archivo_path and os.path.exists(archivo_path):
            print("[FORENSE] Capas 2-4: Analizando documento con Gemini multimodal...")
            forense = self._analizar_forense_gemini(archivo_path, metadata)
            resultado["analisis_forense_documental"] = forense
            print(f"[FORENSE] Score antifraude: {forense.get('score_confianza_antifraude')}")

        cache_key = datos_cliente.get("documento", "").strip() or datos_cliente["nombre"]
        guardar_reporte_compliance(cache_key, datos_cliente["nombre"], resultado)
        print("[DATABASE] Nuevo reporte guardado en base de datos local. [OK]")
        return resultado


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    cliente_test = {
        "nombre": "Juan Ramón Pérez Sosa",
        "documento": "1.234.567-8",
        "nacionalidad": "Argentino",
        "paises_clave": ["Argentina", "Uruguay", "Suecia"],
    }

    api_key = os.getenv("GEMINI_API_KEY", "")
    agent = QuantumComplianceAgent(api_key=api_key)
    print("Iniciando investigación de prueba...\n")
    resultado = agent.ejecutar_investigacion_profunda(cliente_test)
    print("\n=== RESULTADO ===")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
