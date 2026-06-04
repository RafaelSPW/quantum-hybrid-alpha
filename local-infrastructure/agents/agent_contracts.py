import os
import sys
import json
from pathlib import Path
from google import genai
from google.genai import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_MODE = False


def _mock_contrato(contexto: dict) -> dict:
    rol = contexto.get("rol_cliente", "Prestador de Servicios")
    return {
        "tipo_contrato": "Contrato de Prestación de Servicios Profesionales [MOCK]",
        "partes_detectadas": [
            {"nombre": "Grupo Financiero Meridional S.A.", "rol": "Contratante"},
            {"nombre": "Asesor Profesional Independiente", "rol": rol},
        ],
        "resumen_ejecutivo": (
            "Contrato de consultoría financiera por 12 meses. Se identificaron dos cláusulas de "
            "riesgo ALTO (penalidad de rescisión del 30% y cesión irrestricta de propiedad intelectual), "
            "un vacío crítico en materia de resolución de disputas y ausencia de cláusula de confidencialidad. "
            "El plazo de pago de 60 días supera el estándar de mercado (30 días) sin previsión de intereses por mora."
        ),
        "clausulas_problematicas": [
            {
                "clausula": "Cláusula 8.2 — Penalidad por Rescisión Anticipada",
                "texto_detectado": "En caso de rescisión anticipada por parte del Prestador, este deberá abonar el 30% del monto total restante del contrato.",
                "riesgo": "Penalidad desproporcionada. No contempla rescisión justificada por incumplimiento del Contratante como causa eximente.",
                "severidad": "ALTA",
            },
            {
                "clausula": "Cláusula 12.1 — Cesión de Propiedad Intelectual",
                "texto_detectado": "Todo producto, metodología o desarrollo generado durante la relación contractual pertenecerá exclusivamente al Contratante a partir de la firma.",
                "riesgo": "Redacción excesivamente amplia. Puede incluir metodologías y herramientas preexistentes del Prestador desarrolladas antes del contrato.",
                "severidad": "ALTA",
            },
            {
                "clausula": "Cláusula 5.3 — Plazo de Pago",
                "texto_detectado": "El Contratante abonará los honorarios dentro de los 60 días corridos de recibida la factura.",
                "riesgo": "Plazo superior al estándar de mercado (30 días). Sin tasa de interés por mora definida.",
                "severidad": "MEDIA",
            },
        ],
        "vacios_legales": [
            "No se especifica mecanismo de resolución de disputas (mediación, arbitraje o sede judicial).",
            "Ausencia de cláusula de confidencialidad para información sensible compartida durante la ejecución.",
            "No se define qué ocurre con los trabajos en curso si el contrato se rescinde de forma unilateral.",
        ],
        "riesgos_comerciales": [
            "La penalidad del 30% sobre el saldo restante puede representar una cifra elevada en contratos largos.",
            "El plazo de pago de 60 días puede generar tensión de flujo de caja para el Prestador.",
            "Sin límite de responsabilidad (liability cap) establecido para ninguna de las partes.",
        ],
        "clausulas_favorables": [
            "Cláusula 3.1: Entregables definidos con criterios de aceptación objetivos y medibles.",
            "Cláusula 9.2: El Contratante debe proveer acceso a información en un plazo máximo de 5 días hábiles.",
        ],
        "recomendacion_general": "REVISAR_ANTES",
        "_modo": "SIMULADO — activar MOCK_MODE=False cuando haya saldo Gemini",
    }


def _mock_comparacion() -> dict:
    return {
        "resumen_cambios": (
            "Se detectaron 3 cláusulas modificadas, 2 cláusulas nuevas y 1 cláusula eliminada respecto al contrato original. "
            "Los cambios más relevantes incluyen el aumento de la penalidad por rescisión del 20% al 30%, la eliminación de la "
            "cláusula de confidencialidad y la incorporación de una nueva cláusula de arbitraje obligatorio. "
            "Se recomienda negociar antes de firmar."
        ),
        "recomendacion": "NEGOCIAR",
        "clausulas_modificadas": [
            {
                "clausula": "Cláusula 8.2 — Penalidad por Rescisión",
                "texto_original": "En caso de rescisión anticipada, el Prestador abonará el 20% del monto restante.",
                "texto_nuevo": "En caso de rescisión anticipada, el Prestador abonará el 30% del monto total restante del contrato.",
                "descripcion": "La penalidad aumentó un 50%. El cambio de 'monto restante' a 'monto total' puede implicar una base de cálculo significativamente mayor.",
                "impacto": "DESFAVORABLE",
            },
            {
                "clausula": "Cláusula 5.3 — Plazo de Pago",
                "texto_original": "El pago se realizará dentro de los 30 días de recibida la factura.",
                "texto_nuevo": "El pago se realizará dentro de los 45 días corridos de recibida la factura.",
                "descripcion": "El plazo de pago se extendió de 30 a 45 días, lo que impacta negativamente el flujo de caja del Prestador.",
                "impacto": "DESFAVORABLE",
            },
            {
                "clausula": "Cláusula 3.1 — Entregables",
                "texto_original": "Los entregables serán aprobados por el Contratante en un plazo de 10 días hábiles.",
                "texto_nuevo": "Los entregables serán aprobados por el Contratante en un plazo de 5 días hábiles.",
                "descripcion": "Reducción del plazo de aprobación de 10 a 5 días. Este cambio es favorable al Prestador ya que acelera los ciclos de pago.",
                "impacto": "FAVORABLE",
            },
        ],
        "clausulas_agregadas": [
            {
                "clausula": "Cláusula 15.1 — Arbitraje Obligatorio",
                "texto": "Toda controversia que surja del presente contrato será resuelta mediante arbitraje ante el Centro de Arbitraje y Mediación de la Cámara de Comercio, con sede en la ciudad del Contratante.",
                "impacto": "NEUTRAL",
            },
            {
                "clausula": "Cláusula 16.2 — Cesión de Contrato",
                "texto": "El Contratante podrá ceder el presente contrato a cualquier empresa vinculada o subsidiaria sin necesidad de consentimiento previo del Prestador.",
                "impacto": "DESFAVORABLE",
            },
        ],
        "clausulas_eliminadas": [
            {
                "clausula": "Cláusula 11.0 — Confidencialidad",
                "texto": "Ambas partes se comprometen a mantener la confidencialidad de toda información intercambiada durante la vigencia del contrato y por 2 años posteriores.",
                "impacto": "DESFAVORABLE",
            },
        ],
        "_modo": "SIMULADO — activar MOCK_MODE=False cuando haya saldo Gemini",
    }


class QuantumContractsAgent:
    def __init__(self, api_key: str):
        if not MOCK_MODE:
            self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def analizar_contrato(self, archivo_path: str, contexto: dict) -> dict:
        if MOCK_MODE:
            print("[MOCK] Generando análisis de contrato simulado...")
            resultado = _mock_contrato(contexto)
            print("[CONTRACTS] Análisis mock generado. [OK]")
            return resultado

        ext  = Path(archivo_path).suffix.lower()
        mime = "application/pdf" if ext == ".pdf" else "image/jpeg"
        with open(archivo_path, "rb") as f:
            file_bytes = f.read()

        rol     = contexto.get("rol_cliente", "no especificado")
        notas   = contexto.get("notas_adicionales", "").strip()
        notas_s = f"\nContexto adicional del asesor: {notas}" if notas else ""

        prompt = f"""
Eres un abogado corporativo senior especializado en contratos comerciales, financieros e inmobiliarios.
Tu cliente es la parte que actúa como: {rol}.{notas_s}

Analiza el contrato adjunto EN SU TOTALIDAD. Usa tu ventana de contexto completa para no omitir ninguna cláusula.

IDENTIFICA Y REPORTA:
1. CLÁUSULAS PROBLEMÁTICAS: Condiciones leoninas, abusivas o que favorezcan desproporcionadamente a la contraparte.
   Para cada una: número/nombre de cláusula, fragmento del texto original, descripción del riesgo, severidad (ALTA/MEDIA/BAJA).
2. VACÍOS LEGALES: Situaciones no cubiertas que podrían generar conflictos interpretativos o dejar desprotegida a tu parte.
3. RIESGOS COMERCIALES: Compromisos económicos, plazos de pago, penalidades, garantías onerosas o condiciones de renovación automática.
4. CLÁUSULAS FAVORABLES: Disposiciones que protegen o benefician a tu cliente (el rol indicado).

REGLA: Reporta únicamente lo que está en el texto. No inventes cláusulas. Si el contrato es equilibrado, indícalo.

Responde ESTRICTAMENTE en JSON con esta estructura:
{{
    "tipo_contrato": "descripción breve del tipo de contrato",
    "partes_detectadas": [{{"nombre": "...", "rol": "..."}}],
    "resumen_ejecutivo": "resumen factual de los hallazgos principales en 3-4 oraciones",
    "clausulas_problematicas": [
        {{
            "clausula": "identificador o nombre",
            "texto_detectado": "fragmento textual del contrato",
            "riesgo": "descripción del riesgo para el cliente",
            "severidad": "ALTA | MEDIA | BAJA"
        }}
    ],
    "vacios_legales": ["descripción concreta de cada vacío"],
    "riesgos_comerciales": ["descripción de cada riesgo comercial"],
    "clausulas_favorables": ["descripción de cada cláusula favorable"],
    "recomendacion_general": "FIRMAR | REVISAR_ANTES | NO_FIRMAR"
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
        print("[CONTRACTS] Análisis completado por Gemini. [OK]")
        return resultado

    def analizar_contratos_comparativos(self, archivo1_path: str, archivo2_path: str, contexto: dict) -> dict:
        if MOCK_MODE:
            print("[MOCK] Generando comparación de contratos simulada...")
            resultado = _mock_comparacion()
            print("[CONTRACTS] Comparación mock generada. [OK]")
            return resultado

        def _leer(path):
            ext  = Path(path).suffix.lower()
            mime = "application/pdf" if ext == ".pdf" else "image/jpeg"
            with open(path, "rb") as f:
                return f.read(), mime

        bytes1, mime1 = _leer(archivo1_path)
        bytes2, mime2 = _leer(archivo2_path)

        rol   = contexto.get("rol_cliente", "no especificado")
        notas = contexto.get("notas_adicionales", "").strip()
        notas_s = f"\nContexto adicional: {notas}" if notas else ""

        prompt = f"""
Eres un abogado corporativo senior especializado en contratos comerciales.
Tu cliente actúa como: {rol}.{notas_s}

Se te proporcionan DOS versiones del mismo contrato:
- DOCUMENTO 1: Contrato Original (el que tu cliente envió o recibió inicialmente)
- DOCUMENTO 2: Contrato Modificado (la versión devuelta por la contraparte)

TAREA: Compara ambos documentos cláusula por cláusula e identifica EXACTAMENTE qué cambió.

DETECTA Y REPORTA:
1. CLÁUSULAS MODIFICADAS: Cláusulas que existen en ambas versiones pero con texto diferente. Para cada una: nombre/número, texto exacto original, texto exacto nuevo, descripción del impacto, e impacto (FAVORABLE / DESFAVORABLE / NEUTRAL para el cliente).
2. CLÁUSULAS AGREGADAS: Cláusulas que aparecen en el documento 2 pero NO en el documento 1. Texto completo e impacto.
3. CLÁUSULAS ELIMINADAS: Cláusulas que aparecen en el documento 1 pero fueron REMOVIDAS del documento 2. Texto original e impacto.
4. RESUMEN DE CAMBIOS: Síntesis ejecutiva de los cambios detectados (3-4 oraciones).
5. RECOMENDACIÓN: ACEPTAR (cambios menores o favorables), NEGOCIAR (cambios significativos que requieren ajuste) o RECHAZAR (cambios gravemente perjudiciales).

REGLA: Reporta solo diferencias reales. Si un texto es idéntico, no lo menciones.

Responde ESTRICTAMENTE en JSON con esta estructura:
{{
    "resumen_cambios": "síntesis ejecutiva de los cambios",
    "recomendacion": "ACEPTAR | NEGOCIAR | RECHAZAR",
    "clausulas_modificadas": [
        {{
            "clausula": "identificador o nombre de la cláusula",
            "texto_original": "texto exacto del documento 1",
            "texto_nuevo": "texto exacto del documento 2",
            "descripcion": "descripción del impacto del cambio para el cliente",
            "impacto": "FAVORABLE | DESFAVORABLE | NEUTRAL"
        }}
    ],
    "clausulas_agregadas": [
        {{
            "clausula": "identificador o nombre",
            "texto": "texto completo de la cláusula agregada",
            "impacto": "FAVORABLE | DESFAVORABLE | NEUTRAL"
        }}
    ],
    "clausulas_eliminadas": [
        {{
            "clausula": "identificador o nombre",
            "texto": "texto completo de la cláusula eliminada",
            "impacto": "FAVORABLE | DESFAVORABLE | NEUTRAL"
        }}
    ]
}}
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part(inline_data=types.Blob(mime_type=mime1, data=bytes1)),
                types.Part(inline_data=types.Blob(mime_type=mime2, data=bytes2)),
                types.Part(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        resultado = json.loads(response.text)
        print("[CONTRACTS] Comparación completada por Gemini. [OK]")
        return resultado


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    contexto_test = {
        "rol_cliente": "Prestador de Servicios",
        "notas_adicionales": "Contrato recibido de potencial cliente corporativo. Revisar penalidades.",
    }

    agent = QuantumContractsAgent(api_key=os.getenv("GEMINI_API_KEY", ""))
    print("Iniciando análisis de contrato de prueba (MOCK)...\n")
    resultado = agent.analizar_contrato("contrato_test.pdf", contexto_test)
    print("\n=== RESULTADO ===")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
