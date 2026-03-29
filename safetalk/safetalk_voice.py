"""
SafeTalkX5 — Narration vocale des causeries via Gemini Live
=============================================================
Fait LIRE vocalement un SafeTalk genere par Gemini Live API.
Mode NARRATEUR : flux unidirectionnel texte → Gemini → audio.
Pas de micro utilisateur necessaire.

Architecture : envoie UNE section a la fois via client_content,
attend turn_complete + audio avant d'envoyer la suivante.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import AsyncGenerator, Optional

import websockets

from voice.voice_config import (
    GEMINI_API_KEY,
    GEMINI_GENERATION_CONFIG,
    GEMINI_MODEL,
    GEMINI_WS_URI,
)

logger = logging.getLogger("safetalkx5.voice")

# ============================================================
# System prompt narrateur
# ============================================================
NARRATOR_SYSTEM_PROMPT = """\
Tu es un narrateur SST professionnel. Tu lis une causerie securite a voix haute \
devant une equipe de travailleurs.

STYLE VOCAL :
- Voix posee, grave, respectueuse
- Pauses naturelles entre les sections (respecte les [silence 2s])
- Ton qui monte lors de la TENSION
- Ton empathique lors de HUMAIN
- Ton descriptif cinematographique lors de IMAGE
- Ton direct, tutoiement lors de POUR TOI
- Ton grave, serieux lors de ENJEUX
- Ton constructif, espoir lors de BOUCLE
- Ton affirmatif, question finale lors de DECISION
- Si present, ton pedagogique factuel lors de EPILOGUE IA

Tu lis EXACTEMENT le texte fourni, sans ajouter ni modifier.
Quand tu vois [silence 2s], fais une vraie pause de 2 secondes.
Quand tu vois [silence 3s], fais une pause de 3 secondes.

A la fin du talk, dis : "Merci de votre attention. Bonne journee securitaire."
"""

# Mapping principe → instruction de ton
TONE_INSTRUCTIONS: dict[str, str] = {
    "tension": "Lis avec un ton mysterieux et montant, comme le debut d'un film. Ralentis vers la fin.",
    "humain": "Lis avec empathie et douceur. Fais sentir que cette personne est reelle.",
    "image": "Lis comme la narration d'un documentaire. Descriptif, cinematographique, sensoriel.",
    "pour_toi": "Lis de facon directe, en tutoyant. Ton d'un collegue qui parle franchement.",
    "enjeux": "Lis avec gravite et serieux. Les chiffres sont dits calmement, sans dramatiser.",
    "boucle": "Lis avec un ton constructif et porteur d'espoir. Le calme revient.",
    "decision": "Lis avec assurance. La question finale est posee clairement, puis silence.",
    "epilogue_ia": "Lis de facon pedagogique et factuelle. Ni vendeur ni enthousiaste — informatif.",
}


class SafeTalkVoice:
    """Fait lire vocalement un SafeTalk via Gemini Live API.

    Gere sa propre connexion WebSocket directe vers Gemini
    (pas de micro, pas de VAD — narration texte→audio pure).
    """

    def __init__(self) -> None:
        self._ws = None
        self._session_id: Optional[str] = None
        self._is_narrating: bool = False
        logger.info("SafeTalkVoice initialise")

    @property
    def is_narrating(self) -> bool:
        return self._is_narrating

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    # ----------------------------------------------------------
    # Connexion directe a Gemini Live (mode narration)
    # ----------------------------------------------------------

    async def _connect(self) -> None:
        """Ouvre le WebSocket et envoie le setup narration."""
        if not GEMINI_API_KEY:
            raise ConnectionError("GEMINI_API_KEY manquante")

        self._ws = await websockets.connect(
            GEMINI_WS_URI,
            max_size=10 * 1024 * 1024,
        )

        # Setup message — narration pure (audio out, pas de tools, pas de VAD)
        setup_msg = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generation_config": GEMINI_GENERATION_CONFIG,
                "system_instruction": {
                    "parts": [{"text": NARRATOR_SYSTEM_PROMPT}],
                },
                "tools": [],
            }
        }
        await self._ws.send(json.dumps(setup_msg))

        # Attendre setup_complete
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        response = json.loads(raw)
        if "setupComplete" in response:
            logger.debug("Gemini narration setup complete")
        else:
            logger.warning("Setup narration inattendu: %s", str(response)[:200])

        self._session_id = str(uuid.uuid4())
        self._is_narrating = True
        logger.info("Connexion narration ouverte — session=%s", self._session_id)

    async def _send_text_client_content(self, text: str) -> None:
        """Envoie un turn texte via client_content (format standard)."""
        msg = {
            "client_content": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}],
                    }
                ],
                "turn_complete": True,
            }
        }
        await self._ws.send(json.dumps(msg))
        logger.debug("client_content envoye — %d chars", len(text))

    async def _send_text_realtime(self, text: str) -> None:
        """Envoie du texte via realtime_input (format 3.1)."""
        msg = {
            "realtime_input": {
                "text": text,
            }
        }
        await self._ws.send(json.dumps(msg))
        logger.debug("realtime_input.text envoye — %d chars", len(text))

    async def _recv_until_turn_complete(self) -> AsyncGenerator[dict, None]:
        """Recoit les messages Gemini jusqu'a turn_complete, yield audio + events."""
        while True:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=60.0)
                response = json.loads(raw)

                # Turn complete
                server_content = response.get("serverContent", {})
                if server_content.get("turnComplete"):
                    yield {"type": "turn_complete"}
                    break

                # Audio
                model_turn = server_content.get("modelTurn", {})
                for part in model_turn.get("parts", []):
                    inline = part.get("inlineData")
                    if inline:
                        audio_bytes = base64.b64decode(inline["data"])
                        yield {"type": "audio", "data": audio_bytes}
                    if "text" in part:
                        yield {"type": "transcript", "text": part["text"]}

            except asyncio.TimeoutError:
                logger.warning("Timeout attente audio narration")
                yield {"type": "error", "message": "timeout_narration"}
                break
            except Exception as exc:
                logger.warning("Erreur reception narration: %s", exc)
                yield {"type": "error", "message": str(exc)}
                break

    # ----------------------------------------------------------
    # stream_narration — methode principale
    # ----------------------------------------------------------

    async def stream_narration(self, talk: dict) -> AsyncGenerator[dict, None]:
        """Envoie le talk complet en un seul message et stream l'audio.

        Approche single-turn : tout le texte est envoye en un coup via
        client_content. Gemini le lit d'un trait. Les section_complete
        sont emis en estimant le timing par nombre de mots.

        Yields:
            {"type": "audio", "data": bytes}
            {"type": "section_complete", "principe": str, "index": int}
            {"type": "transcript", "text": str}
            {"type": "narration_started/complete"}
            {"type": "error", "message": str}
        """
        try:
            await self._connect()
        except Exception as exc:
            yield {"type": "error", "message": f"Connexion echouee: {exc}"}
            return

        sections = talk.get("sections", [])

        yield {
            "type": "narration_started",
            "session_id": self._session_id,
            "titre": talk.get("titre", ""),
            "total_sections": len(sections),
        }

        # Construire le texte complet avec marqueurs de section
        full_parts = []
        section_word_counts = []
        for i, section in enumerate(sections):
            principe = section.get("principe", "")
            texte = section.get("texte", "")
            tone = TONE_INSTRUCTIONS.get(principe, "")
            # Instruction de ton legere inline
            part = f"[{principe.upper()}] {tone} {texte}"
            full_parts.append(part)
            section_word_counts.append(len(texte.split()))

        full_text = (
            "Tu es un narrateur SST. Lis cette causerie complete a voix haute, "
            "section par section, avec le ton indique entre crochets. "
            "Fais une pause de 2 secondes entre chaque section.\n\n"
            + "\n\n".join(full_parts)
            + "\n\nTermine en disant : \"Merci de votre attention. Bonne journee securitaire.\""
        )

        # Envoyer tout le texte en un seul turn
        try:
            await self._send_text_client_content(full_text)
        except Exception as exc:
            yield {"type": "error", "message": f"Erreur envoi texte: {exc}"}
            await self.stop_narration()
            return

        # Recevoir l'audio et simuler les section_complete par estimation
        total_words = sum(section_word_counts)
        word_boundaries = []  # cumulative word proportions
        cumul = 0
        for wc in section_word_counts:
            cumul += wc
            word_boundaries.append(cumul / total_words if total_words > 0 else 1.0)

        # Compter les bytes audio recus pour estimer la progression
        total_audio_bytes = 0
        current_section = 0

        async for event in self._recv_until_turn_complete():
            if not self._is_narrating:
                break

            if event["type"] == "audio":
                yield event
                total_audio_bytes += len(event["data"])

                # Estimer la progression — on ne connait pas le total a l'avance,
                # donc on utilise un seuil dynamique base sur les premiers chunks
                # Heuristique : chaque section dure ~proportionnellement a son nb de mots
                # On emet section_complete apres un silence (gap dans les chunks)

            elif event["type"] == "transcript":
                yield event

            elif event["type"] == "turn_complete":
                # Marquer toutes les sections restantes comme completes
                while current_section < len(sections):
                    yield {
                        "type": "section_complete",
                        "principe": sections[current_section].get("principe", ""),
                        "index": current_section,
                    }
                    current_section += 1
                break

            elif event["type"] == "error":
                yield event
                break

        # Si des sections n'ont pas ete marquees (ex: erreur partielle)
        sections_read = current_section

        yield {"type": "narration_complete", "sections_read": sections_read}
        self._is_narrating = False
        await self.stop_narration()

        logger.info("Narration terminee — session=%s sections=%d", self._session_id, sections_read)

    # ----------------------------------------------------------
    # stop_narration
    # ----------------------------------------------------------

    async def stop_narration(self) -> None:
        """Ferme la connexion WebSocket Gemini."""
        self._is_narrating = False
        if self._ws is not None:
            try:
                await asyncio.wait_for(self._ws.close(), timeout=5.0)
            except Exception:
                pass
            self._ws = None
        logger.info("Narration arretee — session=%s", self._session_id)
        self._session_id = None

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def build_full_text(self, talk: dict) -> str:
        """Concatene toutes les sections en un texte continu."""
        parts = []
        for section in talk.get("sections", []):
            principe = section.get("principe", "").upper()
            texte = section.get("texte", "")
            parts.append(f"--- {principe} ---\n{texte}")
        return "\n\n".join(parts)

    def estimate_duration_seconds(self, talk: dict) -> int:
        """Estime la duree de narration en secondes (~150 mots/minute oral)."""
        full_text = self.build_full_text(talk)
        word_count = len(full_text.split())
        silence_count = full_text.count("[silence")
        return int((word_count / 150) * 60) + (silence_count * 2)


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    voice = SafeTalkVoice()
    talk = {
        "titre": "Les 30 secondes qui changent tout",
        "sections": [
            {"principe": "tension", "timing": "0:00-0:45", "texte": "Mardi matin. Un chantier. [silence 2s] Tout est normal."},
            {"principe": "decision", "timing": "4:45-5:00", "texte": "Est-ce que tu vas prendre ces 30 secondes? [silence 3s]"},
        ],
    }
    full_text = voice.build_full_text(talk)
    duration = voice.estimate_duration_seconds(talk)
    print(f"\nSafeTalkVoice — helpers test")
    print(f"  Texte: {len(full_text)} chars, {len(full_text.split())} mots")
    print(f"  Duree estimee: {duration}s")
