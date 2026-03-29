"""
SafeTalkX5 — API FastAPI endpoints
====================================
Generateur de causeries SST vocales. Peut tourner standalone (port 8002)
ou etre integre dans voice/api_voice.py via include_router.

Pipeline : Incident → Analyse (4 methodes) → Storytelling (7 principes) → Narration vocale
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from safetalk.analysis_engine import AnalysisEngine
from safetalk.cnesst_parser import CNESSTParser, RISK_FILTERS
from safetalk.osha_scraper import OSHAScraper
from safetalk.safetalk_generator import SafeTalkGenerator
from safetalk.safetalk_voice import SafeTalkVoice

load_dotenv()

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("safetalkx5.api")

# ============================================================
# Singletons (inits lourds faits une seule fois)
# ============================================================
_cnesst: Optional[CNESSTParser] = None
_osha: Optional[OSHAScraper] = None
_analysis: Optional[AnalysisEngine] = None
_generator: Optional[SafeTalkGenerator] = None

# Stockage des talks generes (en memoire pour le MVP)
_generated_talks: dict[str, dict] = {}

# Sessions de narration actives
_narration_sessions: dict[str, SafeTalkVoice] = {}

# Stats
_stats = {"talks_generated": 0, "narrations_started": 0}


def _init_services() -> None:
    """Initialise les services une seule fois."""
    global _cnesst, _osha, _analysis, _generator

    if _cnesst is None:
        _cnesst = CNESSTParser()
        logger.info("CNESSTParser charge — %d records", len(_cnesst.df))

    if _osha is None:
        _osha = OSHAScraper()
        logger.info("OSHAScraper initialise")

    if _analysis is None:
        _analysis = AnalysisEngine()
        logger.info("AnalysisEngine initialise — mode %s", _analysis.mode)

    if _generator is None:
        _generator = SafeTalkGenerator()
        logger.info("SafeTalkGenerator initialise — mode %s", _generator.mode)


# ============================================================
# Router (pour integration dans api_voice.py)
# ============================================================
router = APIRouter(prefix="/api/safetalk", tags=["SafeTalkX5"])


# ----------------------------------------------------------
# 1. POST /api/safetalk/generate
# ----------------------------------------------------------

@router.post("/generate")
async def generate_safetalk(body: dict):
    """Genere une causerie SST complete.

    Pipeline : Incident → Analyse (4 methodes) → Storytelling (7 principes)

    Body:
        secteur_scian: Code SCIAN (ex: "23" pour Construction)
        risk_type: Type de risque (optionnel): chute, tms, machine, etc.
        mode: "sst_pur" ou "ia_sst"
        duree_minutes: 5, 7 ou 10
        langue: "fr" ou "en"
        role_animateur: "superviseur", "hse", "formateur"
        source: "cnesst", "osha" ou "auto"
    """
    _init_services()
    start_time = time.time()

    secteur = body.get("secteur_scian")
    risk_type = body.get("risk_type")
    mode = body.get("mode", "sst_pur")
    duree = body.get("duree_minutes", 5)
    langue = body.get("langue", "fr")
    role = body.get("role_animateur", "superviseur")
    source = body.get("source", "auto")

    # 1. Selectionner un incident
    incident = _select_incident(source, secteur, risk_type, mode)
    if not incident:
        return {"error": "Aucun incident trouve pour les criteres donnes"}

    # 2. Analyser l'incident (4 methodes en parallele)
    analysis = await _analysis.analyze_incident(incident)

    # 3. Generer le talk (7 principes storytelling)
    config = {
        "mode": mode,
        "duree_minutes": duree,
        "langue": langue,
        "role_animateur": role,
    }
    talk = await _generator.generate(incident, analysis, config)

    # 4. Attribuer un ID unique et stocker
    talk_id = str(uuid.uuid4())
    talk["talk_id"] = talk_id
    talk["incident"] = {k: v for k, v in incident.items() if k != "contexte_secteur"}
    talk["analysis_summary"] = analysis.get("synthese", {})
    talk["generation_time_s"] = round(time.time() - start_time, 2)
    talk["generated_at"] = datetime.now(timezone.utc).isoformat()

    _generated_talks[talk_id] = talk
    _stats["talks_generated"] += 1

    logger.info(
        "Talk genere — id=%s titre='%s' mode=%s duree=%dmin en %.1fs",
        talk_id, talk.get("titre", "?")[:50], mode, duree, talk["generation_time_s"],
    )

    return talk


def _select_incident(
    source: str, secteur: Optional[str], risk_type: Optional[str], mode: str
) -> dict:
    """Selectionne un incident depuis CNESST, OSHA ou auto."""
    if source == "osha":
        return _osha.get_random_incident_for_safetalk(
            secteur_scian=secteur, risk_type=risk_type,
        )

    if source == "cnesst":
        return _cnesst.get_random_incident_for_safetalk(
            secteur_scian=secteur, risk_type=risk_type, mode=mode,
        )

    # Auto : CNESST en priorite, fallback OSHA
    incident = _cnesst.get_random_incident_for_safetalk(
        secteur_scian=secteur, risk_type=risk_type, mode=mode,
    )
    if incident:
        return incident

    return _osha.get_random_incident_for_safetalk(
        secteur_scian=secteur, risk_type=risk_type,
    )


# ----------------------------------------------------------
# 2. POST /api/safetalk/generate-and-narrate
# ----------------------------------------------------------

@router.post("/generate-and-narrate")
async def generate_and_narrate(body: dict):
    """Genere un talk ET prepare une session de narration vocale.

    Retourne le talk + un narration_session_id pour le WebSocket.
    """
    # Generer le talk
    talk_response = await generate_safetalk(body)

    if "error" in talk_response:
        return talk_response

    talk_id = talk_response.get("talk_id")
    narration_session_id = str(uuid.uuid4())

    talk_response["narration_session_id"] = narration_session_id
    talk_response["narration_ws_url"] = f"/ws/safetalk/narrate?session_id={narration_session_id}&talk_id={talk_id}"

    logger.info(
        "Talk + narration prepare — talk_id=%s narration=%s",
        talk_id, narration_session_id,
    )
    return talk_response


# ----------------------------------------------------------
# 3. WebSocket /ws/safetalk/narrate
# ----------------------------------------------------------

@router.websocket("/narrate")
async def ws_narrate(websocket: WebSocket):
    """WebSocket de narration vocale.

    Le client envoie un JSON init avec talk_id.
    Le serveur stream l'audio Gemini Live section par section.
    """
    await websocket.accept()
    voice: Optional[SafeTalkVoice] = None

    try:
        # Phase 1 : Init — recevoir talk_id
        raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
        init_msg = json.loads(raw_init)
        talk_id = init_msg.get("talk_id")

        if not talk_id or talk_id not in _generated_talks:
            await websocket.send_json({"type": "error", "message": f"Talk non trouve: {talk_id}"})
            return

        talk = _generated_talks[talk_id]

        # Phase 2 : Demarrer la narration
        voice = SafeTalkVoice()
        _stats["narrations_started"] += 1

        await websocket.send_json({
            "type": "narration_starting",
            "talk_id": talk_id,
            "titre": talk.get("titre", ""),
            "sections": len(talk.get("sections", [])),
        })

        # Phase 3 : Stream audio + events
        async for event in voice.stream_narration(talk):
            if event["type"] == "audio":
                await websocket.send_bytes(event["data"])
            else:
                await websocket.send_json(event)

    except WebSocketDisconnect:
        logger.info("Client narration deconnecte")

    except asyncio.TimeoutError:
        logger.warning("Timeout init narration")
        try:
            await websocket.send_json({"type": "error", "message": "Timeout: envoyez {talk_id} dans 30s"})
        except Exception:
            pass

    except Exception as exc:
        logger.error("Erreur narration WS: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass

    finally:
        if voice:
            await voice.stop_narration()


# ----------------------------------------------------------
# 4. GET /api/safetalk/sectors
# ----------------------------------------------------------

@router.get("/sectors")
async def list_sectors():
    """Liste des secteurs SCIAN disponibles avec nb d'incidents."""
    _init_services()
    sectors = _cnesst.list_sectors()
    return {"sectors": sectors, "total": len(sectors)}


# ----------------------------------------------------------
# 5. GET /api/safetalk/risk-types
# ----------------------------------------------------------

@router.get("/risk-types")
async def list_risk_types():
    """Types de risques disponibles avec count d'incidents par type."""
    _init_services()
    result = []
    for risk_type in RISK_FILTERS:
        incidents = _cnesst.get_incidents_by_risk(risk_type, limit=1)
        # Compter plus efficacement
        count = len(_cnesst.get_incidents_by_risk(risk_type, limit=9999))
        result.append({
            "type": risk_type,
            "label": risk_type.replace("_", " ").title(),
            "count": count,
            "available": count > 0,
        })
    return {"risk_types": result}


# ----------------------------------------------------------
# 6. GET /api/safetalk/stats
# ----------------------------------------------------------

@router.get("/stats")
async def get_stats():
    """Stats globales SafeTalkX5."""
    _init_services()
    return {
        "service": "SafeTalkX5",
        "version": "0.1.0",
        "cnesst_records": len(_cnesst.df),
        "osha_available": _osha is not None,
        "analysis_mode": _analysis.mode,
        "generator_mode": _generator.mode,
        "talks_generated": _stats["talks_generated"],
        "narrations_started": _stats["narrations_started"],
        "talks_in_memory": len(_generated_talks),
        "sectors_available": len(_cnesst.list_sectors()),
        "risk_types_available": len(RISK_FILTERS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------
# 7. GET /api/safetalk/talks/{talk_id}
# ----------------------------------------------------------

@router.get("/talks/{talk_id}")
async def get_talk(talk_id: str):
    """Recupere un talk genere par son ID."""
    talk = _generated_talks.get(talk_id)
    if not talk:
        return {"error": "Talk non trouve", "talk_id": talk_id}
    return talk


# ============================================================
# Standalone app (port 8002)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_services()
    logger.info("SafeTalkX5 API demarree — standalone mode")
    yield
    # Cleanup narrations actives
    for sid, voice in list(_narration_sessions.items()):
        try:
            await voice.stop_narration()
        except Exception:
            pass
    _narration_sessions.clear()
    logger.info("SafeTalkX5 API arretee")


app = FastAPI(
    title="SafeTalkX5 — Generateur de causeries SST vocales",
    description=(
        "Genere des causeries SST narratives basees sur des accidents reels "
        "CNESST/OSHA, analysees avec 4 methodes (ADC, ICAM, Bow-Tie, HFACS) "
        "et racontees avec les 7 principes de storytelling."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure le router
app.include_router(router)


# Health check standalone
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "SafeTalkX5",
        "mode": "standalone",
    }


# ============================================================
# Point d'entree __main__
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "safetalk.api_safetalk:app",
        host="127.0.0.1",
        port=int(os.getenv("SAFETALK_PORT", "8002")),
        reload=True,
        log_level="info",
    )
