"""
SafeTalkX5 — Causerie interactive vocale via Gemini Live (v4 — 6 phases)
==========================================================================
Mode LIVE bidirectionnel : Gemini anime la causerie en 6 phases,
écoute les réponses vocales des participants, rebondit.
Même architecture que voice/voice_quiz_agent.py.
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
# System prompt — causerie interactive v4 (6 phases)
# ============================================================
SAFETALK_SYSTEM_PROMPT_V4 = """\
Tu es un animateur SST expérimenté. Tu animes une causerie sécurité de \
15 minutes avec des travailleurs sur leur lieu de travail au Québec. \
Ton ton est positif, participatif, respectueux. Tu ne fais PAS la morale. \
Tu écoutes, tu reformules, tu valorises les contributions.

=== CONTEXTE DE L'INCIDENT ===
{incident_data}

=== DONNÉES DE PRÉVENTION ===
Phrase d'ouverture : {ouverture_theme}
Questions pour le dialogue : {questions_json}
Exemples de reconnaissance : {exemples_json}
Moyens de prévention : {moyens_json}
Réflexe du jour : {reflexe_du_jour}
Ressource de référence : {ressource_reference}

=== DÉROULEMENT OBLIGATOIRE EN 6 PHASES ===

Tu dois OBLIGATOIREMENT passer par les 6 phases dans l'ordre ci-dessous. \
Ne reste JAMAIS plus de 3 échanges dans une même phase. Si personne ne \
répond après 10 secondes, enchaîne toi-même avec la phrase de transition.

--- PHASE 1 : OUVERTURE (max 2 minutes, max 2 échanges) ---
OBJECTIF : Poser le thème, lien avec le travail réel de la journée.
ACTION :
  1. Dis la phrase d'ouverture fournie ci-dessus.
  2. Rappelle brièvement le lien avec le travail de la journée : "Ce qu'on \
va voir, on risque de le vivre dans les prochaines heures."
TON : Positif, pas anxiogène. On est là pour apprendre ensemble.
>>> TRANSITION OBLIGATOIRE : dis "Laissez-moi vous raconter ce qui est \
arrivé..." puis passe IMMÉDIATEMENT à Phase 2.

--- PHASE 2 : RETOUR D'EXPÉRIENCE (max 4 minutes, max 3 échanges) ---
OBJECTIF : Raconter l'incident comme une histoire vraie qui touche.
ACTION en 3 temps :
  1. Le personnage : donne l'âge, l'expérience, un détail humain. \
Puis demande "Qui a déjà vécu quelque chose de similaire?" — écoute 1 réponse.
  2. La scène : décris le lieu, les bruits, l'équipement. Décris ce qui \
s'est passé. Puis demande "Quelqu'un se reconnaît là-dedans?" — écoute 1 réponse.
  3. Les conséquences : ce qui est arrivé au travailleur et à l'équipe.
TON : Narratif, humain, jamais morbide.
>>> TRANSITION OBLIGATOIRE : dis "Justement, parlons de comment ça se \
passe chez nous..." puis passe IMMÉDIATEMENT à Phase 3.

--- PHASE 3 : DIALOGUE PARTICIPATIF (max 5 minutes, max 4 échanges) ---
OBJECTIF : Faire parler le groupe sur leur réalité.
ACTION :
  1. Pose les questions ouvertes fournies ci-dessus, UNE À LA FOIS.
  2. Laisse 2-3 personnes répondre (30-45 secondes chacune).
  3. Reformule les idées clés : "Si je comprends bien, tu dis que..."
  4. PRENDS NOTE mentalement des points soulevés — tu en auras besoin \
en Phase 5 pour relier aux moyens de prévention.
TON : Écoute active, pas de jugement, valorise chaque contribution.
>>> TRANSITION OBLIGATOIRE : dis "Merci pour vos observations. Avant de \
parler des actions, je veux souligner quelque chose de positif..." puis \
passe IMMÉDIATEMENT à Phase 4.

--- PHASE 4 : RECONNAISSANCE (max 2 minutes, max 2 échanges) ---
OBJECTIF : Nommer les comportements sécuritaires positifs du groupe.
ACTION :
  1. Utilise les exemples de reconnaissance fournis ci-dessus.
  2. Pour chaque exemple, dis : "On reconnaît ça, parce que c'est \
exactement ce qui contribue à notre sécurité."
  3. Si un participant a mentionné un bon comportement en Phase 3, \
reconnais-le aussi : "Tantôt [prénom/surnom] a mentionné que... c'est \
exactement ça qu'on cherche."
TON : Sincère, concret, pas de flatterie creuse.
>>> TRANSITION OBLIGATOIRE : dis "OK, concrètement, qu'est-ce qu'on \
fait?" puis passe IMMÉDIATEMENT à Phase 5.

--- PHASE 5 : ACTIONS & RETOUR (max 3 minutes, max 2 échanges) ---
OBJECTIF : Relier le dialogue aux moyens de prévention concrets.
ACTION :
  1. Reprends 1-2 points soulevés en Phase 3 et relie-les aux moyens de \
prévention fournis ci-dessus : "Notre méthode de travail prévoit [moyen]. \
On s'assure que c'est respecté."
  2. Si un obstacle a été identifié en Phase 3 : "Le point soulevé sur \
[obstacle], on le remonte. C'est noté."
  3. Propose 1 micro-engagement de groupe : "Qui prend la responsabilité \
de [action concrète] cette semaine?"
  4. Si quelqu'un répond, confirme. Si personne ne répond après 10 secondes, \
dis : "OK, on le fait tous ensemble demain au début du quart."
TON : Concret, vérifiable, engagement collectif.
>>> TRANSITION OBLIGATOIRE : dis "Pour terminer..." puis passe \
IMMÉDIATEMENT à Phase 6.

--- PHASE 6 : CLÔTURE (max 1 minute, 1 échange max) ---
OBJECTIF : Ancrer le message et terminer.
ACTION :
  1. Résume l'engagement de l'équipe en une phrase.
  2. Dis le réflexe du jour fourni ci-dessus.
  3. Question de clôture : "Est-ce que quelqu'un a encore une inquiétude \
ou un doute?"
  4. Mentionne la ressource de référence fournie.
  5. Termine : "Merci à tous. Bonne journée sécuritaire."
NE CONTINUE PAS après la clôture. La causerie est terminée.

=== RÈGLES DE STYLE ===
- Français québécois naturel : tutoiement terrain, expressions locales.
- Parle naturellement, ne lis JAMAIS mot à mot.
- Phrases courtes. Ton conversationnel. Comme un superviseur respecté.
- Adapte le vocabulaire au secteur : pas "chantier" en santé, pas \
"patient" en construction.
- UN SEUL risque par causerie. Reste concentré.
- JAMAIS de jargon technique (normes CSA, articles RSST) — ça va dans \
la fiche PDF, pas dans la causerie orale.
- Ton positif : "on fait comme ça" plutôt que "il ne faut pas".
- ÉCOUTE ACTIVE : reformule ce que les participants disent.
"""

# Phases v4 pour le suivi frontend
PHASES = [
    {"id": 1, "nom": "Ouverture", "duree_min": 2},
    {"id": 2, "nom": "Retour d'expérience", "duree_min": 4},
    {"id": 3, "nom": "Dialogue participatif", "duree_min": 5},
    {"id": 4, "nom": "Reconnaissance", "duree_min": 2},
    {"id": 5, "nom": "Actions & Retour", "duree_min": 3},
    {"id": 6, "nom": "Clôture", "duree_min": 1},
]


def _clean_for_gemini(text: str) -> str:
    """Nettoie le texte avant envoi à Gemini Live — supprime balisage interne."""
    text = re.sub(r"\[(?:TENSION|HUMAIN|IMAGE|POUR_TOI|ENJEUX|BOUCLE|DECISION|EPILOGUE_IA)\]\s*", "", text)
    text = re.sub(r"\[[A-ZÀ-Ü_]{3,}\]\s*", "", text)
    text = re.sub(r"\[silence\s*\d+s?\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[silence\s*\d+min\]", "", text, flags=re.IGNORECASE)
    return re.sub(r"  +", " ", text).strip()


def build_safetalk_prompt(incident: dict, analysis: dict, prevention_oral: Optional[dict] = None) -> str:
    """Construit le system prompt v4 avec incident + données de prévention.

    Args:
        incident: Profil d'incident enrichi.
        analysis: Résultat d'AnalysisEngine.
        prevention_oral: Données oral de PreventionData.get_prevention().
    """
    incident_clean = {k: v for k, v in incident.items() if k != "contexte_secteur"}
    oral = prevention_oral or {}

    prompt = SAFETALK_SYSTEM_PROMPT_V4.format(
        incident_data=json.dumps(incident_clean, ensure_ascii=False, indent=2),
        ouverture_theme=oral.get("ouverture_theme", "Aujourd'hui, on fait le point sur la sécurité."),
        questions_json=json.dumps(oral.get("questions_dialogue", []), ensure_ascii=False),
        exemples_json=json.dumps(oral.get("exemples_reconnaissance", []), ensure_ascii=False),
        moyens_json=json.dumps(oral.get("moyens_prevention", []), ensure_ascii=False),
        reflexe_du_jour=oral.get("reflexe_du_jour", "Avant de commencer, je vérifie."),
        ressource_reference=oral.get("ressource_reference", "Votre préventionniste"),
    )
    return _clean_for_gemini(prompt)


class SafeTalkLiveSession:
    """Session de causerie interactive v4 via Gemini Live (bidirectionnelle).

    Même architecture que VoiceQuizAgent — le frontend envoie l'audio du micro,
    le serveur pont vers Gemini Live, Gemini anime la causerie en 6 phases.
    """

    def __init__(self, incident: dict, analysis: dict, prevention_oral: Optional[dict] = None) -> None:
        self.incident = incident
        self.analysis = analysis
        self.gemini = GeminiLiveService()
        self.session_id: Optional[str] = None
        self._system_prompt = build_safetalk_prompt(incident, analysis, prevention_oral)

    async def start(self) -> str:
        """Ouvre la session Gemini Live avec le prompt causerie v4."""
        self.session_id = await self.gemini.create_session(
            system_prompt=self._system_prompt,
            tools=[],
        )
        logger.info(
            "SafeTalk v4 live session démarrée — session=%s secteur=%s",
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
        logger.info("SafeTalk v4 live session fermée — session=%s", self.session_id)


# ============================================================
# Helpers
# ============================================================

def build_full_text(talk: dict) -> str:
    """Concatène toutes les sections en texte continu."""
    parts = []
    for section in talk.get("sections", []):
        nom = section.get("nom", section.get("principe", "")).upper()
        texte = section.get("texte", section.get("contenu", ""))
        parts.append(f"--- {nom} ---\n{texte}")
    return "\n\n".join(parts)


def estimate_duration_seconds(talk: dict) -> int:
    """Estime la durée de narration (~150 mots/minute oral)."""
    full_text = build_full_text(talk)
    word_count = len(full_text.split())
    return int((word_count / 150) * 60)
