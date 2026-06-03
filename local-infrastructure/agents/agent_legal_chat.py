import os
import sys
import json
from pathlib import Path
from google import genai
from google.genai import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_MODE = False

SYSTEM_INSTRUCTION = """
Eres una herramienta de referencia regulatoria y normativa especializada en compliance financiero, derecho comercial y regulación de mercados.
Tu función es ayudar a asesores y profesionales a comprender el contenido de normas, leyes, circulares y reglamentos.

REGLAS DE COMPORTAMIENTO:
- Respondé en español, de forma clara, estructurada y profesional.
- Si hay un documento adjunto, analizalo y citá artículos, secciones o cláusulas con su identificador exacto.
- Si la pregunta no tiene respuesta en el documento, indicalo claramente antes de responder desde tu base de conocimiento general.
- No inventes artículos, secciones ni referencias que no existan en el documento.
- Siempre aclará que tus respuestas son orientación informativa de referencia, no asesoramiento legal ni regulatorio formal.
- Si identificás un punto relevante que el usuario no consultó, mencionalo brevemente como "Punto a considerar".
- Mantené el contexto de la conversación entre turnos.
- NUNCA uses frases como "como tu asesor legal" o "te recomiendo legalmente". Usá frases como "según la normativa", "el artículo X establece", "a modo de referencia".
"""

MOCK_RESPONSES = [
    "He analizado el documento adjunto. El contrato contiene disposiciones estándar para este tipo de acuerdo, aunque identifico algunas áreas que merecen atención.\n\nEn cuanto a tu consulta específica: la cláusula relevante establece las condiciones bajo las cuales aplica la penalidad. Lo que me llama la atención es que no hay un límite de responsabilidad definido para ninguna de las partes, lo cual deja expuesto al cliente ante reclamaciones de montos indeterminados.\n\n**Nota adicional:** La cláusula de renovación automática (si existe) debería revisarse para confirmar que hay un plazo de notificación de no renovación adecuado. [SIMULADO]",
    "Basándome en el documento que compartiste, puedo responderte lo siguiente:\n\nEsa cláusula es típica en contratos de este tipo, pero la redacción actual es más amplia de lo estándar. El problema no es la figura en sí, sino que no especifica excepciones para casos de fuerza mayor o incumplimiento previo de la contraparte.\n\nEn la práctica, eso significa que incluso si la contraparte incumple primero, tu cliente podría verse obligado a cumplir o pagar penalidades. Recomendaría agregar una cláusula de 'incumplimiento previo como causa eximente'. [SIMULADO]",
    "Entendido. Revisando el documento en ese punto específico:\n\nEl artículo que mencionás establece la jurisdicción y ley aplicable. La elección de ley uruguaya es favorable para tu cliente si opera en Uruguay, pero si la contraparte es extranjera, podrías negociar añadir arbitraje internacional (CIADI o ICC) como mecanismo alternativo, lo cual suele ser más eficiente en disputas transfronterizas.\n\n¿Querés que analice alguna otra sección del contrato? [SIMULADO]",
]

_mock_idx = 0


def _mock_respuesta(mensaje: str) -> str:
    global _mock_idx
    resp = MOCK_RESPONSES[_mock_idx % len(MOCK_RESPONSES)]
    _mock_idx += 1
    return resp


class QuantumLegalChatAgent:
    def __init__(self, api_key: str):
        if not MOCK_MODE:
            self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def responder(self, mensaje: str, historial: list, archivo_path: str = None) -> str:
        """
        Genera una respuesta conversacional.
        historial: lista de { "rol": "user"|"assistant", "texto": str }
        archivo_path: ruta local del documento de contexto (opcional)
        """
        if MOCK_MODE:
            print("[MOCK] Generando respuesta de asesor legal simulada...")
            return _mock_respuesta(mensaje)

        # Construir el mensaje inicial con el documento (si existe)
        first_parts = []
        if archivo_path and os.path.exists(archivo_path):
            ext  = Path(archivo_path).suffix.lower()
            mime_map = {
                ".pdf":  "application/pdf",
                ".jpg":  "image/jpeg", ".jpeg": "image/jpeg",
                ".png":  "image/png",
                ".txt":  "text/plain",
            }
            mime = mime_map.get(ext, "application/octet-stream")
            with open(archivo_path, "rb") as f:
                file_bytes = f.read()
            first_parts.append(types.Part(inline_data=types.Blob(mime_type=mime, data=file_bytes)))
            first_parts.append(types.Part(text="[Documento adjunto para análisis. El usuario realizará consultas sobre este documento.]"))

        # Construir historial de conversación en formato Gemini
        contents = []

        # Si hay documento, va como primer mensaje del usuario
        if first_parts:
            if historial and historial[0]["rol"] == "user":
                # Adjuntar el doc al primer mensaje real del usuario
                first_user_text = historial[0]["texto"]
                first_parts.append(types.Part(text=first_user_text))
                contents.append(types.Content(role="user", parts=first_parts))
                historial_resto = historial[1:]
            else:
                # Doc solo, sin primer mensaje de historial
                contents.append(types.Content(role="user", parts=first_parts))
                contents.append(types.Content(role="model", parts=[types.Part(text="Documento recibido. Estoy listo para responder tus consultas sobre este documento.")]))
                historial_resto = historial
        else:
            historial_resto = historial

        # Agregar el resto del historial
        for msg in historial_resto:
            role = "user" if msg["rol"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["texto"])]))

        # Mensaje actual del usuario
        contents.append(types.Content(role="user", parts=[types.Part(text=mensaje)]))

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
            ),
        )

        return response.text.strip()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    agent = QuantumLegalChatAgent(api_key=os.getenv("GEMINI_API_KEY", ""))
    print("Asesor Legal — prueba conversacional (MOCK)\n")

    historial = []
    preguntas = [
        "¿Qué tipo de contrato es este y cuáles son las partes?",
        "¿Hay alguna cláusula de renovación automática?",
        "¿Qué pasa si el cliente quiere rescindirlo antes del plazo?",
    ]
    for p in preguntas:
        print(f"USUARIO: {p}")
        resp = agent.responder(p, historial)
        print(f"ASESOR: {resp}\n")
        historial.append({"rol": "user", "texto": p})
        historial.append({"rol": "assistant", "texto": resp})
