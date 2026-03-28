"""
VOICEX5-GEMINI-LIVE — API FastAPI Voice Quiz
=============================================
Serveur autonome : endpoints REST + WebSocket bidirectionnel
pour le quiz radar vocal LiteraCIA via Gemini Live API.

Port 8001 (ne conflite pas avec LiteraCIA sur 5000).

Usage:
    python -m voice.api_voice
    # ou
    uvicorn voice.api_voice:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from voice.gemini_live_service import GeminiMessageType
from voice.voice_config import GEMINI_API_KEY, VoiceSessionCreate, VoiceSessionResponse
from voice.voice_quiz_agent import VoiceQuizAgent

load_dotenv()

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("voicex5.api")

# ============================================================
# Supabase client (gracieux si absent)
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase_client = None
_demo_mode = False


def _init_supabase():
    """Initialise le client Supabase. Mode demo si absent."""
    global _supabase_client, _demo_mode

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning(
            "SUPABASE_URL ou SUPABASE_KEY manquant — mode demo (pas de persistance)"
        )
        _demo_mode = True
        return

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY manquant — le quiz vocal ne fonctionnera pas")

    try:
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Client Supabase connecte — %s", SUPABASE_URL[:40] + "...")
    except ImportError:
        logger.warning("Module supabase non installe — mode demo")
        _demo_mode = True
    except Exception as exc:
        logger.error("Erreur connexion Supabase: %s — mode demo", exc)
        _demo_mode = True


class _DemoSupabase:
    """Stub Supabase pour le mode demo (log au lieu de persister)."""

    def table(self, name: str):
        return self

    def insert(self, data):
        logger.debug("DEMO insert %s", json.dumps(data, default=str)[:200])
        return self

    def update(self, data):
        logger.debug("DEMO update %s", json.dumps(data, default=str)[:200])
        return self

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def single(self):
        return self

    def execute(self):
        from types import SimpleNamespace
        return SimpleNamespace(data={"question_scores": []})


def _get_supabase():
    """Retourne le client Supabase ou le stub demo."""
    if _supabase_client is not None:
        return _supabase_client
    return _DemoSupabase()


# ============================================================
# Sessions actives (en memoire pour lookup REST)
# ============================================================

_active_agents: dict[str, VoiceQuizAgent] = {}

# ============================================================
# FastAPI app
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_supabase()
    mode = "DEMO" if _demo_mode else "PRODUCTION"
    logger.info("VoiceX5 API demarree — mode %s", mode)
    yield
    # Cleanup : fermer toutes les sessions Gemini actives
    for sid, agent in list(_active_agents.items()):
        try:
            await agent.gemini.close_session()
        except Exception:
            pass
    _active_agents.clear()
    logger.info("VoiceX5 API arretee — %d sessions nettoyees", len(_active_agents))


app = FastAPI(
    title="VoiceX5 Gemini Live — LiteraCIA Voice API",
    description=(
        "Quiz Radar Vocal — 18 questions ouvertes scorees en temps reel "
        "via Gemini Live API (audio natif, <1s latence)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 2. WebSocket endpoint — /ws/voice/quiz
# ============================================================

@app.websocket("/ws/voice/quiz")
async def ws_voice_quiz(websocket: WebSocket):
    """WebSocket bidirectionnel : frontend <-> Gemini Live.

    Protocole :
    1. Client envoie JSON init : {"user_id": "xxx", "language": "fr-CA"}
    2. Serveur repond JSON : {"type": "session_started", "session_id": "..."}
    3. Boucle bidirectionnelle :
       - Client envoie bytes (audio PCM16) ou JSON (commandes)
       - Serveur envoie bytes (audio Gemini) ou JSON (events)
    """
    await websocket.accept()
    agent: Optional[VoiceQuizAgent] = None
    session_id: Optional[str] = None

    try:
        # --- Phase 1 : Init ---
        raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_msg = json.loads(raw_init)
        user_id = init_msg["user_id"]
        language = init_msg.get("language", "fr-CA")

        logger.info("WS connexion — user=%s lang=%s", user_id, language)

        # Creer agent et demarrer quiz
        agent = VoiceQuizAgent(
            user_id=user_id,
            supabase_client=_get_supabase(),
            language=language,
        )
        session_id = await agent.start_quiz()
        _active_agents[session_id] = agent

        # Confirmer au frontend
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "total_questions": 18,
            "message": "Quiz radar vocal demarre. Gemini vous accueille.",
        })

        # --- Phase 2 : Boucle bidirectionnelle ---
        await _run_bidirectional_loop(websocket, agent)

    except WebSocketDisconnect:
        logger.info("WS deconnecte — session=%s", session_id)
        if agent and not agent.result:
            await _mark_abandoned(agent)

    except ConnectionError as exc:
        logger.warning("Connexion Gemini perdue — session=%s: %s", session_id, exc)
        if agent and not agent.result:
            await _mark_abandoned(agent)
        await _ws_send_error(websocket, f"Connexion Gemini perdue: {exc}")

    except asyncio.TimeoutError:
        logger.warning("WS timeout init — pas de message user_id recu")
        await _ws_send_error(websocket, "Timeout: message init attendu dans 30s")

    except json.JSONDecodeError as exc:
        logger.warning("WS JSON invalide init: %s", exc)
        await _ws_send_error(websocket, f"JSON invalide: {exc}")

    except Exception as exc:
        logger.error("Erreur WS inattendue: %s", exc, exc_info=True)
        await _ws_send_error(websocket, "Erreur serveur interne")

    finally:
        # Cleanup
        if agent:
            await agent.gemini.close_session()
        if session_id and session_id in _active_agents:
            del _active_agents[session_id]


async def _run_bidirectional_loop(
    websocket: WebSocket,
    agent: VoiceQuizAgent,
) -> None:
    """Deux taches paralleles : frontend→Gemini et Gemini→frontend."""

    async def frontend_to_gemini():
        """Recoit audio/commandes du frontend, relaie a Gemini."""
        while True:
            msg = await websocket.receive()

            # Audio binaire
            if "bytes" in msg and msg["bytes"]:
                await agent.gemini.relay_audio_to_gemini(msg["bytes"])

            # Commande JSON texte
            elif "text" in msg and msg["text"]:
                data = json.loads(msg["text"])
                if data.get("type") == "stop":
                    logger.info("Arret demande par le client")
                    break
                elif data.get("type") == "status":
                    status = agent.get_session_status()
                    await websocket.send_json({"type": "status", **status})

    async def gemini_to_frontend():
        """Recoit messages Gemini, dispatch au frontend."""
        async for msg in agent.gemini.receive_from_gemini():
            if msg.type == GeminiMessageType.AUDIO:
                await websocket.send_bytes(msg.data)

            elif msg.type == GeminiMessageType.TOOL_CALL:
                # Traiter le function call cote serveur
                result = await agent.handle_tool_call(
                    msg.function_name, msg.tool_call_id, msg.function_args
                )
                # Renvoyer le resultat a Gemini pour qu'il continue
                await agent.gemini.send_tool_result(msg.tool_call_id, result)

                # Notifier le frontend de la progression
                await websocket.send_json({
                    "type": "tool_call_processed",
                    "function": msg.function_name,
                    "result": result,
                })

            elif msg.type == GeminiMessageType.TRANSCRIPT:
                await websocket.send_json({
                    "type": "transcript",
                    "text": msg.data,
                })

            elif msg.type == GeminiMessageType.TURN_COMPLETE:
                await websocket.send_json({"type": "turn_complete"})

            elif msg.type == GeminiMessageType.ERROR:
                await websocket.send_json({
                    "type": "error",
                    "message": str(msg.data),
                })
                break

    # Lancer les deux taches en parallele — la premiere qui termine arrete l'autre
    task_f2g = asyncio.create_task(frontend_to_gemini())
    task_g2f = asyncio.create_task(gemini_to_frontend())

    done, pending = await asyncio.wait(
        {task_f2g, task_g2f},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Propager les exceptions des taches terminees
    for task in done:
        if task.exception() and not isinstance(task.exception(), asyncio.CancelledError):
            raise task.exception()


async def _mark_abandoned(agent: VoiceQuizAgent) -> None:
    """Marque une session comme abandonnee ou sauvegarde les resultats partiels."""
    # Si 12+ questions, sauvegarder comme completed_partial
    if agent.questions_answered >= agent.MIN_QUESTIONS_FOR_PARTIAL:
        try:
            result = await agent.save_partial_results()
            if result:
                sb = _get_supabase()
                sb.table("voice_sessions").update({
                    "status": "completed_partial",
                }).eq("session_id", agent.session_id).execute()
                logger.info(
                    "Session sauvegardee partielle — %s (%d/18 questions, score=%.1f%%)",
                    agent.session_id,
                    agent.questions_answered,
                    result.score_global_pct,
                )
                return
        except Exception as exc:
            logger.error("Erreur sauvegarde partielle: %s", exc)

    # Sinon marquer comme abandonnee
    try:
        sb = _get_supabase()
        sb.table("voice_sessions").update({
            "status": "abandoned",
            "questions_answered": agent.questions_answered,
            "abandoned_at": datetime.now(timezone.utc).isoformat(),
        }).eq("session_id", agent.session_id).execute()

        logger.info(
            "Session marquee abandonnee — %s (%d/18 questions)",
            agent.session_id,
            agent.questions_answered,
        )
    except Exception as exc:
        logger.error("Erreur marquage abandon: %s", exc)


async def _ws_send_error(websocket: WebSocket, message: str) -> None:
    """Envoie un message d'erreur JSON au client WebSocket (best-effort)."""
    try:
        await websocket.send_json({"type": "error", "message": message})
    except Exception:
        pass


# ============================================================
# 3. REST endpoints
# ============================================================

@app.post("/api/voice/sessions", response_model=VoiceSessionResponse)
async def create_voice_session(body: VoiceSessionCreate):
    """Cree une session quiz vocal (alternative REST).

    Le client doit ensuite se connecter au WebSocket avec le session_id.
    """
    agent = VoiceQuizAgent(
        user_id=body.user_id,
        supabase_client=_get_supabase(),
        language=body.langue,
    )
    session_id = await agent.start_quiz()
    _active_agents[session_id] = agent

    return VoiceSessionResponse(
        session_id=session_id,
        websocket_url=f"/ws/voice/quiz",
        total_questions=18,
        duree_estimee_minutes=15,
    )


@app.get("/api/voice/sessions/{session_id}")
async def get_voice_session(session_id: str):
    """Retourne l'etat d'une session quiz vocal."""
    agent = _active_agents.get(session_id)
    if agent:
        return agent.get_session_status()

    # Session pas en memoire — chercher dans Supabase
    try:
        sb = _get_supabase()
        row = (
            sb.table("voice_sessions")
            .select("*")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        if row.data:
            return row.data
    except Exception as exc:
        logger.error("Erreur lecture session %s: %s", session_id, exc)

    return {"error": "Session non trouvee", "session_id": session_id}


@app.get("/api/voice/results/{user_id}")
async def get_user_results(user_id: str, limit: int = 10):
    """Retourne l'historique des quiz vocaux d'un utilisateur."""
    try:
        sb = _get_supabase()
        rows = (
            sb.table("radar_results")
            .select("*")
            .eq("user_id", user_id)
            .eq("source", "voice_quiz_gemini_live")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"user_id": user_id, "results": rows.data or []}
    except Exception as exc:
        logger.error("Erreur lecture resultats user %s: %s", user_id, exc)
        return {"user_id": user_id, "results": [], "error": str(exc)}


@app.post("/api/voice/skills-gap")
async def skills_gap_analysis(body: dict):
    """Analyse les resultats d'un quiz et genere un plan d'apprentissage via Claude.

    Body: {"session_id": "xxx"} ou {"user_id": "xxx", "session_id": "xxx"}
    """
    session_id = body.get("session_id")
    if not session_id:
        return {"error": "session_id requis"}

    # 1. Recuperer les scores depuis memoire ou Supabase
    session_data = None
    agent = _active_agents.get(session_id)
    if agent:
        session_data = agent.get_session_status()
    else:
        try:
            sb = _get_supabase()
            row = (
                sb.table("voice_sessions")
                .select("*")
                .eq("session_id", session_id)
                .single()
                .execute()
            )
            session_data = row.data
        except Exception as exc:
            logger.error("Erreur lecture session %s: %s", session_id, exc)

    if not session_data:
        return {"error": "Session non trouvee", "session_id": session_id}

    # 2. Extraire les scores par axe
    user_id = session_data.get("user_id", body.get("user_id", "unknown"))
    overall_score = session_data.get("overall_score") or 0
    level = session_data.get("level") or "Novice"
    summary = session_data.get("summary") or ""

    # Construire axes_scores depuis axes_scores (Supabase) ou axes_partiels (memoire)
    axes_scores = {}
    raw_axes = session_data.get("axes_scores") or session_data.get("axes_partiels") or {}
    if isinstance(raw_axes, list):
        # Format Supabase: [{axe, score_pct, niveau, ...}, ...]
        for ax in raw_axes:
            axe_key = ax.get("axe", "")
            axes_scores[axe_key] = {
                "score_pct": ax.get("score_pct", 0),
                "niveau": ax.get("niveau", "—"),
            }
    elif isinstance(raw_axes, dict):
        # Format memoire: {label -> {score_brut_partiel, ...}}
        key_map = {
            "Compr. Technique IA": "comprehension_technique_ia",
            "Comprehension Technique IA": "comprehension_technique_ia",
            "Usage Operationnel": "usage_operationnel",
            "Pensee Critique": "pensee_critique",
            "Ethique & Conformite": "ethique_conformite",
            "Collaboration Humain-IA": "collaboration_humain_ia",
            "Collab. Humain-IA": "collaboration_humain_ia",
            "Apprentissage Continu": "apprentissage_continu",
        }
        for label, data in raw_axes.items():
            key = key_map.get(label, label)
            if isinstance(data, dict):
                brut = data.get("score_brut_partiel", 0)
                pct = round((brut / 60) * 100) if brut else data.get("score_pct", 0)
                axes_scores[key] = {"score_pct": pct, "niveau": data.get("niveau", "—")}

    # 3. Appeler le SkillsGapAgent
    try:
        from voice.skills_gap_agent import SkillsGapAgent

        gap_agent = SkillsGapAgent()
        analysis = await gap_agent.analyze(
            user_id=user_id,
            axes_scores=axes_scores,
            overall_score=overall_score,
            level=level,
            summary=summary,
        )
    except Exception as exc:
        logger.error("Erreur skills gap analysis: %s", exc, exc_info=True)
        return {"error": f"Erreur analyse: {exc}", "session_id": session_id}

    # 4. Sauvegarder dans Supabase (dans voice_sessions.summary si pas de table dediee)
    try:
        sb = _get_supabase()
        sb.table("voice_sessions").update({
            "summary": json.dumps(analysis, ensure_ascii=False)[:10000],
        }).eq("session_id", session_id).execute()
        logger.info("Skills gap analysis sauvegardee — session=%s", session_id)
    except Exception as exc:
        logger.warning("Erreur sauvegarde skills gap: %s", exc)

    return {
        "status": "ok",
        "session_id": session_id,
        "user_id": user_id,
        "analysis": analysis,
    }


@app.get("/health")
async def health_check():
    """Health check — statut API + Supabase + Gemini."""
    supabase_ok = False
    if not _demo_mode and _supabase_client:
        try:
            _supabase_client.table("voice_sessions").select("session_id").limit(1).execute()
            supabase_ok = True
        except Exception:
            pass

    return {
        "status": "ok",
        "service": "VoiceX5 Gemini Live",
        "version": "0.1.0",
        "mode": "demo" if _demo_mode else "production",
        "gemini_api_key_set": bool(GEMINI_API_KEY),
        "supabase_connected": supabase_ok,
        "active_sessions": len(_active_agents),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# 4. Point d'entree __main__
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "voice.api_voice:app",
        host="127.0.0.1",
        port=int(os.getenv("VOICE_PORT", "8003")),
        reload=True,
        log_level="info",
    )
