"""
VOICEX5-GEMINI-LIVE — Agent Quiz Radar Vocal LiteraCIA
======================================================
Logique metier du quiz : orchestration des 18 questions,
scoring par axe, persistance Supabase, integration avec
le flux existant LiteraCIA (Agent Claude #2 Skills Gap).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from voice.gemini_live_service import GeminiLiveService
from voice.voice_config import (
    AXE_LABELS,
    GEMINI_TOOLS,
    QUESTION_AXE_MAP,
    QUIZ_QUESTIONS,
    SYSTEM_PROMPT,
    AxeRadar,
    NiveauLiteratie,
    QuestionScore,
    QuizVocalResult,
    calcul_niveau,
)

logger = logging.getLogger("voicex5.quiz_agent")


class VoiceQuizAgent:
    """Orchestre un quiz radar vocal de 18 questions via Gemini Live.

    Responsabilites :
    - Demarrage de session Gemini Live avec le prompt quiz
    - Traitement des function calls (score_response, finalize_quiz)
    - Calcul des scores par axe et global
    - Persistance dans Supabase (voice_sessions + radar_results)
    """

    def __init__(
        self,
        user_id: str,
        supabase_client: Any,
        language: str = "fr-CA",
    ) -> None:
        self.user_id = user_id
        self.supabase = supabase_client
        self.language = language

        # Etat du quiz
        self.scores: list[QuestionScore] = []
        self.questions_answered: int = 0
        self.start_time: Optional[float] = None
        self.session_id: Optional[str] = None
        self.result: Optional[QuizVocalResult] = None

        # Service Gemini Live
        self.gemini = GeminiLiveService()

    # ----------------------------------------------------------
    # 2. start_quiz
    # ----------------------------------------------------------

    async def start_quiz(self) -> str:
        """Demarre le quiz vocal : connexion Gemini + entree Supabase.

        Returns:
            session_id (UUID str).
        """
        self.start_time = time.time()

        # Construire le prompt enrichi avec les 18 questions
        enriched_prompt = self._build_enriched_prompt()

        # Connexion Gemini Live
        self.session_id = await self.gemini.create_session(
            system_prompt=enriched_prompt,
            tools=GEMINI_TOOLS,
        )

        # Creer entree Supabase
        await self._supabase_create_session()

        logger.info(
            "Quiz demarre — session=%s user=%s",
            self.session_id,
            self.user_id,
        )
        return self.session_id

    def _build_enriched_prompt(self) -> str:
        """Injecte les 18 questions dans le system prompt."""
        questions_block = "\n\nQUESTIONS DU QUIZ (pose-les dans cet ordre) :\n"
        for i, q in enumerate(QUIZ_QUESTIONS, 1):
            questions_block += (
                f"\n{i}. [{q['id']}] (Axe: {AXE_LABELS[q['axe']]})\n"
                f"   {q['question']}\n"
            )
        return SYSTEM_PROMPT + questions_block

    # ----------------------------------------------------------
    # 3. handle_tool_call
    # ----------------------------------------------------------

    async def handle_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        args: dict,
    ) -> dict:
        """Traite un function call de Gemini (score_response ou finalize_quiz).

        Args:
            tool_name: Nom de la fonction appelee.
            tool_call_id: ID du call pour repondre a Gemini.
            args: Arguments du function call.

        Returns:
            Dictionnaire resultat a renvoyer a Gemini via send_tool_result.
        """
        if tool_name == "score_response":
            return await self._handle_score_response(args)

        if tool_name == "finalize_quiz":
            return await self._handle_finalize_quiz(args)

        logger.warning("Function call inconnue: %s", tool_name)
        return {"status": "error", "message": f"Unknown function: {tool_name}"}

    async def _handle_score_response(self, args: dict) -> dict:
        """Enregistre le score d'une question."""
        question_id = args["question_id"]
        axe = QUESTION_AXE_MAP.get(question_id)

        if axe is None:
            logger.error("question_id inconnu: %s", question_id)
            return {"status": "error", "message": f"Unknown question_id: {question_id}"}

        # Garde-fou doublon : Gemini re-score parfois la même question
        existing = next((s for s in self.scores if s.question_id == question_id), None)
        if existing is not None:
            logger.warning("Question %s déjà scorée, doublon ignoré", question_id)
            return {
                "status": "recorded",
                "question_id": question_id,
                "question_number": self.questions_answered,
                "total": 18,
            }

        score = QuestionScore(
            question_id=question_id,
            axe=axe,
            score=max(0, min(20, int(args["score"]))),
            justification=args["justification"],
            mots_cles_detectes=args.get("mots_cles_detectes", []),
        )
        self.scores.append(score)
        self.questions_answered = len(self.scores)

        logger.info(
            "Score enregistre — %s=%d/20 (question %d/18)",
            question_id,
            score.score,
            self.questions_answered,
        )

        # Mise a jour Supabase (non bloquant en cas d'erreur)
        await self._supabase_update_progress(score)

        return {
            "status": "recorded",
            "question_id": question_id,
            "question_number": self.questions_answered,
            "total": 18,
        }

    async def _handle_finalize_quiz(self, args: dict) -> dict:
        """Finalise le quiz, calcule les resultats, sauvegarde."""
        feedback = args.get("participant_feedback", "")
        points_forts = args.get("points_forts", [])
        axes_a_developper = args.get("axes_a_developper", [])

        self.result = self._calculate_results(
            feedback=feedback,
            points_forts=points_forts,
            axes_a_developper=axes_a_developper,
        )

        # Sauvegarder dans Supabase
        await self._save_to_supabase(self.result)

        logger.info(
            "Quiz finalise — session=%s score=%.1f%% niveau=%s",
            self.session_id,
            self.result.score_global_pct,
            self.result.niveau_global.value,
        )

        return {
            "status": "completed",
            "overall_score": self.result.score_global_pct,
            "level": self.result.niveau_global.value,
            "questions_scored": len(self.scores),
        }

    # ----------------------------------------------------------
    # 4. _calculate_results
    # ----------------------------------------------------------

    def _calculate_results(
        self,
        feedback: str = "",
        points_forts: Optional[list[str]] = None,
        axes_a_developper: Optional[list[str]] = None,
    ) -> QuizVocalResult:
        """Calcule les scores par axe et le resultat global.

        Scoring :
        - score_axe = (sum 3 questions) / 60 * 100
        - score_global = moyenne des 6 axes
        - niveau selon seuils 20/40/60/80
        """
        scores_axes = QuizVocalResult.calculer_scores_axes(self.scores)

        # Score global = moyenne des 6 axes
        axes_pcts = [a.score_pct for a in scores_axes]
        score_global = round(sum(axes_pcts) / len(axes_pcts), 1) if axes_pcts else 0.0

        # Duree
        duree = None
        if self.start_time is not None:
            duree = int(time.time() - self.start_time)

        return QuizVocalResult(
            session_id=self.session_id or "",
            user_id=self.user_id,
            scores_axes=scores_axes,
            score_global_pct=score_global,
            niveau_global=calcul_niveau(score_global),
            points_forts=points_forts or [],
            axes_a_developper=axes_a_developper or [],
            participant_feedback=feedback,
            duree_secondes=duree,
        )

    # ----------------------------------------------------------
    # 5. _save_to_supabase
    # ----------------------------------------------------------

    async def _save_to_supabase(self, result: QuizVocalResult) -> None:
        """Sauvegarde les resultats dans Supabase (voice_sessions + radar_results).

        Gracieux : log les erreurs sans bloquer le quiz.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # --- Update voice_sessions ---
        try:
            axes_json = [
                {
                    "axe": sa.axe.value,
                    "label": sa.label,
                    "score_brut": sa.score_brut,
                    "score_pct": sa.score_pct,
                    "niveau": sa.niveau.value,
                    "questions": [
                        {
                            "question_id": qs.question_id,
                            "score": qs.score,
                            "justification": qs.justification,
                            "mots_cles": qs.mots_cles_detectes,
                        }
                        for qs in sa.questions
                    ],
                }
                for sa in result.scores_axes
            ]

            self.supabase.table("voice_sessions").update({
                "status": "completed",
                "axes_scores": axes_json,
                "overall_score": result.score_global_pct,
                "level": result.niveau_global.value,
                "summary": result.participant_feedback,
                "questions_answered": self.questions_answered,
                "duration_seconds": result.duree_secondes,
                "completed_at": now_iso,
            }).eq("session_id", self.session_id).execute()

            logger.info("voice_sessions mis a jour — session=%s", self.session_id)
        except Exception as exc:
            logger.error(
                "Erreur Supabase voice_sessions update: %s", exc, exc_info=True
            )

        # --- Insert radar_results (table existante LiteraCIA) ---
        # Permet au flux Agent Claude #2 Skills Gap de fonctionner sans modification
        try:
            recommendations = []
            for sa in result.scores_axes:
                if sa.score_pct < 40:
                    recommendations.append(
                        f"Priorite haute : renforcer '{sa.label}' "
                        f"(score actuel {sa.score_pct:.0f}%)"
                    )
                elif sa.score_pct < 60:
                    recommendations.append(
                        f"A developper : '{sa.label}' "
                        f"(score actuel {sa.score_pct:.0f}%)"
                    )

            self.supabase.table("radar_results").insert({
                "user_id": self.user_id,
                "session_id": self.session_id,
                "overall_score": result.score_global_pct,
                "level": result.niveau_global.value,
                "axes": {
                    sa.axe.value: {
                        "score_pct": sa.score_pct,
                        "niveau": sa.niveau.value,
                    }
                    for sa in result.scores_axes
                },
                "recommendations": recommendations,
                "source": "voice_quiz_gemini_live",
                "created_at": now_iso,
            }).execute()

            logger.info("radar_results insere — user=%s", self.user_id)
        except Exception as exc:
            logger.error(
                "Erreur Supabase radar_results insert: %s", exc, exc_info=True
            )

    # ----------------------------------------------------------
    # Helpers Supabase (creation / progression)
    # ----------------------------------------------------------

    async def _supabase_create_session(self) -> None:
        """Cree l'entree initiale dans voice_sessions."""
        try:
            self.supabase.table("voice_sessions").insert({
                "session_id": self.session_id,
                "user_id": self.user_id,
                "language": self.language,
                "status": "active",
                "questions_answered": 0,
                "question_scores": [],
            }).execute()

            logger.debug("voice_sessions cree — session=%s", self.session_id)
        except Exception as exc:
            logger.error(
                "Erreur Supabase voice_sessions insert: %s", exc, exc_info=True
            )

    async def _supabase_update_progress(self, score: QuestionScore) -> None:
        """Met a jour la progression apres chaque question scoree."""
        try:
            # Lire les scores existants, ajouter le nouveau
            row = (
                self.supabase.table("voice_sessions")
                .select("question_scores")
                .eq("session_id", self.session_id)
                .single()
                .execute()
            )
            existing_scores = row.data.get("question_scores", []) if row.data else []
            existing_scores.append({
                "question_id": score.question_id,
                "axe": score.axe.value,
                "score": score.score,
                "justification": score.justification,
                "mots_cles": score.mots_cles_detectes,
            })

            self.supabase.table("voice_sessions").update({
                "questions_answered": self.questions_answered,
                "question_scores": existing_scores,
            }).eq("session_id", self.session_id).execute()

            logger.debug(
                "Progression MAJ — session=%s q=%d/18",
                self.session_id,
                self.questions_answered,
            )
        except Exception as exc:
            logger.error(
                "Erreur Supabase progress update: %s", exc, exc_info=True
            )

    # ----------------------------------------------------------
    # 6. save_partial_results (connexion tombee apres Q12+)
    # ----------------------------------------------------------

    MIN_QUESTIONS_FOR_PARTIAL = 12

    async def save_partial_results(self) -> Optional[QuizVocalResult]:
        """Sauvegarde les resultats partiels si assez de questions repondues.

        Appele quand la connexion Gemini tombe en cours de quiz.
        Calcule les scores uniquement sur les axes avec 3 questions completes.
        """
        if self.questions_answered < self.MIN_QUESTIONS_FOR_PARTIAL:
            logger.info(
                "Seulement %d questions — pas assez pour resultats partiels",
                self.questions_answered,
            )
            return None

        self.result = self._calculate_results(
            feedback=(
                f"Quiz interrompu apres {self.questions_answered}/18 questions. "
                f"Resultats partiels calcules sur les axes completes."
            ),
            points_forts=[],
            axes_a_developper=[],
        )

        # Marquer les axes incomplets
        for sa in self.result.scores_axes:
            if len(sa.questions) < 3:
                sa.niveau = calcul_niveau(0)
                sa.score_pct = 0.0
                sa.score_brut = 0

        # Recalculer le global sur les axes complets uniquement
        axes_complets = [sa for sa in self.result.scores_axes if len(sa.questions) == 3]
        if axes_complets:
            self.result.score_global_pct = round(
                sum(a.score_pct for a in axes_complets) / len(axes_complets), 1
            )
            self.result.niveau_global = calcul_niveau(self.result.score_global_pct)

        await self._save_to_supabase(self.result)

        logger.info(
            "Resultats partiels sauvegardes — session=%s questions=%d/18 "
            "axes_complets=%d/6 score=%.1f%%",
            self.session_id,
            self.questions_answered,
            len(axes_complets),
            self.result.score_global_pct,
        )
        return self.result

    # ----------------------------------------------------------
    # 7. get_session_status
    # ----------------------------------------------------------

    def get_session_status(self) -> dict:
        """Retourne l'etat courant du quiz.

        Returns:
            Dict avec questions_answered, scores partiels par axe,
            duree courante, et etat de connexion.
        """
        duree = None
        if self.start_time is not None:
            duree = int(time.time() - self.start_time)

        # Scores partiels par axe
        axes_partiels: dict[str, dict] = {}
        for axe in AxeRadar:
            qs = [s for s in self.scores if s.axe == axe]
            if qs:
                brut = sum(q.score for q in qs)
                axes_partiels[AXE_LABELS[axe]] = {
                    "questions_scored": len(qs),
                    "score_brut_partiel": brut,
                    "questions_ids": [q.question_id for q in qs],
                }

        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": "completed" if self.result else "active",
            "questions_answered": self.questions_answered,
            "total_questions": 18,
            "duree_secondes": duree,
            "gemini_connected": self.gemini.is_connected,
            "axes_partiels": axes_partiels,
        }
