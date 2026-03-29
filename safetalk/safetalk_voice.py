"""
SafeTalkX5 — Narration vocale des causeries via Gemini Live
=============================================================
Fait LIRE vocalement un SafeTalk genere par Gemini Live API.
Mode NARRATEUR : flux unidirectionnel texte → Gemini → audio.
Pas de micro utilisateur necessaire.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from voice.gemini_live_service import (
    GeminiLiveService,
    GeminiMessage,
    GeminiMessageType,
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

# Mapping principe → instruction de ton pour chaque section
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

    Flux unidirectionnel : texte envoyé via client_content → Gemini lit → audio retourné.
    """

    def __init__(self) -> None:
        self._gemini: Optional[GeminiLiveService] = None
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
    # 1. start_narration
    # ----------------------------------------------------------

    async def start_narration(self, talk: dict) -> str:
        """Ouvre une session Gemini Live et envoie le talk complet.

        Envoie chaque section comme un message texte client_content.
        Gemini le lit a voix haute et retourne l'audio.

        Args:
            talk: SafeTalk genere par SafeTalkGenerator.

        Returns:
            session_id de la session Gemini.
        """
        self._gemini = GeminiLiveService()

        # Creer session avec prompt narrateur, sans tools (pas de function calling)
        self._session_id = await self._gemini.create_session(
            system_prompt=NARRATOR_SYSTEM_PROMPT,
            tools=[],
        )
        self._is_narrating = True

        logger.info(
            "Narration demarree — session=%s titre='%s' sections=%d",
            self._session_id,
            talk.get("titre", "?")[:50],
            len(talk.get("sections", [])),
        )

        # Envoyer le talk section par section
        asyncio.create_task(self._send_talk_sections(talk))

        return self._session_id

    async def _send_talk_sections(self, talk: dict) -> None:
        """Envoie les sections du talk une par une via client_content."""
        sections = talk.get("sections", [])

        # Introduction
        titre = talk.get("titre", "Causerie SST")
        intro_text = f"Tu vas maintenant lire la causerie intitulee : {titre}. Commence."
        await self._send_text_to_gemini(intro_text)

        # Attendre un peu pour laisser Gemini traiter l'intro
        await asyncio.sleep(1.0)

        for i, section in enumerate(sections):
            if not self._is_narrating:
                break

            principe = section.get("principe", "")
            texte = section.get("texte", "")
            tone = TONE_INSTRUCTIONS.get(principe, "Lis de facon naturelle et posee.")

            # Instruction de ton + texte de la section
            message = f"[Section {i+1}/{len(sections)} — {principe.upper()}]\n{tone}\n\nLis exactement ceci :\n\n{texte}"
            await self._send_text_to_gemini(message)

            # Pause entre sections pour laisser Gemini finir de lire
            # Plus longue pour les sections emotionnelles
            pause = 2.0 if principe in ("enjeux", "decision") else 1.5
            await asyncio.sleep(pause)

        # Conclusion
        if self._is_narrating:
            await self._send_text_to_gemini(
                "La causerie est terminee. Dis maintenant : "
                "\"Merci de votre attention. Bonne journee securitaire.\""
            )

        logger.info("Toutes les sections envoyees — session=%s", self._session_id)

    async def _send_text_to_gemini(self, text: str) -> None:
        """Envoie un message texte a Gemini via client_content."""
        if not self._gemini or not self._gemini.is_connected:
            logger.warning("Gemini non connecte — impossible d'envoyer le texte")
            return

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
        await self._gemini._send_json(msg)
        logger.debug("Texte envoye a Gemini — %d chars", len(text))

    # ----------------------------------------------------------
    # 2. stream_narration
    # ----------------------------------------------------------

    async def stream_narration(self, talk: dict) -> AsyncGenerator[dict, None]:
        """Demarre la narration et yield les chunks audio + events.

        Yields:
            dict avec type parmi :
            - {"type": "audio", "data": bytes} — chunk audio PCM16
            - {"type": "section_start", "principe": str, "index": int}
            - {"type": "transcript", "text": str}
            - {"type": "turn_complete"}
            - {"type": "narration_complete"}
            - {"type": "error", "message": str}
        """
        session_id = await self.start_narration(talk)
        sections = talk.get("sections", [])
        section_idx = 0

        yield {
            "type": "narration_started",
            "session_id": session_id,
            "titre": talk.get("titre", ""),
            "total_sections": len(sections),
        }

        async for msg in self._gemini.receive_from_gemini():
            if not self._is_narrating:
                break

            if msg.type == GeminiMessageType.AUDIO:
                yield {"type": "audio", "data": msg.data}

            elif msg.type == GeminiMessageType.TRANSCRIPT:
                yield {"type": "transcript", "text": msg.data}

            elif msg.type == GeminiMessageType.TURN_COMPLETE:
                # Une section a ete lue
                if section_idx < len(sections):
                    yield {
                        "type": "section_complete",
                        "principe": sections[section_idx].get("principe", ""),
                        "index": section_idx,
                    }
                    section_idx += 1
                yield {"type": "turn_complete"}

            elif msg.type == GeminiMessageType.ERROR:
                yield {"type": "error", "message": str(msg.data)}
                break

        yield {"type": "narration_complete", "sections_read": section_idx}
        self._is_narrating = False
        logger.info(
            "Narration terminee — session=%s sections_lues=%d/%d",
            self._session_id, section_idx, len(sections),
        )

    # ----------------------------------------------------------
    # 3. stop_narration
    # ----------------------------------------------------------

    async def stop_narration(self) -> None:
        """Ferme la session Gemini proprement."""
        self._is_narrating = False
        if self._gemini:
            await self._gemini.close_session()
            logger.info("Narration arretee — session=%s", self._session_id)
        self._gemini = None
        self._session_id = None

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def build_full_text(self, talk: dict) -> str:
        """Concatene toutes les sections en un texte continu (utile pour TTS alternatif)."""
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
        # 150 mots/min + pauses [silence Xs]
        silence_count = full_text.count("[silence")
        return int((word_count / 150) * 60) + (silence_count * 2)


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    voice = SafeTalkVoice()

    # Talk de test
    talk = {
        "titre": "Les 30 secondes qui changent tout",
        "duree_estimee_minutes": 5,
        "sections": [
            {"principe": "tension", "timing": "0:00-0:45", "texte": "Mardi matin, 2023. Un chantier. [silence 2s] Tout est normal.", "note_animateur": "Lentement."},
            {"principe": "humain", "timing": "0:45-1:30", "texte": "Un travailleur, 38 ans. Il connait la job.", "note_animateur": "Empathie."},
            {"principe": "image", "timing": "1:30-2:15", "texte": "L'echelle contre le mur. Le bruit des outils. [silence 2s]", "note_animateur": "Descriptif."},
            {"principe": "pour_toi", "timing": "2:15-3:15", "texte": "Est-ce que TOI, t'as deja skippe une inspection? [silence 2s]", "note_animateur": "Direct."},
            {"principe": "enjeux", "timing": "3:15-4:00", "texte": "40 000$. C'est le cout moyen. Mais le vrai cout? [silence 2s]", "note_animateur": "Grave."},
            {"principe": "boucle", "timing": "4:00-4:45", "texte": "Meme mardi. Sauf que quelqu'un inspecte l'echelle. 30 secondes.", "note_animateur": "Espoir."},
            {"principe": "decision", "timing": "4:45-5:00", "texte": "Est-ce que tu vas prendre ces 30 secondes? [silence 3s]", "note_animateur": "Question finale."},
        ],
    }

    # Test helpers
    full_text = voice.build_full_text(talk)
    duration = voice.estimate_duration_seconds(talk)
    print(f"\nSafeTalkVoice — test helpers")
    print(f"  Texte complet: {len(full_text)} chars, {len(full_text.split())} mots")
    print(f"  Duree estimee: {duration}s (~{duration//60}min {duration%60}s)")
    print(f"  Narrating: {voice.is_narrating}")
    print(f"\n  Pour tester la narration live, lancez le serveur API et utilisez le frontend.")
