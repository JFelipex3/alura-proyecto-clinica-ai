from __future__ import annotations

import os
from typing import Any, Dict, List

import google.generativeai as genai

_SYSTEM = """Eres el asistente virtual oficial de la Clínica Bienestar Integral.
Tu función es ayudar a pacientes y colaboradores respondiendo preguntas basándote
EXCLUSIVAMENTE en los documentos internos de la clínica que se te proporcionan como contexto.

Reglas estrictas:
1. Responde SOLO con información que esté en el contexto proporcionado.
2. Si la información no está en los documentos, dilo con claridad:
   "No encontré esa información en nuestra documentación. Te recomiendo contactar
   directamente a la clínica al (32) 2234512 o escribir a info@clinicabienestar.com."
3. Cita siempre el documento del que extraes la información (nombre del archivo).
4. Sé amable, profesional y empático. Usa el tuteo o el ustedeo según el tono del paciente.
5. Responde siempre en español.
6. Ante cualquier señal de emergencia médica, indica de inmediato:
   "Por favor llame al 131 (emergencias) o acuda a la sala de Urgencias de la clínica,
   disponible las 24 horas."
7. Nunca inventes diagnósticos, pronósticos ni información médica."""


class ClinicAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash-lite") -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "La variable de entorno GOOGLE_API_KEY no está configurada."
            )
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=_SYSTEM,
        )

    def _build_context(self, hits: List[Dict[str, Any]], threshold: float = 0.25) -> str:
        relevant = [h for h in hits if h.get("score", 0) >= threshold]
        if not relevant:
            return "No se encontraron documentos con relevancia suficiente para esta consulta."
        parts = []
        for h in relevant:
            source = h["metadata"].get("source", "Documento desconocido")
            category = h["metadata"].get("category", "")
            parts.append(f"[Fuente: {source} | Categoría: {category}]\n{h['content']}")
        return "\n\n---\n\n".join(parts)

    def _extract_sources(self, hits: List[Dict[str, Any]], threshold: float = 0.25) -> List[str]:
        seen: set = set()
        sources: List[str] = []
        for h in hits:
            if h.get("score", 0) >= threshold:
                src = h["metadata"].get("source", "")
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
        return sources

    def answer(
        self,
        question: str,
        hits: List[Dict[str, Any]],
        history: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        context = self._build_context(hits)
        sources = self._extract_sources(hits)

        gemini_history = []
        for msg in history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        user_turn = (
            f"Contexto de los documentos de la Clínica Bienestar Integral:\n"
            f"{context}\n\n"
            f"Pregunta: {question}"
        )

        chat = self._model.start_chat(history=gemini_history)
        response = chat.send_message(user_turn)

        meta = getattr(response, "usage_metadata", None)
        return {
            "answer": response.text,
            "sources": sources,
            "input_tokens": getattr(meta, "prompt_token_count", 0),
            "output_tokens": getattr(meta, "candidates_token_count", 0),
        }
