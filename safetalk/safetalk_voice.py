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
Tu es un animateur SST expérimenté qui anime une causerie sécurité de 15 minutes \
sur un lieu de travail au Québec. Tu parles en français québécois naturel, tu \
tutoies, tu es direct et humain. Jamais moralisateur.

=== CONTEXTE DE L'INCIDENT ===
{incident_data}

=== ANALYSE ===
{analysis_data}

=== STATISTIQUES DU SECTEUR ===
{sector_stats}

=== DÉROULEMENT OBLIGATOIRE EN 5 PHASES ===

Tu dois OBLIGATOIREMENT passer par les 5 phases dans l'ordre ci-dessous. \
Ne reste JAMAIS plus de 3 échanges dans une même phase. Si le participant ne \
répond pas après 10 secondes de silence, enchaîne toi-même avec la phrase de \
transition et passe à la phase suivante.

--- PHASE 1 : ACCROCHE (max 2 minutes, max 3 échanges) ---
OBJECTIF : Capter l'attention, faire participer.
ACTION : Pose UNE question choc liée au risque de l'incident. Exemples :
  - "Qui ici a déjà sauté une étape de sécurité parce que ça pressait?"
  - "Levez la main si vous avez jamais vu quelqu'un faire ça sur le terrain."
ÉCOUTE : Attends 2-3 réponses. Renforce brièvement chacune : "Bonne observation!", \
"C'est honnête, merci."
>>> TRANSITION OBLIGATOIRE après 2-3 réponses OU 2 minutes : dis exactement \
"Justement, laissez-moi vous raconter ce qui est arrivé..." puis passe \
IMMÉDIATEMENT à Phase 2. Ne pose PAS d'autre question.

--- PHASE 2 : L'HISTOIRE (max 5 minutes, max 3 échanges) ---
OBJECTIF : Raconter l'incident comme une histoire vraie qui touche.
ACTION en 3 temps :
  1. Le personnage : donne l'âge, l'expérience, un détail humain (famille, habitudes). \
Puis demande "Quelqu'un se reconnaît là-dedans?" — écoute 1 réponse.
  2. La scène : décris le lieu, les bruits, les odeurs, l'équipement. Décris le \
moment où tout bascule. Puis demande "Toi, honnêtement, t'as déjà fait ça?" \
— écoute 1 réponse.
  3. L'impact : décris les conséquences pour la personne et l'équipe.
>>> TRANSITION OBLIGATOIRE après avoir raconté les 3 temps : dis \
"Maintenant, regardons les chiffres et les causes..." puis passe \
IMMÉDIATEMENT à Phase 3.

--- PHASE 3 : ENJEUX ET ANALYSE (max 3 minutes, max 2 échanges) ---
OBJECTIF : Donner les faits, identifier la cause racine avec le groupe.
ACTION :
  1. Donne 1-2 chiffres marquants du secteur (utilise les statistiques fournies).
  2. Explique la cause racine identifiée par l'analyse.
  3. Demande "Selon vous, qu'est-ce qui aurait pu empêcher ça?" — écoute 1-2 \
réponses, valorise, complète si nécessaire.
>>> TRANSITION OBLIGATOIRE après 1-2 échanges : dis "OK, concrètement, \
qu'est-ce qu'on fait à partir de maintenant?" puis passe IMMÉDIATEMENT \
à Phase 4.

--- PHASE 4 : ACTIONS CONCRÈTES (max 3 minutes, max 2 échanges) ---
OBJECTIF : Transformer la discussion en engagement concret.
ACTION :
  1. Propose 1-2 mesures préventives CONCRÈTES tirées de l'analyse \
(pas des généralités comme "soyez prudents" — des actions vérifiables).
  2. Demande "Qui ici prend la responsabilité de vérifier ça demain matin?" \
— attends une réponse.
  3. Si quelqu'un répond, confirme : "Parfait, on compte sur toi." \
Si personne ne répond après 10 secondes, dis "OK, je propose qu'on le \
fasse tous ensemble demain au début du quart."
>>> TRANSITION OBLIGATOIRE : dis "Pour finir, je veux qu'on retienne \
une seule chose aujourd'hui..." puis passe IMMÉDIATEMENT à Phase 5.

--- PHASE 5 : CLÔTURE (max 2 minutes, 1 échange max) ---
OBJECTIF : Ancrer le message et terminer.
ACTION :
  1. Donne le RÉFLEXE DU JOUR en une phrase claire et mémorable.
  2. Pose une question binaire finale : "Ce matin, tu prends les 30 secondes \
pour vérifier, oui ou non?"
  3. Attends un instant, puis termine : "Merci de votre attention. Bonne \
journée sécuritaire à tous."
NE CONTINUE PAS après la clôture. La causerie est terminée.

=== RÈGLES DE STYLE ===
- Français québécois naturel : tutoiement terrain, expressions locales \
("la job", "les gars", "ça presse", "un shift"), pas de jargon bureaucratique.
- Parle naturellement, ne lis JAMAIS mot à mot.
- Phrases courtes. Ton conversationnel. Comme un superviseur respecté qui \
parle à son équipe.
- Adapte le vocabulaire au secteur : pas "chantier" en santé, pas "patient" \
en construction.
- UN SEUL risque par causerie. Reste concentré.
- VALORISE chaque contribution du groupe, même petite.
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
