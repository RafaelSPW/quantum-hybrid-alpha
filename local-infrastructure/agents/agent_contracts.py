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
