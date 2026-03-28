"""
VOICEX5-GEMINI-LIVE — Configuration Quiz Radar Vocal LiteraCIA
===============================================================
Pivot : Whisper+Piper+TEN → Gemini Live API (audio natif, <1s latence, 90+ langues)
Scope : Intégration LiteraCIA (formation SST, FastAPI, Supabase PostgreSQL)
MVP   : Quiz Radar Vocal — 18 questions ouvertes, scoring 0-100 par axe
LLM   : Hybride — Gemini Live (vocal) / Claude (analyses texte post-quiz)
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 1. CONFIGURATION GEMINI LIVE API
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.1-flash-live-preview"
GEMINI_WS_URI = (
    f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage"
    f".v1beta.GenerativeService.BidiGenerateContent"
    f"?key={GEMINI_API_KEY}"
)

# Audio PCM16 config
AUDIO_INPUT_SAMPLE_RATE = 16_000   # 16 kHz mono PCM16 entrée micro
AUDIO_OUTPUT_SAMPLE_RATE = 24_000  # 24 kHz mono PCM16 sortie Gemini
AUDIO_CHANNELS = 1
AUDIO_ENCODING = "pcm16"           # Linear PCM 16-bit little-endian

GEMINI_GENERATION_CONFIG = {
    "response_modalities": ["AUDIO"],
    "speech_config": {
        "voice_config": {
            "prebuilt_voice_config": {
                "voice_name": "Aoede",  # Voix naturelle FR
            }
        }
    },
}


# ============================================================
# 2. LES 6 AXES DU RADAR + 18 QUESTIONS (3 × 6)
# ============================================================

class AxeRadar(str, Enum):
    COMPREHENSION_TECHNIQUE = "comprehension_technique_ia"
    USAGE_OPERATIONNEL = "usage_operationnel"
    PENSEE_CRITIQUE = "pensee_critique"
    ETHIQUE_CONFORMITE = "ethique_conformite"
    COLLABORATION_HUMAIN_IA = "collaboration_humain_ia"
    APPRENTISSAGE_CONTINU = "apprentissage_continu"


AXE_LABELS: dict[AxeRadar, str] = {
    AxeRadar.COMPREHENSION_TECHNIQUE: "Comprehension Technique IA",
    AxeRadar.USAGE_OPERATIONNEL: "Usage Operationnel",
    AxeRadar.PENSEE_CRITIQUE: "Pensee Critique",
    AxeRadar.ETHIQUE_CONFORMITE: "Ethique & Conformite",
    AxeRadar.COLLABORATION_HUMAIN_IA: "Collaboration Humain-IA",
    AxeRadar.APPRENTISSAGE_CONTINU: "Apprentissage Continu",
}


# 18 questions ouvertes contextualisees SST/HSE Quebec
QUIZ_QUESTIONS: list[dict] = [
    # --- Axe 1 : Comprehension Technique IA ---
    {
        "id": "CT1",
        "axe": AxeRadar.COMPREHENSION_TECHNIQUE,
        "question": (
            "Dans tes mots, c'est quoi la difference entre une IA generative "
            "comme ChatGPT pis un systeme expert traditionnel qu'on utilise "
            "deja en SST pour l'analyse de risques?"
        ),
    },
    {
        "id": "CT2",
        "axe": AxeRadar.COMPREHENSION_TECHNIQUE,
        "question": (
            "Si je te dis qu'un modele de langage peut halluciner, qu'est-ce "
            "que ca veut dire concretement? Peux-tu me donner un exemple de "
            "risque que ca pourrait causer dans un contexte SST?"
        ),
    },
    {
        "id": "CT3",
        "axe": AxeRadar.COMPREHENSION_TECHNIQUE,
        "question": (
            "Explique-moi comment un modele d'IA apprend a partir de donnees. "
            "Pourquoi c'est important de comprendre ca quand on utilise l'IA "
            "pour analyser des rapports d'incidents CNESST?"
        ),
    },

    # --- Axe 2 : Usage Operationnel ---
    {
        "id": "UO1",
        "axe": AxeRadar.USAGE_OPERATIONNEL,
        "question": (
            "Decris-moi une situation concrete dans ton travail en SST ou "
            "l'IA pourrait t'aider a etre plus efficace. Comment tu "
            "l'utiliserais, etape par etape?"
        ),
    },
    {
        "id": "UO2",
        "axe": AxeRadar.USAGE_OPERATIONNEL,
        "question": (
            "T'as un rapport d'enquete d'accident de 40 pages a analyser "
            "pour la CNESST. Comment tu structurerais un prompt pour qu'une "
            "IA t'aide a en extraire les causes racines?"
        ),
    },
    {
        "id": "UO3",
        "axe": AxeRadar.USAGE_OPERATIONNEL,
        "question": (
            "Un collegue te montre une procedure de cadenassage generee par "
            "l'IA. Quelles verifications tu ferais avant de l'approuver pour "
            "utilisation sur le plancher?"
        ),
    },

    # --- Axe 3 : Pensee Critique ---
    {
        "id": "PC1",
        "axe": AxeRadar.PENSEE_CRITIQUE,
        "question": (
            "Une IA te recommande de reduire la frequence d'inspection d'un "
            "equipement critique parce que les donnees historiques montrent "
            "peu de defaillances. Es-tu d'accord? Explique ton raisonnement."
        ),
    },
    {
        "id": "PC2",
        "axe": AxeRadar.PENSEE_CRITIQUE,
        "question": (
            "Comment tu ferais pour evaluer si une reponse donnee par l'IA "
            "sur une norme CSA ou un reglement RSST est fiable? Quels "
            "reflexes tu devrais avoir?"
        ),
    },
    {
        "id": "PC3",
        "axe": AxeRadar.PENSEE_CRITIQUE,
        "question": (
            "Un systeme IA analyse tes donnees d'accidents et conclut que "
            "90%% des incidents arrivent le lundi matin. Avant d'agir "
            "la-dessus, quelles questions tu te poserais?"
        ),
    },

    # --- Axe 4 : Ethique & Conformite ---
    {
        "id": "EC1",
        "axe": AxeRadar.ETHIQUE_CONFORMITE,
        "question": (
            "Ton employeur veut utiliser l'IA pour analyser les videos de "
            "surveillance afin de detecter les comportements non securitaires. "
            "Quels enjeux ethiques tu vois la-dedans?"
        ),
    },
    {
        "id": "EC2",
        "axe": AxeRadar.ETHIQUE_CONFORMITE,
        "question": (
            "En lien avec la Loi 25 au Quebec, quelles precautions faut-il "
            "prendre quand on utilise l'IA pour traiter des donnees de sante "
            "et securite des travailleurs?"
        ),
    },
    {
        "id": "EC3",
        "axe": AxeRadar.ETHIQUE_CONFORMITE,
        "question": (
            "Si une IA de prediction de risques montre un biais — par exemple "
            "elle signale plus souvent les incidents dans un departement "
            "specifique — comment tu reagirais?"
        ),
    },

    # --- Axe 5 : Collaboration Humain-IA ---
    {
        "id": "CH1",
        "axe": AxeRadar.COLLABORATION_HUMAIN_IA,
        "question": (
            "Dans un processus d'enquete d'accident, quelles etapes tu "
            "confierais a l'IA et lesquelles tu garderais absolument pour "
            "le jugement humain? Pourquoi?"
        ),
    },
    {
        "id": "CH2",
        "axe": AxeRadar.COLLABORATION_HUMAIN_IA,
        "question": (
            "Comment tu presenterais l'utilisation d'un outil IA a une equipe "
            "de travailleurs sur un chantier qui sont mefiants envers la "
            "technologie? Quelle approche tu prendrais?"
        ),
    },
    {
        "id": "CH3",
        "axe": AxeRadar.COLLABORATION_HUMAIN_IA,
        "question": (
            "Decris comment tu vois le role ideal d'un professionnel SST qui "
            "travaille avec l'IA au quotidien. Qu'est-ce qui change et "
            "qu'est-ce qui reste pareil dans son expertise?"
        ),
    },

    # --- Axe 6 : Apprentissage Continu ---
    {
        "id": "AC1",
        "axe": AxeRadar.APPRENTISSAGE_CONTINU,
        "question": (
            "L'IA evolue tres vite. Comment tu t'y prends concretement pour "
            "rester a jour sur les nouveaux outils IA pertinents pour la SST? "
            "Donne-moi des exemples de ce que tu fais deja ou voudrais faire."
        ),
    },
    {
        "id": "AC2",
        "axe": AxeRadar.APPRENTISSAGE_CONTINU,
        "question": (
            "Si ta compagnie t'offrait une formation sur l'IA appliquee a la "
            "SST, qu'est-ce que tu voudrais absolument y retrouver? Quels "
            "sujets seraient prioritaires pour toi?"
        ),
    },
    {
        "id": "AC3",
        "axe": AxeRadar.APPRENTISSAGE_CONTINU,
        "question": (
            "Raconte-moi une fois ou tu as du apprendre rapidement un nouvel "
            "outil ou une nouvelle technologie dans ton travail. Comment tu "
            "t'y es pris et qu'est-ce que t'en retires pour l'adoption de l'IA?"
        ),
    },
]

# Mapping question_id → axe (pour lookup rapide)
QUESTION_AXE_MAP: dict[str, AxeRadar] = {
    q["id"]: q["axe"] for q in QUIZ_QUESTIONS
}


# ============================================================
# 3. SYSTEM PROMPT GEMINI (Assistant vocal LiteraCIA)
# ============================================================

SYSTEM_PROMPT = """\
Tu es l'assistant vocal de LiteraCIA, la plateforme de formation en litteratie \
IA pour les professionnels de la sante et securite au travail (SST/HSE) au Quebec.

TON ROLE :
- Tu fais passer un quiz vocal de 18 questions ouvertes pour evaluer le niveau \
de litteratie IA d'un professionnel SST.
- Tu poses UNE question a la fois, tu ecoutes la reponse complete, puis tu \
scores via function calling avant de passer a la suivante.

TON TON :
- Quebecois bienveillant et professionnel. Tutoiement naturel.
- Encourageant mais honnete. Tu valorises l'effort meme si la reponse est partielle.
- Tu reformules ou clarifies si la personne semble hesiter, sans donner la reponse.

DEROULEMENT :
1. Accueille chaleureusement le participant et explique brievement le quiz \
(18 questions, ~15 minutes, pas de bonne ou mauvaise reponse).
2. Pose les questions dans l'ordre (CT1 a AC3).
3. Apres chaque reponse, appelle la fonction score_response avec ton evaluation.
4. Enchaine naturellement vers la question suivante avec une transition courte.
5. Apres la derniere question (AC3), appelle finalize_quiz et fais un debrief \
encourageant avec les points forts identifies.

SCORING (0-20 par question) :
- 0-4   : Pas de reponse ou hors sujet complet
- 5-8   : Notions vagues, comprehension superficielle
- 9-12  : Comprehension correcte avec exemples partiels
- 13-16 : Bonne maitrise, exemples concrets et pertinents
- 17-20 : Excellence, vision strategique, liens entre concepts

REGLES :
- Ne donne JAMAIS le score a voix haute pendant le quiz.
- Si la personne dit "je sais pas", encourage-la a essayer puis score selon ce qu'elle donne.
- Adapte ton debit : laisse le temps de reflechir, ne coupe pas la parole.
- Reste dans le contexte SST/HSE Quebec (CNESST, RSST, Loi 25, normes CSA).
"""


# ============================================================
# 4. SCHEMAS FUNCTION CALLING GEMINI
# ============================================================

TOOL_SCORE_RESPONSE = {
    "name": "score_response",
    "description": (
        "Score la reponse du participant a une question du quiz radar vocal. "
        "Appelee apres chaque reponse pour enregistrer l'evaluation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "question_id": {
                "type": "string",
                "description": "Identifiant de la question (ex: CT1, UO2, PC3)",
                "enum": [q["id"] for q in QUIZ_QUESTIONS],
            },
            "score": {
                "type": "integer",
                "description": "Score de 0 a 20 pour cette reponse",
                "minimum": 0,
                "maximum": 20,
            },
            "justification": {
                "type": "string",
                "description": (
                    "Justification breve du score attribue (criteres observes, "
                    "elements manquants). Non communiquee au participant."
                ),
            },
            "mots_cles_detectes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concepts cles mentionnes par le participant",
            },
        },
        "required": ["question_id", "score", "justification"],
    },
}

TOOL_FINALIZE_QUIZ = {
    "name": "finalize_quiz",
    "description": (
        "Finalise le quiz apres la derniere question. Calcule les scores par "
        "axe et le profil global du participant."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "participant_feedback": {
                "type": "string",
                "description": (
                    "Message de debrief encourageant a communiquer vocalement "
                    "au participant, incluant ses points forts."
                ),
            },
            "points_forts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste des axes ou le participant excelle",
            },
            "axes_a_developper": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste des axes a ameliorer en priorite",
            },
        },
        "required": ["participant_feedback", "points_forts", "axes_a_developper"],
    },
}

GEMINI_TOOLS = [
    {"function_declarations": [TOOL_SCORE_RESPONSE, TOOL_FINALIZE_QUIZ]}
]


# ============================================================
# 5. MODELES PYDANTIC
# ============================================================

class NiveauLiteratie(str, Enum):
    NOVICE = "Novice"
    DEBUTANT = "Debutant"
    INTERMEDIAIRE = "Intermediaire"
    AVANCE = "Avance"
    EXPERT = "Expert"


def calcul_niveau(score_pct: float) -> NiveauLiteratie:
    """Determine le niveau a partir du score en pourcentage (0-100)."""
    if score_pct < 20:
        return NiveauLiteratie.NOVICE
    if score_pct < 40:
        return NiveauLiteratie.DEBUTANT
    if score_pct < 60:
        return NiveauLiteratie.INTERMEDIAIRE
    if score_pct < 80:
        return NiveauLiteratie.AVANCE
    return NiveauLiteratie.EXPERT


class VoiceSessionCreate(BaseModel):
    """Requete de creation d'une session quiz vocal."""
    user_id: str = Field(..., description="UUID de l'utilisateur LiteraCIA")
    langue: str = Field(default="fr-CA", description="Code langue BCP-47")
    metadata: Optional[dict] = Field(
        default=None,
        description="Metadonnees optionnelles (poste, secteur, experience)",
    )


class VoiceSessionResponse(BaseModel):
    """Reponse apres creation d'une session."""
    session_id: str = Field(..., description="UUID de la session quiz")
    websocket_url: str = Field(
        ..., description="URL WebSocket pour le client audio"
    )
    total_questions: int = Field(default=18)
    duree_estimee_minutes: int = Field(default=15)


class QuestionScore(BaseModel):
    """Score d'une question individuelle."""
    question_id: str = Field(..., description="ID question (ex: CT1)")
    axe: AxeRadar
    score: int = Field(..., ge=0, le=20, description="Score 0-20")
    justification: str = Field(
        ..., description="Justification interne (non montree au participant)"
    )
    mots_cles_detectes: list[str] = Field(default_factory=list)


class ScoreAxe(BaseModel):
    """Score agrege pour un axe du radar."""
    axe: AxeRadar
    label: str
    score_brut: int = Field(..., ge=0, le=60, description="Somme des 3 questions (0-60)")
    score_pct: float = Field(..., ge=0, le=100, description="Score en % (0-100)")
    niveau: NiveauLiteratie
    questions: list[QuestionScore] = Field(default_factory=list)


class QuizVocalResult(BaseModel):
    """Resultat complet du quiz radar vocal."""
    session_id: str
    user_id: str
    scores_axes: list[ScoreAxe]
    score_global_pct: float = Field(
        ..., ge=0, le=100, description="Moyenne des 6 axes (0-100)"
    )
    niveau_global: NiveauLiteratie
    points_forts: list[str] = Field(default_factory=list)
    axes_a_developper: list[str] = Field(default_factory=list)
    participant_feedback: str = Field(
        default="", description="Debrief vocal genere par Gemini"
    )
    duree_secondes: Optional[int] = Field(
        default=None, description="Duree totale du quiz en secondes"
    )

    @staticmethod
    def calculer_scores_axes(
        scores: list[QuestionScore],
    ) -> list[ScoreAxe]:
        """Agrege les scores par question en scores par axe."""
        axes_scores: dict[AxeRadar, list[QuestionScore]] = {}
        for s in scores:
            axes_scores.setdefault(s.axe, []).append(s)

        result = []
        for axe in AxeRadar:
            qs = axes_scores.get(axe, [])
            brut = sum(q.score for q in qs)
            pct = round((brut / 60) * 100, 1) if qs else 0.0
            result.append(
                ScoreAxe(
                    axe=axe,
                    label=AXE_LABELS[axe],
                    score_brut=brut,
                    score_pct=pct,
                    niveau=calcul_niveau(pct),
                    questions=qs,
                )
            )
        return result
