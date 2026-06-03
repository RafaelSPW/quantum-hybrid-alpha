import os
import re
import json
from google import genai
from google.genai import types

MOCK_MODE = False


def _parse_json(text: str) -> dict:
    """Extrae JSON de la respuesta aunque venga envuelto en markdown code blocks."""
    text = text.strip()
    # Quitar bloques ```json ... ``` o ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)

SYSTEM_STRATEGY = """
Eres un Consultor Senior de Portafolios de AHC Intelligence, especializado en diseño de estrategias de asignación de activos para clientes institucionales y de alto patrimonio.

TU ROL:
- Guiar al asesor en el diseño de una estrategia óptima de portafolio para su cliente.
- Cruzar los parámetros del cliente con el análisis macroeconómico actual del mercado.
- Generar propuestas de asignación de activos concretas con porcentajes y justificación.

ACTIVOS QUE MANEJAS: Oro (XAU/USD), Forex (pares principales y emergentes), Bonos soberanos y corporativos, Commodities.

REGLAS:
- Respondé en español, de forma profesional y directa.
- Usá negrita (**texto**) para resaltar proporciones, activos y cifras clave.
- Si te faltan datos, pedí solo lo que falta — no hagas múltiples preguntas a la vez.
- Cuando tenés capital, horizonte y tolerancia al riesgo: generá la asignación con porcentajes concretos.
- Podés ajustar la estrategia si el asesor da feedback o cambian los parámetros.
- NUNCA garantices rendimientos específicos ni prometás resultados.
- Finalizá cada respuesta con: *Análisis de referencia — no constituye asesoramiento financiero formal.*
"""

_MOCK_STRATEGY = [
    "Bienvenido al **Configurador de Portafolios — AHC Intelligence**.\n\nPara diseñar la estrategia óptima, necesito tres datos clave:\n\n1. **Capital disponible** (en USD)\n2. **Horizonte de inversión** (ej: 12 meses, 3 años)\n3. **Objetivo de retorno o nivel de riesgo** que el cliente está dispuesto a asumir\n\nPodés darme todo en un solo mensaje o ir respondiendo de a uno.\n\n*Análisis de referencia — no constituye asesoramiento financiero formal.*",
    "Con esos parámetros y el contexto de mercado actual, propongo la siguiente **asignación de activos**:\n\n- 🟡 **40% Oro (XAU/USD)** — Refugio ante inflación persistente y tensiones geopolíticas. Soportes técnicos sólidos en zona de acumulación.\n- 📊 **35% Bonos del Tesoro 2Y-5Y** — Tasa real positiva con baja volatilidad. Ideal para anclar el portafolio en escenario de soft landing.\n- 💱 **25% Forex — EURUSD estrategia de rango** — Par con baja volatilidad histórica, adecuado para estrategias de rango en contexto de convergencia de tasas.\n\n**Retorno proyectado:** 7–9% anual | **Drawdown máximo estimado:** 8–12%\n\n¿Querés que profundice en la entrada de alguno de estos activos, o ajusto la composición por alguna restricción adicional?\n\n*Análisis de referencia — no constituye asesoramiento financiero formal.*",
    "Ajustando la estrategia según los nuevos parámetros:\n\nDado el horizonte revisado, sugiero **reducir la exposición a Forex** (mayor incertidumbre ante datos macro) y **aumentar Bonos al 45%** para preservar capital.\n\n**Composición revisada:**\n- 🟡 **35% Oro** — Sin cambios. Mantiene función de cobertura.\n- 📊 **45% Bonos corto plazo** — Aumentado para anclar el portafolio.\n- 💱 **20% EURUSD** — Reducido. Stop en zona de soporte técnico.\n\n¿Hay algún ajuste adicional o pasamos al informe final?\n\n*Análisis de referencia — no constituye asesoramiento financiero formal.*",
]

_MOCK_ASSET = {
    "activo_consultado": "EUR/USD [SIMULADO]",
    "precio_referencia": "1.0842 — 3 Jun 2026",
    "contexto_tecnico": {
        "tendencia": "Lateral con sesgo bajista de corto plazo",
        "soporte_clave": "1.0780",
        "resistencia_clave": "1.0920",
        "volatilidad": "Moderada — ATR(14): 0.0062",
        "analisis": "El par se encuentra comprimido en rango 140 pips entre 1.0780 y 1.0920. RSI(14) en 47 confirma neutralidad. Sin catalizador, el sesgo es lateral con mayor probabilidad de ruptura bajista ante la divergencia de tasas vigente.",
    },
    "contexto_fundamental": {
        "tasas_interes": "BCE: 3.75% | FED: 5.25–5.50% — Diferencial favorable al USD",
        "eventos_macro": [
            "Datos de empleo USA (viernes) — impacto alto",
            "Declaraciones BCE pendientes — impacto medio",
            "IPC Eurozona pendiente de publicación",
        ],
        "analisis": "La diferencia de tasas sigue favoreciendo al dólar. El mercado descuenta 1–2 recortes de la FED para fin de año. El BCE mantiene postura más restrictiva en su comunicación.",
    },
    "matriz_riesgo_retorno": {
        "escenario_base": "Rango 1.0780–1.0920 por 2 semanas más. Captura: ±60 pips.",
        "escenario_alcista": "Ruptura 1.0920 → 1.1050 si datos USA decepcionan. Probabilidad: 30%.",
        "escenario_bajista": "Ruptura 1.0780 → 1.0680 si nóminas superan expectativas. Probabilidad: 35%.",
        "ratio_riesgo_retorno": "1.5:1 en estrategia de rango — 1.2:1 en breakout",
    },
    "veredicto": "ESPERAR",
    "conclusion": "Posición de espera recomendada hasta conocer los datos de empleo del viernes. Gestión activa del rango 1.0780–1.0920 para operadores intradía. Breakout traders: aguardar confirmación de cierre semanal fuera del rango antes de operar.",
    "advertencias": [
        "Alta sensibilidad a publicaciones macro USA esta semana",
        "Liquidez puede reducirse antes de publicaciones importantes",
        "No operar sin stop definido en contexto de alta volatilidad potencial",
    ],
    "_modo": "SIMULADO",
}

_MOCK_AUDIT = {
    "resumen_ejecutivo": "La cartera presenta concentración excesiva en activos de volatilidad media-alta (60%) para un perfil de mediano plazo. El Oro está sobreponderado cerca de máximos históricos y la exposición Forex carece de cobertura explícita. Existen oportunidades claras de optimización.",
    "score_salud_cartera": 64.5,
    "alertas_desviacion": [
        {
            "activo": "XAU/USD",
            "problema": "Sobreponderado",
            "descripcion": "30% de exposición en Oro es elevada para mediano plazo. El activo cotiza cerca de máximos históricos, reduciendo el potencial upside vs. el riesgo de corrección técnica.",
            "severidad": "MEDIA",
        },
        {
            "activo": "EUR/USD",
            "problema": "Sin cobertura de volatilidad",
            "descripcion": "Posición Forex del 20% sin niveles de stop definidos ni cobertura de divisa. Riesgo de drawdown significativo ante eventos macro no anticipados.",
            "severidad": "ALTA",
        },
    ],
    "propuesta_rebalanceo": [
        {
            "accion": "REDUCIR",
            "activo": "XAU/USD",
            "cambio": "−10% (de 30% a 20%)",
            "razon": "Reducir concentración cerca de máximos históricos. Reasignar a bonos de mayor rendimiento para anclar el portafolio.",
        },
        {
            "accion": "AUMENTAR",
            "activo": "Bonos Tesoro 2Y–5Y",
            "cambio": "+15% (de 50% a 65%)",
            "razon": "Anclar cartera con tasa real positiva. Menor volatilidad para objetivo de mediano plazo en contexto de soft landing.",
        },
        {
            "accion": "MANTENER",
            "activo": "EUR/USD",
            "cambio": "20% — definir stop en 1.0750",
            "razon": "Par en rango técnico estructural. Mantener exposición pero con gestión de riesgo activa y stop documentado.",
        },
    ],
    "composicion_sugerida": [
        {"activo": "Bonos Tesoro 2Y–5Y", "porcentaje": "65%"},
        {"activo": "XAU/USD", "porcentaje": "15%"},
        {"activo": "EUR/USD", "porcentaje": "20%"},
    ],
    "conclusion_macro": "En el contexto macro actual (tasas altas, inflación moderándose, incertidumbre geopolítica activa), la cartera optimizada prioriza preservación de capital con generación de renta fija positiva, manteniendo exposición limitada a activos de refugio y divisas con riesgo controlado.",
    "_modo": "SIMULADO",
}

_mock_strategy_idx = 0


class QuantumMarketsAgent:
    def __init__(self, api_key: str):
        if not MOCK_MODE:
            self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-pro"

    # ── 02-A: Diseñador de Estrategias (Conversacional) ──────────────────────

    def disenar_estrategia(self, historial: list, mensaje: str) -> str:
        global _mock_strategy_idx
        if MOCK_MODE:
            resp = _MOCK_STRATEGY[_mock_strategy_idx % len(_MOCK_STRATEGY)]
            _mock_strategy_idx += 1
            return resp

        contents = []
        for msg in historial:
            role = "user" if msg["rol"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["texto"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=mensaje)]))

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_STRATEGY,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            ),
        )
        return response.text.strip()

    # ── 02-B: Analizador Clínico de Activos ────────────────────────────────

    def analizar_activo(self, consulta: str) -> dict:
        if MOCK_MODE:
            return _MOCK_ASSET

        prompt = f"""
Eres un analista de mesa de dinero senior especializado en Oro, Forex y Bonos soberanos.
Usá Google Search para obtener datos de mercado actuales.

CONSULTA DEL ASESOR: {consulta}

Analizá en tres capas:

CAPA 1 — CONTEXTO TÉCNICO: Precio actual, tendencia, soportes/resistencias clave, volatilidad (ATR si disponible), señales de indicadores relevantes.

CAPA 2 — CONTEXTO FUNDAMENTAL: Tasas de interés relevantes, eventos macro próximos, posicionamiento institucional, factores geopolíticos.

CAPA 3 — MATRIZ RIESGO/RETORNO: Tres escenarios (base, alcista, bajista) con probabilidades y ratio riesgo/retorno estimado.

VEREDICTO FINAL: Una palabra — COMPRAR, ESPERAR, VENDER o NEUTRAL.

REGLA: Solo hechos y datos verificables. No garantices rendimientos. Indicá que es orientación de referencia.

Responde ESTRICTAMENTE en JSON:
{{
    "activo_consultado": "nombre del activo analizado",
    "precio_referencia": "precio actual con fecha",
    "contexto_tecnico": {{
        "tendencia": "...",
        "soporte_clave": "...",
        "resistencia_clave": "...",
        "volatilidad": "...",
        "analisis": "párrafo de análisis técnico"
    }},
    "contexto_fundamental": {{
        "tasas_interes": "...",
        "eventos_macro": ["evento 1", "evento 2"],
        "analisis": "párrafo de análisis fundamental"
    }},
    "matriz_riesgo_retorno": {{
        "escenario_base": "...",
        "escenario_alcista": "...",
        "escenario_bajista": "...",
        "ratio_riesgo_retorno": "..."
    }},
    "veredicto": "COMPRAR|ESPERAR|VENDER|NEUTRAL",
    "conclusion": "párrafo de conclusión ejecutiva",
    "advertencias": ["advertencia 1", "advertencia 2"]
}}
"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        return _parse_json(response.text)

    # ── 02-C: Auditor de Carteras ───────────────────────────────────────────

    def auditar_cartera(self, composicion: str, plazo: str, notas: str) -> dict:
        if MOCK_MODE:
            return _MOCK_AUDIT

        notas_s = f"\nContexto adicional: {notas}" if notas.strip() else ""
        prompt = f"""
Eres un gestor de riesgos senior especializado en auditoría de portafolios de inversión.
Usá Google Search para obtener el contexto de mercado actual de cada activo en la cartera.

COMPOSICIÓN ACTUAL DE LA CARTERA:
{composicion}

PLAZO DE INVERSIÓN: {plazo}{notas_s}

AUDITÁ la cartera en tres pasos:

1. ALERTAS DE DESVIACIÓN: ¿Hay activos sobreponderados o infraponderados para el plazo? ¿Alguno genera riesgo excesivo en el contexto actual?

2. PROPUESTA DE REBALANCEO: Acciones concretas (REDUCIR/AUMENTAR/MANTENER/LIQUIDAR) con porcentajes y justificación macro.

3. SCORE DE SALUD (0–100): Basado en diversificación, alineación con el plazo, riesgo concentrado y coherencia macroeconómica.

REGLA: Solo ajustes justificados por datos reales. No garantices rendimientos. Orientación de referencia.

Responde ESTRICTAMENTE en JSON:
{{
    "resumen_ejecutivo": "3–4 oraciones sobre el estado actual de la cartera",
    "score_salud_cartera": número entre 0 y 100,
    "alertas_desviacion": [
        {{
            "activo": "...",
            "problema": "Sobreponderado|Infraponderado|Sin cobertura|Fuera de plazo",
            "descripcion": "...",
            "severidad": "ALTA|MEDIA|BAJA"
        }}
    ],
    "propuesta_rebalanceo": [
        {{
            "accion": "REDUCIR|AUMENTAR|MANTENER|LIQUIDAR",
            "activo": "...",
            "cambio": "descripción del cambio con porcentaje",
            "razon": "justificación basada en mercado actual"
        }}
    ],
    "composicion_sugerida": [
        {{"activo": "...", "porcentaje": "..."}}
    ],
    "conclusion_macro": "párrafo sobre el contexto macro que justifica los cambios propuestos"
}}
"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        return _parse_json(response.text)

    def consultar_estrategia(self, parametros: dict) -> dict:
        """Mantenido por compatibilidad con tareas antiguas."""
        consulta = (
            f"Analiza {parametros.get('activo', 'Oro')} para un perfil "
            f"{parametros.get('perfil_riesgo', 'Moderado')}, "
            f"capital USD {parametros.get('monto_usd', 10000):,}, "
            f"horizonte {parametros.get('horizonte', '12 meses')}."
        )
        return self.analizar_activo(consulta)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    agent = QuantumMarketsAgent(api_key=os.getenv("GEMINI_API_KEY", ""))
    print("=== TEST 02-B: Analizador Clínico ===")
    r = agent.analizar_activo("Analiza el panorama actual del EURUSD para los próximos 15 días")
    print(json.dumps(r, indent=2, ensure_ascii=False))
