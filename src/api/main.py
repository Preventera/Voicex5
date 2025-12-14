"""
VoiceX5 - API FastAPI Principale
Agents Vocaux SST Intelligents
Preventera / GenAISafety
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import des modules VoiceX5
from src.agents.voice_agent import VoiceAgentSST
from src.audio.fastrtc_handler import SSTAudioHandler, SessionManager


# ============================================================
# CONFIGURATION
# ============================================================

VERSION = "1.0.0"
DESCRIPTION = """
🎙️ **VoiceX5** - Agents Vocaux SST Intelligents

Plateforme d'agents vocaux temps réel pour la Santé et Sécurité au Travail,
propulsée par EDGY-AgenticX5.

## Fonctionnalités

* 📞 Réception d'appels téléphoniques (Twilio)
* 🎤 Transcription FR-CA haute précision
* 🧠 Agents LangGraph spécialisés SST
* 🔍 Recherche sémantique 793K incidents CNESST
* 📊 Knowledge Graph Neo4j (SafetyGraph)
* 🔔 Notifications automatiques multi-canal

## Architecture

5 niveaux AgenticX5: Collecte → Normalisation → Analyse → Recommandation → Orchestration
"""


# ============================================================
# LIFESPAN (Startup/Shutdown)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # Startup
    print("🚀 VoiceX5 démarrage...")
    app.state.audio_handler = SSTAudioHandler()
    app.state.session_manager = SessionManager()
    print("✅ VoiceX5 prêt!")
    
    yield
    
    # Shutdown
    print("🛑 VoiceX5 arrêt...")
    # Fermer les connexions
    print("✅ VoiceX5 arrêté proprement")


# ============================================================
# APPLICATION FASTAPI
# ============================================================

app = FastAPI(
    title="VoiceX5",
    description=DESCRIPTION,
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODÈLES PYDANTIC
# ============================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: dict


class TextMessageRequest(BaseModel):
    message: str
    call_id: Optional[str] = None
    caller_phone: Optional[str] = None


class TextMessageResponse(BaseModel):
    response: str
    call_id: str
    intent: Optional[str] = None
    entities: Optional[dict] = None


class OutboundCallRequest(BaseModel):
    to_number: str
    message: Optional[str] = "Bonjour, ceci est un appel de suivi VoiceX5."


# ============================================================
# ROUTES: Health & Info
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Page d'accueil"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VoiceX5 - Agents Vocaux SST</title>
        <style>
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                color: #e2e8f0;
                min-height: 100vh;
            }}
            h1 {{ 
                background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.5rem;
            }}
            .status {{ 
                padding: 15px; 
                background: rgba(34, 197, 94, 0.2); 
                border: 1px solid #22c55e;
                border-radius: 10px; 
                margin: 20px 0;
            }}
            .endpoint {{ 
                background: rgba(71, 85, 105, 0.5); 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 8px;
                border-left: 4px solid #3b82f6;
            }}
            a {{ color: #60a5fa; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            code {{ 
                background: rgba(0,0,0,0.3); 
                padding: 2px 6px; 
                border-radius: 4px;
                font-family: 'Fira Code', monospace;
            }}
        </style>
    </head>
    <body>
        <h1>🎙️ VoiceX5</h1>
        <p>Agents Vocaux SST Intelligents - Propulsé par AgenticX5</p>
        
        <div class="status">
            ✅ Service actif - Version {VERSION}
        </div>
        
        <h2>📡 Points d'entrée</h2>
        
        <div class="endpoint">
            <strong>WebSocket Audio</strong><br>
            <code>ws://localhost:8000/ws/audio</code>
        </div>
        
        <div class="endpoint">
            <strong>WebSocket Twilio</strong><br>
            <code>ws://localhost:8000/ws/twilio</code>
        </div>
        
        <div class="endpoint">
            <strong>API REST</strong><br>
            <code>POST /api/v1/message</code> - Traiter un message texte
        </div>
        
        <h2>📚 Documentation</h2>
        <p>
            <a href="/docs">Swagger UI</a> | 
            <a href="/redoc">ReDoc</a> |
            <a href="/health">Health Check</a>
        </p>
        
        <h2>🏗️ Architecture</h2>
        <p>5 Niveaux AgenticX5:</p>
        <ol>
            <li>📡 Collecte (FastRTC + faster-whisper)</li>
            <li>🔄 Normalisation (Intent + Entity extraction)</li>
            <li>🔍 Analyse (Superlinked + Risk scoring)</li>
            <li>💡 Recommandation (Procédures + Actions)</li>
            <li>🎭 Orchestration (HUGO + Human-in-loop)</li>
        </ol>
        
        <hr style="border-color: #475569; margin: 30px 0;">
        <p style="color: #64748b;">
            Preventera / GenAISafety<br>
            Projet EDGY-AgenticX5
        </p>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérification de l'état du service"""
    return HealthResponse(
        status="healthy",
        version=VERSION,
        timestamp=datetime.now().isoformat(),
        services={
            "api": "up",
            "audio_handler": "up",
            "neo4j": "checking...",
            "qdrant": "checking...",
            "redis": "checking..."
        }
    )


@app.get("/api/v1/stats")
async def get_stats():
    """Statistiques d'utilisation"""
    return {
        "total_calls_today": 0,
        "active_sessions": len(app.state.session_manager.sessions) if hasattr(app.state, 'session_manager') else 0,
        "incidents_created_today": 0,
        "avg_call_duration_seconds": 0,
        "resolution_rate_percent": 0
    }


# ============================================================
# ROUTES: API Text (pour tests sans audio)
# ============================================================

@app.post("/api/v1/message", response_model=TextMessageResponse)
async def process_text_message(request: TextMessageRequest):
    """
    Traite un message texte comme s'il venait d'un appel vocal.
    Utile pour les tests et l'intégration.
    """
    call_id = request.call_id or f"TEXT-{uuid.uuid4().hex[:8]}"
    
    # Créer un agent
    agent = VoiceAgentSST()
    agent.start_session(call_id, request.caller_phone or "api-test")
    
    # Traiter le message
    response = agent.process_message(call_id, request.message)
    
    # Récupérer le contexte
    session = agent.active_sessions.get(call_id, {})
    
    return TextMessageResponse(
        response=response,
        call_id=call_id,
        intent=str(session.get("intent")) if session.get("intent") else None,
        entities=session.get("entities")
    )


# ============================================================
# ROUTES: WebSocket Audio
# ============================================================

@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    """
    WebSocket pour le streaming audio bidirectionnel.
    Utilisé par l'interface Gradio ou toute autre interface audio.
    """
    await websocket.accept()
    call_id = f"WS-{uuid.uuid4().hex[:8]}"
    
    print(f"🎙️ Connexion WebSocket audio: {call_id}")
    
    try:
        async def audio_generator():
            while True:
                data = await websocket.receive_bytes()
                yield data
        
        audio_handler = app.state.audio_handler
        
        async for response_audio in audio_handler.process_audio_stream(
            audio_generator(),
            call_id=call_id,
            caller_phone="websocket"
        ):
            await websocket.send_bytes(response_audio)
            
    except Exception as e:
        print(f"❌ Erreur WebSocket: {e}")
    finally:
        print(f"📴 Déconnexion WebSocket: {call_id}")
        await websocket.close()


@app.websocket("/ws/twilio")
async def websocket_twilio(websocket: WebSocket):
    """
    WebSocket pour Twilio Media Streams.
    Gère le protocole spécifique de Twilio.
    """
    await websocket.accept()
    call_id = None
    
    try:
        while True:
            message = await websocket.receive_json()
            event = message.get("event")
            
            if event == "start":
                start_data = message.get("start", {})
                call_id = start_data.get("callSid", f"TWILIO-{uuid.uuid4().hex[:8]}")
                caller = start_data.get("from", "unknown")
                print(f"📞 Appel Twilio démarré: {call_id} depuis {caller}")
                
            elif event == "media":
                # Traiter l'audio (simplifié)
                pass
                
            elif event == "stop":
                print(f"📴 Appel Twilio terminé: {call_id}")
                break
                
    except Exception as e:
        print(f"❌ Erreur Twilio WebSocket: {e}")
    finally:
        if call_id:
            app.state.session_manager.end_session(call_id)


# ============================================================
# ROUTES: Twilio Webhooks
# ============================================================

@app.post("/twilio/voice")
async def twilio_voice_webhook(request: Request):
    """
    Webhook pour les appels entrants Twilio.
    Retourne le TwiML pour connecter au WebSocket.
    """
    try:
        from twilio.twiml.voice_response import VoiceResponse, Connect
        
        response = VoiceResponse()
        
        # Message d'accueil
        response.say(
            "Bienvenue sur la ligne SST VoiceX5. Veuillez patienter pendant la connexion.",
            voice="alice",
            language="fr-CA"
        )
        
        # Connecter au WebSocket
        stream_url = os.getenv("STREAM_URL", "wss://localhost:8000/ws/twilio")
        connect = Connect()
        connect.stream(url=stream_url)
        response.append(connect)
        
        return HTMLResponse(
            content=str(response),
            media_type="application/xml"
        )
        
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Twilio SDK not installed. Run: pip install twilio"
        )


@app.post("/twilio/outbound")
async def make_outbound_call(request: OutboundCallRequest):
    """
    Initie un appel sortant (pour les suivis automatiques).
    """
    try:
        from twilio.rest import Client
        
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        
        call = client.calls.create(
            to=request.to_number,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            url=f"{base_url}/twilio/outbound-twiml"
        )
        
        return {
            "call_sid": call.sid,
            "status": call.status,
            "to": request.to_number
        }
        
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Twilio SDK not installed"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate call: {str(e)}"
        )


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🎙️  VOICEX5 - Agents Vocaux SST                           ║
    ║                                                              ║
    ║   Propulsé par EDGY-AgenticX5                                ║
    ║   Preventera / GenAISafety                                   ║
    ║                                                              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║   🌐 API:     http://{host}:{port}                           ║
    ║   📚 Docs:    http://{host}:{port}/docs                      ║
    ║   🎤 Audio:   ws://{host}:{port}/ws/audio                    ║
    ║   📞 Twilio:  ws://{host}:{port}/ws/twilio                   ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=os.getenv("ENV") == "development"
    )
