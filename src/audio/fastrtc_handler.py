"""
FastRTC SST Handler - EDGY AgenticX5
Gestionnaire de flux audio temps réel pour l'agent vocal SST

Adapté du cours: neural-maze/realtime-phone-agents-course
Pour: Preventera / GenAISafety
"""

import os
import asyncio
import uuid
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from fastrtc import ReplyOnPause, Stream, get_stt_model, get_tts_model
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
import httpx

from voice_agent_sst import VoiceAgentSST


# ============================================================
# CONFIGURATION
# ============================================================

# STT Configuration (faster-whisper)
STT_MODEL = os.getenv("STT_MODEL", "large-v3")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "fr")  # Français canadien
STT_DEVICE = os.getenv("STT_DEVICE", "cuda")    # GPU si disponible

# TTS Configuration (Orpheus 3B via llama.cpp)
TTS_ENDPOINT = os.getenv("TTS_ENDPOINT", "http://localhost:8080")
TTS_VOICE = os.getenv("TTS_VOICE", "french_female")  # Voix française pro

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Sample rates
INPUT_SAMPLE_RATE = 16000   # Twilio envoie en 8kHz, on upsample
OUTPUT_SAMPLE_RATE = 24000  # Orpheus génère en 24kHz


# ============================================================
# MODÈLES DE DONNÉES
# ============================================================

@dataclass
class AudioFrame:
    """Trame audio avec métadonnées"""
    data: np.ndarray
    sample_rate: int
    timestamp: datetime
    duration_ms: float


@dataclass
class CallSession:
    """Session d'appel en cours"""
    call_id: str
    caller_phone: str
    start_time: datetime
    agent: VoiceAgentSST
    audio_buffer: list
    is_active: bool = True
    language_detected: str = "fr"


# ============================================================
# GESTIONNAIRE DE SESSION
# ============================================================

class SessionManager:
    """Gère les sessions d'appel actives"""
    
    def __init__(self):
        self.sessions: dict[str, CallSession] = {}
    
    def create_session(self, call_id: str, caller_phone: str) -> CallSession:
        """Crée une nouvelle session d'appel"""
        agent = VoiceAgentSST()
        agent.start_session(call_id, caller_phone)
        
        session = CallSession(
            call_id=call_id,
            caller_phone=caller_phone,
            start_time=datetime.now(),
            agent=agent,
            audio_buffer=[]
        )
        
        self.sessions[call_id] = session
        print(f"📞 Nouvelle session créée: {call_id} depuis {caller_phone}")
        return session
    
    def get_session(self, call_id: str) -> Optional[CallSession]:
        return self.sessions.get(call_id)
    
    def end_session(self, call_id: str) -> dict:
        """Termine une session et retourne le résumé"""
        if call_id in self.sessions:
            session = self.sessions.pop(call_id)
            session.is_active = False
            summary = session.agent.end_session(call_id)
            summary["duration_seconds"] = (datetime.now() - session.start_time).total_seconds()
            print(f"📴 Session terminée: {call_id} - Durée: {summary['duration_seconds']:.1f}s")
            return summary
        return {}


# ============================================================
# HANDLER AUDIO FASTRTC
# ============================================================

class SSTAudioHandler:
    """
    Gestionnaire audio pour l'agent SST.
    Intègre STT (faster-whisper) et TTS (Orpheus) avec LangGraph.
    """
    
    def __init__(self):
        self.session_manager = SessionManager()
        
        # Charger les modèles STT/TTS
        print("🔄 Chargement des modèles audio...")
        self.stt_model = get_stt_model(
            model_size=STT_MODEL,
            device=STT_DEVICE
        )
        print(f"✅ STT chargé: {STT_MODEL}")
        
        # Client HTTP pour TTS Orpheus
        self.tts_client = httpx.AsyncClient(base_url=TTS_ENDPOINT)
        print(f"✅ TTS configuré: {TTS_ENDPOINT}")
    
    async def process_audio_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        call_id: str,
        caller_phone: str = "unknown"
    ) -> AsyncGenerator[bytes, None]:
        """
        Traite un flux audio entrant et génère les réponses.
        
        Args:
            audio_stream: Flux audio entrant (PCM 16-bit)
            call_id: Identifiant unique de l'appel
            caller_phone: Numéro de l'appelant
        
        Yields:
            Flux audio de réponse (PCM 16-bit)
        """
        # Créer ou récupérer la session
        session = self.session_manager.get_session(call_id)
        if not session:
            session = self.session_manager.create_session(call_id, caller_phone)
        
        # Message d'accueil
        welcome_text = "Bienvenue sur la ligne SST Preventera. Comment puis-je vous aider?"
        async for audio_chunk in self._text_to_speech(welcome_text):
            yield audio_chunk
        
        # Buffer pour accumulation audio
        audio_buffer = []
        silence_threshold = 0.01
        silence_frames = 0
        max_silence_frames = 30  # ~500ms de silence = fin de phrase
        
        async for audio_chunk in audio_stream:
            if not session.is_active:
                break
            
            # Convertir bytes en numpy array
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Détecter le silence
            energy = np.sqrt(np.mean(audio_array ** 2))
            
            if energy > silence_threshold:
                audio_buffer.append(audio_array)
                silence_frames = 0
            else:
                silence_frames += 1
            
            # Si assez de silence après de l'audio = fin de phrase
            if silence_frames >= max_silence_frames and audio_buffer:
                # Concaténer l'audio
                full_audio = np.concatenate(audio_buffer)
                audio_buffer = []
                silence_frames = 0
                
                # Transcrire
                transcript = await self._speech_to_text(full_audio)
                
                if transcript and len(transcript.strip()) > 3:
                    print(f"🎤 Transcription: {transcript}")
                    
                    # Traiter avec l'agent LangGraph
                    response_text = session.agent.process_message(call_id, transcript)
                    print(f"🤖 Réponse: {response_text}")
                    
                    # Synthétiser et streamer la réponse
                    async for audio_chunk in self._text_to_speech(response_text):
                        yield audio_chunk
        
        # Fin de l'appel
        self.session_manager.end_session(call_id)
    
    async def _speech_to_text(self, audio: np.ndarray) -> str:
        """
        Convertit l'audio en texte via faster-whisper.
        """
        try:
            # Transcription avec faster-whisper
            segments, info = self.stt_model.transcribe(
                audio,
                language=STT_LANGUAGE,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Concaténer les segments
            transcript = " ".join([segment.text for segment in segments])
            
            # Détecter la langue si pas français
            if info.language != "fr" and info.language_probability > 0.8:
                # L'appelant parle anglais
                return transcript  # TODO: adapter la réponse
            
            return transcript.strip()
            
        except Exception as e:
            print(f"❌ Erreur STT: {e}")
            return ""
    
    async def _text_to_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convertit le texte en audio via Orpheus 3B.
        Stream le résultat pour une latence minimale.
        """
        try:
            # Requête à l'API Orpheus (llama.cpp server)
            async with self.tts_client.stream(
                "POST",
                "/tts",
                json={
                    "text": text,
                    "voice": TTS_VOICE,
                    "language": "fr",
                    "sample_rate": OUTPUT_SAMPLE_RATE,
                    "stream": True
                }
            ) as response:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
                        
        except Exception as e:
            print(f"❌ Erreur TTS: {e}")
            # Fallback: utiliser le TTS local de FastRTC
            local_tts = get_tts_model()
            audio = local_tts.synthesize(text)
            yield audio.tobytes()


# ============================================================
# APPLICATION FASTAPI
# ============================================================

app = FastAPI(
    title="EDGY Voice Agent SST",
    description="Agent vocal intelligent pour la Santé et Sécurité au Travail",
    version="1.0.0"
)

# Instance du handler
audio_handler = SSTAudioHandler()


@app.get("/")
async def root():
    """Page d'accueil"""
    return HTMLResponse("""
    <html>
        <head>
            <title>EDGY Voice Agent SST</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #2563eb; }
                .status { padding: 10px; background: #d1fae5; border-radius: 5px; }
                .endpoint { background: #f3f4f6; padding: 15px; margin: 10px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>🎙️ EDGY Voice Agent SST</h1>
            <div class="status">✅ Service actif</div>
            
            <h2>Points d'entrée</h2>
            <div class="endpoint">
                <strong>WebSocket Gradio:</strong> ws://localhost:8000/ws/gradio
            </div>
            <div class="endpoint">
                <strong>WebSocket Twilio:</strong> ws://localhost:8000/ws/twilio
            </div>
            <div class="endpoint">
                <strong>Health Check:</strong> GET /health
            </div>
            
            <h2>Documentation</h2>
            <p><a href="/docs">Swagger UI</a> | <a href="/redoc">ReDoc</a></p>
        </body>
    </html>
    """)


@app.get("/health")
async def health_check():
    """Vérification de l'état du service"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(audio_handler.session_manager.sessions),
        "stt_model": STT_MODEL,
        "tts_endpoint": TTS_ENDPOINT
    }


@app.websocket("/ws/gradio")
async def gradio_websocket(websocket: WebSocket):
    """
    WebSocket pour l'interface Gradio (test local).
    """
    await websocket.accept()
    call_id = f"GRADIO-{uuid.uuid4().hex[:8]}"
    
    print(f"🌐 Connexion Gradio: {call_id}")
    
    try:
        async def audio_generator():
            while True:
                data = await websocket.receive_bytes()
                yield data
        
        async for response_audio in audio_handler.process_audio_stream(
            audio_generator(),
            call_id=call_id,
            caller_phone="gradio-test"
        ):
            await websocket.send_bytes(response_audio)
            
    except Exception as e:
        print(f"❌ Erreur WebSocket Gradio: {e}")
    finally:
        audio_handler.session_manager.end_session(call_id)
        await websocket.close()


@app.websocket("/ws/twilio")
async def twilio_websocket(websocket: WebSocket):
    """
    WebSocket pour les appels Twilio.
    Gère le protocole Twilio Media Streams.
    """
    await websocket.accept()
    call_id = None
    caller_phone = None
    
    try:
        async def audio_generator():
            nonlocal call_id, caller_phone
            
            while True:
                message = await websocket.receive_json()
                event = message.get("event")
                
                if event == "start":
                    # Début de l'appel
                    start_data = message.get("start", {})
                    call_id = start_data.get("callSid", f"TWILIO-{uuid.uuid4().hex[:8]}")
                    caller_phone = start_data.get("from", "unknown")
                    print(f"📞 Appel Twilio: {call_id} depuis {caller_phone}")
                    
                elif event == "media":
                    # Données audio (mulaw 8kHz -> PCM 16kHz)
                    payload = message.get("media", {}).get("payload", "")
                    if payload:
                        import base64
                        audio_bytes = base64.b64decode(payload)
                        # Convertir mulaw -> PCM (simplifié)
                        yield audio_bytes
                        
                elif event == "stop":
                    # Fin de l'appel
                    print(f"📴 Fin appel Twilio: {call_id}")
                    break
        
        async for response_audio in audio_handler.process_audio_stream(
            audio_generator(),
            call_id=call_id or f"TWILIO-{uuid.uuid4().hex[:8]}",
            caller_phone=caller_phone or "unknown"
        ):
            # Encoder en mulaw pour Twilio
            import base64
            encoded = base64.b64encode(response_audio).decode()
            
            await websocket.send_json({
                "event": "media",
                "streamSid": call_id,
                "media": {
                    "payload": encoded
                }
            })
            
    except Exception as e:
        print(f"❌ Erreur WebSocket Twilio: {e}")
    finally:
        if call_id:
            audio_handler.session_manager.end_session(call_id)


@app.post("/twilio/voice")
async def twilio_voice_webhook(request: Request):
    """
    Webhook Twilio pour les appels entrants.
    Retourne TwiML pour connecter au WebSocket.
    """
    from twilio.twiml.voice_response import VoiceResponse, Connect
    
    response = VoiceResponse()
    
    # Connecter au WebSocket
    connect = Connect()
    stream_url = os.getenv("STREAM_URL", "wss://your-domain.com/ws/twilio")
    connect.stream(url=stream_url)
    response.append(connect)
    
    return HTMLResponse(
        content=str(response),
        media_type="application/xml"
    )


@app.post("/twilio/outbound")
async def make_outbound_call(
    to_number: str,
    message: str = "Bonjour, ceci est un appel de suivi de Preventera SST."
):
    """
    Initie un appel sortant (suivi automatique).
    """
    from twilio.rest import Client
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    call = client.calls.create(
        to=to_number,
        from_=TWILIO_PHONE_NUMBER,
        url=f"{os.getenv('BASE_URL')}/twilio/outbound-twiml?message={message}"
    )
    
    return {
        "call_sid": call.sid,
        "status": call.status,
        "to": to_number
    }


# ============================================================
# INTERFACE GRADIO (LOCAL)
# ============================================================

def create_gradio_interface():
    """
    Crée une interface Gradio pour tester l'agent localement.
    """
    import gradio as gr
    
    def process_audio(audio):
        """Traite l'audio uploadé"""
        if audio is None:
            return None, "Veuillez enregistrer un message"
        
        sample_rate, audio_data = audio
        
        # TODO: Intégrer avec le handler
        # Pour l'instant, retourner un placeholder
        return None, "Traitement audio en cours..."
    
    interface = gr.Interface(
        fn=process_audio,
        inputs=gr.Audio(sources=["microphone"], type="numpy"),
        outputs=[
            gr.Audio(label="Réponse"),
            gr.Textbox(label="Transcription")
        ],
        title="🎙️ EDGY Voice Agent SST - Test Local",
        description="Testez l'agent vocal SST localement. Parlez dans votre micro.",
        theme=gr.themes.Soft()
    )
    
    return interface


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="EDGY Voice Agent SST Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--gradio", action="store_true", help="Launch Gradio interface")
    args = parser.parse_args()
    
    if args.gradio:
        # Lancer l'interface Gradio
        interface = create_gradio_interface()
        interface.launch(server_name=args.host, server_port=args.port + 1)
    else:
        # Lancer le serveur FastAPI
        print(f"""
        ╔══════════════════════════════════════════════════════════════╗
        ║         🎙️ EDGY VOICE AGENT SST - PREVENTERA                 ║
        ╠══════════════════════════════════════════════════════════════╣
        ║  Server: http://{args.host}:{args.port}                      ║
        ║  Docs:   http://{args.host}:{args.port}/docs                 ║
        ║  WebSocket Gradio: ws://{args.host}:{args.port}/ws/gradio    ║
        ║  WebSocket Twilio: ws://{args.host}:{args.port}/ws/twilio    ║
        ╚══════════════════════════════════════════════════════════════╝
        """)
        uvicorn.run(app, host=args.host, port=args.port)
