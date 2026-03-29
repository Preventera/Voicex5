"""
SafeTalkX5 — Causerie interactive vocale via Gemini Live
==========================================================
Deux modes :
1. LIVE (bidirectionnel) — Gemini anime la causerie en 5 phases,
   écoute les réponses vocales des participants, rebondit.
   Même architecture que voice/voice_quiz_agent.py.
2. NARRATION (fallback) — Lecture template via speechSynthesis navigateur.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from voice.gemini_live_service import GeminiLiveService, GeminiMessage, GeminiMessageType
from voice.voice_config import GEMINI_REALTIME_INPUT_CONFIG

logger = logging.getLogger("safetalkx5.voice")

# ============================================================
# System prompt — causerie interactive 5 phases
# ============================================================
SAFETALK_SYSTEM_PROMPT = """\
Tu es un animateur de causerie SST chevronné au Québec. Tu animes une rencontre \
sécurité de 10-15 minutes avec une équipe de travailleurs. Parle en français \
québécois terrain, tutoie, sois empathique et jamais moralisateur.

ACCIDENT À RACONTER :
{incident_data}

ANALYSE DE L'ACCIDENT :
{analysis_data}

STATISTIQUES DU SECTEUR :
{sector_stats}

STRUCTURE EN 5 PHASES — suis cet ordre exactement :

PHASE 1 — ACCROCHE (2 min)
- Ouvre par une question choc liée au risque. Exemples : "Qui a failli glisser \
cette semaine?", "Levez la main si vous avez déjà sauté une étape de sécurité."
- Attends les réponses vocales. Valorise chaque contribution : "Bonne observation!", \
"C'est exactement ça."
- Enchaîne naturellement : "Justement, laissez-moi vous raconter ce qui est arrivé..."

PHASE 2 — L'HISTOIRE (5 min)
- Raconte l'accident comme une histoire vraie. Donne vie au travailleur : âge, \
famille, expérience.
- Décris la scène comme un film : lieu, bruits, odeurs, lumière, équipement.
- Après le portrait : pause et demande "Quelqu'un ici se reconnaît dans ce profil-là?"
- Après la scène : "Fermez les yeux deux secondes. Vous voyez l'endroit?"
- Interpelle directement : "Toi, honnêtement, t'as déjà fait ça?" — laisse répondre, \
rebondis sur la réponse.

PHASE 3 — ENJEUX ET ANALYSE (3 min)
- Donne les chiffres réels du secteur (utilise les statistiques fournies)
- Explique la cause racine identifiée par l'analyse
- Demande au groupe : "Selon vous, qu'est-ce qui aurait pu changer l'issue?"
- Écoute les réponses, valorise, complète avec les barrières manquantes de l'analyse

PHASE 4 — ACTIONS CONCRÈTES (3 min)
- Propose 1-2 mesures précises tirées de l'analyse (pas des généralités)
- Demande : "Qui veut prendre la responsabilité de [action spécifique] cette semaine?"
- Si quelqu'un répond, confirme et encourage
- Si personne ne répond après 8 secondes, reformule : "OK, qui commence demain matin?"

PHASE 5 — CLÔTURE (2 min)
- Résume en UNE phrase — le réflexe du jour
- Pose une question de décision binaire : "Ce matin, tu le fais ou tu le fais pas?"
- Termine : "Merci de votre attention. Bonne journée sécuritaire à tous."

RÈGLES IMPORTANTES :
- ATTENDS TOUJOURS les réponses vocales avant de continuer. Fais des pauses de \
5-10 secondes.
- Si personne ne répond après 8 secondes, reformule la question ou passe à la suite.
- NE LIS JAMAIS mot à mot — parle naturellement, comme un superviseur respecté.
- VALORISE chaque contribution, même petite.
- UN SEUL risque par causerie. Pas 3, pas 5. Un seul.
- Maximum 15 minutes total incluant les échanges.
- Adapte ton vocabulaire au secteur : pas "chantier" en santé, pas "patient" en \
construction.
"""

# Phases pour le suivi frontend
PHASES = [
    {"id": 1, "nom": "Accroche", "duree_min": 2},
    {"id": 2, "nom": "L'histoire", "duree_min": 5},
    {"id": 3, "nom": "Enjeux et analyse", "duree_min": 3},
    {"id": 4, "nom": "Actions concrètes", "duree_min": 3},
    {"id": 5, "nom": "Clôture", "duree_min": 2},
]


def _clean_for_gemini(text: str) -> str:
    """Nettoie le texte avant envoi à Gemini Live — supprime balisage interne."""
    text = re.sub(r"\[(?:TENSION|HUMAIN|IMAGE|POUR_TOI|ENJEUX|BOUCLE|DECISION|EPILOGUE_IA)\]\s*", "", text)
    text = re.sub(r"\[[A-ZÀ-Ü_]{3,}\]\s*", "", text)
    text = re.sub(r"\[silence\s*\d+s?\]", "", text)
    return re.sub(r"  +", " ", text).strip()


def build_safetalk_prompt(incident: dict, analysis: dict) -> str:
    """Construit le system prompt avec les données de l'incident."""
    # Incident sans contexte_secteur (trop verbeux)
    incident_clean = {k: v for k, v in incident.items() if k != "contexte_secteur"}
    sector_stats = incident.get("contexte_secteur", {})

    # Nettoyer les textes d'analyse qui pourraient contenir du balisage
    analysis_clean = {
        "synthese": analysis.get("synthese", {}),
        "adc": analysis.get("adc", {}),
        "bowtie": analysis.get("bowtie", {}),
    }

    prompt = SAFETALK_SYSTEM_PROMPT.format(
        incident_data=json.dumps(incident_clean, ensure_ascii=False, indent=2),
        analysis_data=json.dumps(analysis_clean, ensure_ascii=False, indent=2),
        sector_stats=json.dumps(sector_stats, ensure_ascii=False, indent=2),
    )
    return _clean_for_gemini(prompt)


class SafeTalkLiveSession:
    """Session de causerie interactive via Gemini Live (bidirectionnelle).

    Même architecture que VoiceQuizAgent — le frontend envoie l'audio du micro,
    le serveur pont vers Gemini Live, Gemini anime la causerie.
    """

    def __init__(self, incident: dict, analysis: dict) -> None:
        self.incident = incident
        self.analysis = analysis
        self.gemini = GeminiLiveService()
        self.session_id: Optional[str] = None
        self._system_prompt = build_safetalk_prompt(incident, analysis)

    async def start(self) -> str:
        """Ouvre la session Gemini Live avec le prompt causerie."""
        self.session_id = await self.gemini.create_session(
            system_prompt=self._system_prompt,
            tools=[],  # Pas de function calling pour la causerie
        )
        logger.info(
            "SafeTalk live session démarrée — session=%s secteur=%s",
            self.session_id,
            self.incident.get("secteur_nom", "?"),
        )
        return self.session_id

    async def relay_audio(self, audio_chunk: bytes) -> None:
        """Relaye un chunk audio du micro vers Gemini."""
        await self.gemini.relay_audio_to_gemini(audio_chunk)

    async def close(self) -> None:
        """Ferme la session."""
        await self.gemini.close_session()
        logger.info("SafeTalk live session fermée — session=%s", self.session_id)


# ============================================================
# Legacy — helpers pour le mode template/speechSynthesis
# ============================================================

def build_full_text(talk: dict) -> str:
    """Concatène toutes les sections en texte continu."""
    parts = []
    for section in talk.get("sections", []):
        principe = section.get("principe", "").upper()
        texte = section.get("texte", "")
        parts.append(f"--- {principe} ---\n{texte}")
    return "\n\n".join(parts)


def estimate_duration_seconds(talk: dict) -> int:
    """Estime la durée de narration (~150 mots/minute oral)."""
    full_text = build_full_text(talk)
    word_count = len(full_text.split())
    silence_count = full_text.count("[silence")
    return int((word_count / 150) * 60) + (silence_count * 2)
