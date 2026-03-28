"""
VOICEX5 — Agent Claude #2 : Skills Gap Analysis
=================================================
Analyse les resultats du quiz radar vocal et genere un plan
d'apprentissage personnalise en litteratie IA pour les
professionnels SST/HSE au Quebec.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger("voicex5.skills_gap")

NIVEAU_SUIVANT = {
    "Novice": "Debutant",
    "Debutant": "Intermediaire",
    "Intermediaire": "Avance",
    "Avance": "Expert",
    "Expert": "Expert",
}

ANALYSIS_PROMPT = """\
Tu es un expert en formation professionnelle specialise en litteratie IA \
pour les professionnels de la sante et securite au travail (SST/HSE) au Quebec.

Un participant vient de completer un quiz radar vocal evaluant 6 axes de litteratie IA. \
Voici ses resultats :

PROFIL DU PARTICIPANT :
- User ID : {user_id}
- Score global : {overall_score}%
- Niveau actuel : {level}
- Niveau cible : {niveau_cible}

SCORES PAR AXE (sur 100%) :
{axes_detail}

RESUME DU QUIZ :
{summary}

CONTEXTE :
- Domaine : Sante et securite au travail (SST/HSE) au Quebec
- Reglementation : CNESST, RSST, Loi 25 (protection des renseignements personnels)
- Normes : CSA, ISO 45001
- Les modules disponibles sont de type : lecture, video, quiz, pratique (exercice hands-on), projet

CONSIGNE :
Analyse les resultats et genere un plan d'apprentissage personnalise.
Reponds UNIQUEMENT en JSON valide avec cette structure exacte :

{{
  "analysis_summary": "Paragraphe de synthese (3-5 phrases) sur le profil du participant",
  "top_priorities": [
    {{
      "axe": "nom de l'axe",
      "score_actuel": 35,
      "score_cible": 60,
      "raison": "pourquoi c'est prioritaire",
      "action_cle": "action concrete a prendre"
    }}
  ],
  "quick_wins": [
    {{
      "titre": "titre du micro-learning",
      "duree_minutes": 10,
      "type": "lecture|video|quiz|pratique",
      "axe_cible": "nom de l'axe",
      "description": "ce que le participant apprendra"
    }}
  ],
  "plan_12_semaines": [
    {{
      "semaine": 1,
      "theme": "theme de la semaine",
      "objectif": "objectif mesurable",
      "activites": [
        {{
          "titre": "titre de l'activite",
          "type": "lecture|video|quiz|pratique|projet",
          "duree_minutes": 30,
          "description": "description courte"
        }}
      ],
      "heures_estimees": 5
    }}
  ],
  "forces_identifiees": [
    {{
      "axe": "nom de l'axe",
      "score": 75,
      "commentaire": "ce qui est bien maitrise"
    }}
  ],
  "estimation_progression": {{
    "niveau_actuel": "Intermediaire",
    "niveau_cible": "Avance",
    "semaines_estimees": 8,
    "heures_totales_estimees": 48,
    "facteurs_de_succes": ["facteur 1", "facteur 2"]
  }}
}}

REGLES :
- Top priorities : axes < 60% en premier, max 3
- Quick wins : exactement 5, tous < 15 minutes
- Plan 12 semaines : 12 entrees, 4-8h par semaine, progression graduelle
- Forces : axes >= 60%
- Tout doit etre contextualise SST/HSE Quebec
- Reponds UNIQUEMENT en JSON, pas de texte avant ou apres
"""


class SkillsGapAgent:
    """Agent Claude #2 — Analyse des ecarts de competences et plan d'apprentissage."""

    def __init__(self, anthropic_api_key: str | None = None) -> None:
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquante")
        self._client = anthropic.Anthropic(api_key=api_key)

    async def analyze(
        self,
        user_id: str,
        axes_scores: dict[str, Any],
        overall_score: float,
        level: str,
        summary: str = "",
    ) -> dict:
        """Analyse les resultats du quiz et genere un plan d'apprentissage.

        Args:
            user_id: Identifiant du participant.
            axes_scores: Dict axe_key -> {score_pct, niveau, ...}.
            overall_score: Score global 0-100.
            level: Niveau global (Novice..Expert).
            summary: Resume textuel du quiz par Gemini.

        Returns:
            Dict avec analysis_summary, top_priorities, quick_wins,
            plan_12_semaines, forces_identifiees, estimation_progression.
        """
        axes_detail = self._format_axes(axes_scores)
        niveau_cible = NIVEAU_SUIVANT.get(level, "Avance")

        prompt = ANALYSIS_PROMPT.format(
            user_id=user_id,
            overall_score=round(overall_score),
            level=level,
            niveau_cible=niveau_cible,
            axes_detail=axes_detail,
            summary=summary or "(pas de resume disponible)",
        )

        logger.info("Skills gap analysis — user=%s score=%.0f%% level=%s", user_id, overall_score, level)

        response = self._client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()
        result = self._parse_json_response(raw_text)

        logger.info(
            "Skills gap analysis terminee — %d priorites, %d quick wins, %d semaines",
            len(result.get("top_priorities", [])),
            len(result.get("quick_wins", [])),
            len(result.get("plan_12_semaines", [])),
        )

        return result

    def _format_axes(self, axes_scores: dict) -> str:
        """Formate les scores par axe pour le prompt."""
        label_map = {
            "comprehension_technique_ia": "Comprehension Technique IA",
            "usage_operationnel": "Usage Operationnel",
            "pensee_critique": "Pensee Critique",
            "ethique_conformite": "Ethique & Conformite",
            "collaboration_humain_ia": "Collaboration Humain-IA",
            "apprentissage_continu": "Apprentissage Continu",
        }
        lines = []
        for key, label in label_map.items():
            data = axes_scores.get(key, {})
            if isinstance(data, dict):
                score = data.get("score_pct", 0)
                niveau = data.get("niveau", "—")
            else:
                score = 0
                niveau = "—"
            lines.append(f"- {label} : {score}% ({niveau})")
        return "\n".join(lines)

    def _parse_json_response(self, text: str) -> dict:
        """Parse la reponse JSON de Claude, tolerant aux blocs markdown."""
        # Retirer les blocs ```json ... ``` si presents
        if "```json" in text:
            text = text.split("```json", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Erreur parsing JSON Claude: %s — raw: %s", exc, text[:500])
            return {
                "analysis_summary": text[:1000],
                "top_priorities": [],
                "quick_wins": [],
                "plan_12_semaines": [],
                "forces_identifiees": [],
                "estimation_progression": {},
                "parse_error": str(exc),
            }
