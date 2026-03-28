"""
VOICEX5-GEMINI-LIVE — Service WebSocket bidirectionnel Gemini Live API
======================================================================
Pont entre le frontend audio et Gemini Live API.
Gere la session, le relay audio PCM16, la reception des reponses
(audio, tool calls, transcripts) et les reponses aux function calls.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from voice.voice_config import (
    AUDIO_INPUT_SAMPLE_RATE,
    GEMINI_API_KEY,
    GEMINI_GENERATION_CONFIG,
    GEMINI_MODEL,
    GEMINI_REALTIME_INPUT_CONFIG,
    GEMINI_TOOLS,
    GEMINI_WS_URI,
    SYSTEM_PROMPT,
)

logger = logging.getLogger("voicex5.gemini_live")

# ============================================================
# Types de messages reçus de Gemini
# ============================================================

class GeminiMessageType(str, Enum):
    AUDIO = "audio"
    TOOL_CALL = "tool_call"
    TRANSCRIPT = "transcript"
    TURN_COMPLETE = "turn_complete"
    SETUP_COMPLETE = "setup_complete"
    ERROR = "error"


@dataclass
class GeminiMessage:
    """Message type recu de Gemini Live API."""
    type: GeminiMessageType
    data: Any = None
    tool_call_id: Optional[str] = None
    function_name: Optional[str] = None
    function_args: Optional[dict] = None


# ============================================================
# Configuration reconnexion
# ============================================================

MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_BASE_DELAY_S = 1.0  # backoff exponentiel : 1s, 2s, 4s
WS_CLOSE_TIMEOUT_S = 5.0
RECEIVE_TIMEOUT_S = 300.0  # 5 min max silence avant timeout


# ============================================================
# GeminiLiveService
# ============================================================

class GeminiLiveService:
    """Pont WebSocket bidirectionnel entre le frontend et Gemini Live API.

    Usage:
        service = GeminiLiveService()
        session_id = await service.create_session()

        # Envoyer audio du micro
        await service.relay_audio_to_gemini(pcm16_chunk)

        # Recevoir reponses
        async for msg in service.receive_from_gemini():
            if msg.type == GeminiMessageType.AUDIO:
                send_to_frontend(msg.data)
            elif msg.type == GeminiMessageType.TOOL_CALL:
                result = handle_tool(msg.function_name, msg.function_args)
                await service.send_tool_result(msg.tool_call_id, result)

        await service.close_session()
    """

    KEEPALIVE_INTERVAL_S = 15.0  # Ping toutes les 15s pour eviter timeout Gemini

    def __init__(self) -> None:
        self._ws: Optional[ClientConnection] = None
        self._session_id: Optional[str] = None
        self._connected: bool = False
        self._system_prompt: str = SYSTEM_PROMPT
        self._tools: list[dict] = GEMINI_TOOLS
        self._reconnect_attempts: int = 0
        self._keepalive_task: Optional[asyncio.Task] = None

    # ----------------------------------------------------------
    # Proprietes
    # ----------------------------------------------------------

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    # ----------------------------------------------------------
    # 1. create_session
    # ----------------------------------------------------------

    async def create_session(
        self,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict]] = None,
    ) -> str:
        """Ouvre le WebSocket vers Gemini Live et envoie le setup message.

        Args:
            system_prompt: Prompt systeme (defaut: SYSTEM_PROMPT de voice_config).
            tools: Schemas function calling (defaut: GEMINI_TOOLS de voice_config).

        Returns:
            session_id (UUID str).

        Raises:
            ConnectionError: Si la connexion echoue apres retries.
        """
        if system_prompt is not None:
            self._system_prompt = system_prompt
        if tools is not None:
            self._tools = tools

        self._session_id = str(uuid.uuid4())
        await self._connect_with_retry()

        logger.info("Session %s creee — modele=%s", self._session_id, GEMINI_MODEL)
        return self._session_id

    async def _connect_with_retry(self) -> None:
        """Connexion WebSocket avec backoff exponentiel."""
        if not GEMINI_API_KEY:
            raise ConnectionError(
                "GEMINI_API_KEY manquante. Ajoutez-la dans .env."
            )

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            try:
                logger.debug(
                    "Tentative connexion %d/%d vers Gemini Live",
                    attempt + 1,
                    MAX_RECONNECT_ATTEMPTS,
                )
                self._ws = await websockets.connect(
                    GEMINI_WS_URI,
                    max_size=10 * 1024 * 1024,  # 10 MB max message
                )
                await self._send_setup_message()
                self._connected = True
                self._reconnect_attempts = 0
                self._start_keepalive()
                logger.info("Connexion Gemini Live etablie (tentative %d)", attempt + 1)
                return
            except (
                websockets.exceptions.WebSocketException,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                last_error = exc
                delay = RECONNECT_BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "Echec connexion (tentative %d/%d): %s — retry dans %.1fs",
                    attempt + 1,
                    MAX_RECONNECT_ATTEMPTS,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        self._connected = False
        raise ConnectionError(
            f"Impossible de se connecter a Gemini Live apres "
            f"{MAX_RECONNECT_ATTEMPTS} tentatives: {last_error}"
        )

    async def _send_setup_message(self) -> None:
        """Envoie le message de setup initial a Gemini."""
        setup_msg = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generation_config": GEMINI_GENERATION_CONFIG,
                "system_instruction": {
                    "parts": [{"text": self._system_prompt}],
                },
                "tools": self._tools,
                "realtimeInputConfig": GEMINI_REALTIME_INPUT_CONFIG,
            }
        }
        await self._send_json(setup_msg)
        logger.debug("Setup message envoye — attente setup_complete")

        # Attendre la confirmation setup_complete de Gemini
        raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
        response = json.loads(raw)

        if "setupComplete" in response:
            logger.debug("Setup complete recu de Gemini")
        else:
            logger.warning("Reponse setup inattendue: %s", response)

    # ----------------------------------------------------------
    # 2. relay_audio_to_gemini
    # ----------------------------------------------------------

    async def relay_audio_to_gemini(self, audio_chunk: bytes) -> None:
        """Envoie un chunk audio PCM16 du frontend vers Gemini.

        Args:
            audio_chunk: Bytes bruts PCM16 mono 16kHz.

        Raises:
            ConnectionError: Si le WebSocket n'est pas connecte.
        """
        if not self.is_connected:
            raise ConnectionError("WebSocket non connecte — appelez create_session() d'abord")

        audio_b64 = base64.b64encode(audio_chunk).decode("ascii")
        msg = {
            "realtime_input": {
                "audio": {
                    "data": audio_b64,
                    "mime_type": f"audio/pcm;rate={AUDIO_INPUT_SAMPLE_RATE}",
                }
            }
        }
        await self._send_json(msg)
        logger.debug("Audio chunk envoye — %d bytes", len(audio_chunk))

    # ----------------------------------------------------------
    # 3. receive_from_gemini — async generator
    # ----------------------------------------------------------

    async def receive_from_gemini(self) -> AsyncGenerator[GeminiMessage, None]:
        """Ecoute les messages Gemini en continu et yield des GeminiMessage types.

        Yields:
            GeminiMessage avec type parmi: audio, tool_call, transcript,
            turn_complete, setup_complete, error.
        """
        if not self.is_connected:
            raise ConnectionError("WebSocket non connecte")

        while self._connected:
            try:
                raw = await asyncio.wait_for(
                    self._ws.recv(), timeout=RECEIVE_TIMEOUT_S
                )
                response = json.loads(raw)

                for msg in self._parse_gemini_response(response):
                    yield msg

            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout reception Gemini (%.0fs) — session %s",
                    RECEIVE_TIMEOUT_S,
                    self._session_id,
                )
                yield GeminiMessage(
                    type=GeminiMessageType.ERROR,
                    data="receive_timeout",
                )
                break

            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning("Connexion Gemini fermee: %s", exc)
                self._connected = False
                yield GeminiMessage(
                    type=GeminiMessageType.ERROR,
                    data=f"connection_closed: {exc.code}",
                )
                break

            except json.JSONDecodeError as exc:
                logger.error("JSON invalide de Gemini: %s", exc)
                continue

    def _parse_gemini_response(self, response: dict) -> list[GeminiMessage]:
        """Parse une reponse JSON Gemini en messages types."""
        messages: list[GeminiMessage] = []

        # --- Setup complete ---
        if "setupComplete" in response:
            messages.append(GeminiMessage(type=GeminiMessageType.SETUP_COMPLETE))
            return messages

        # --- Server content (audio, text, turn_complete) ---
        server_content = response.get("serverContent")
        if server_content:
            # Turn complete?
            if server_content.get("turnComplete"):
                messages.append(
                    GeminiMessage(type=GeminiMessageType.TURN_COMPLETE)
                )

            # Parts (audio inline ou texte)
            model_turn = server_content.get("modelTurn", {})
            for part in model_turn.get("parts", []):
                # Audio inline
                inline_data = part.get("inlineData")
                if inline_data:
                    audio_bytes = base64.b64decode(inline_data["data"])
                    messages.append(
                        GeminiMessage(
                            type=GeminiMessageType.AUDIO,
                            data=audio_bytes,
                        )
                    )

                # Texte (transcript side-channel)
                if "text" in part:
                    messages.append(
                        GeminiMessage(
                            type=GeminiMessageType.TRANSCRIPT,
                            data=part["text"],
                        )
                    )

        # --- Tool calls ---
        tool_call = response.get("toolCall")
        if tool_call:
            for fc in tool_call.get("functionCalls", []):
                messages.append(
                    GeminiMessage(
                        type=GeminiMessageType.TOOL_CALL,
                        tool_call_id=fc.get("id", str(uuid.uuid4())),
                        function_name=fc["name"],
                        function_args=fc.get("args", {}),
                    )
                )

        return messages

    # ----------------------------------------------------------
    # 4. send_tool_result
    # ----------------------------------------------------------

    async def send_tool_result(
        self, tool_call_id: str, result: dict
    ) -> None:
        """Envoie le resultat d'un function call a Gemini.

        Args:
            tool_call_id: ID du function call recu dans le GeminiMessage.
            result: Dictionnaire resultat a renvoyer a Gemini.

        Raises:
            ConnectionError: Si le WebSocket n'est pas connecte.
        """
        if not self.is_connected:
            raise ConnectionError("WebSocket non connecte")

        msg = {
            "tool_response": {
                "function_responses": [
                    {
                        "id": tool_call_id,
                        "response": result,
                    }
                ]
            }
        }
        await self._send_json(msg)
        logger.debug(
            "Tool result envoye — call_id=%s",
            tool_call_id,
        )

    # ----------------------------------------------------------
    # 4b. Keepalive
    # ----------------------------------------------------------

    def _start_keepalive(self) -> None:
        """Demarre la boucle keepalive en background."""
        self._stop_keepalive()
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    def _stop_keepalive(self) -> None:
        """Arrete la boucle keepalive."""
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None

    async def _keepalive_loop(self) -> None:
        """Envoie un micro audio chunk silence toutes les 15s."""
        # 160 samples de silence @ 16kHz = 10ms — assez petit pour ne pas interferer
        silence = base64.b64encode(b"\x00" * 320).decode("ascii")
        while self._connected:
            try:
                await asyncio.sleep(self.KEEPALIVE_INTERVAL_S)
                if not self.is_connected:
                    break
                msg = {
                    "realtime_input": {
                        "audio": {
                            "data": silence,
                            "mime_type": f"audio/pcm;rate={AUDIO_INPUT_SAMPLE_RATE}",
                        }
                    }
                }
                await self._send_json(msg)
                logger.debug("Keepalive envoye — session %s", self._session_id)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Keepalive erreur: %s", exc)
                break

    # ----------------------------------------------------------
    # 5. close_session
    # ----------------------------------------------------------

    async def close_session(self) -> None:
        """Ferme proprement le WebSocket Gemini."""
        self._connected = False
        self._stop_keepalive()
        if self._ws is not None:
            try:
                await asyncio.wait_for(
                    self._ws.close(), timeout=WS_CLOSE_TIMEOUT_S
                )
                logger.info("Session %s fermee proprement", self._session_id)
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning(
                    "Fermeture forcee session %s: %s", self._session_id, exc
                )
            finally:
                self._ws = None

    # ----------------------------------------------------------
    # Helpers internes
    # ----------------------------------------------------------

    async def _send_json(self, payload: dict) -> None:
        """Envoie un message JSON sur le WebSocket."""
        raw = json.dumps(payload)
        await self._ws.send(raw)
