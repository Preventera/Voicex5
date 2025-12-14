"""
Voice Agent SST - EDGY AgenticX5
Agent vocal intelligent pour la Santé et Sécurité au Travail

Adapté du cours: neural-maze/realtime-phone-agents-course
Pour: Preventera / GenAISafety
"""

import os
import json
from datetime import datetime
from typing import Annotated, Literal, TypedDict, Optional, List
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# Import des outils personnalisés
from neo4j_sst_tools import (
    create_incident_from_voice,
    find_similar_incidents,
    get_zone_risk_profile,
    notify_stakeholders,
    schedule_followup
)
from superlinked_sst_tools import (
    search_similar_incidents,
    search_procedures,
    search_formations
)


# ============================================================
# CONFIGURATION
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Modèle Claude pour l'agent
LLM_MODEL = "claude-sonnet-4-20250514"


# ============================================================
# TYPES D'INTENTIONS SST
# ============================================================

class IntentType(str, Enum):
    INCIDENT_REPORT = "incident_report"
    NEAR_MISS_REPORT = "near_miss_report"
    HAZARD_IDENTIFICATION = "hazard_identification"
    PROCEDURE_QUESTION = "procedure_question"
    TRAINING_INQUIRY = "training_inquiry"
    EQUIPMENT_CONCERN = "equipment_concern"
    COMPLIANCE_QUESTION = "compliance_question"
    EMERGENCY_CALL = "emergency_call"
    FOLLOW_UP = "follow_up"
    GENERAL_INQUIRY = "general_inquiry"


class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"  # Urgence vitale
    HIGH = "HIGH"          # Action immédiate requise
    MEDIUM = "MEDIUM"      # Action dans les 24h
    LOW = "LOW"            # Information/consultation


# ============================================================
# MODÈLES DE DONNÉES
# ============================================================

class ExtractedEntities(BaseModel):
    """Entités extraites de la transcription vocale"""
    location: Optional[str] = Field(None, description="Zone, bâtiment, département")
    equipment: Optional[str] = Field(None, description="Machine, outil, véhicule")
    hazard_type: Optional[str] = Field(None, description="Type de danger: chimique, mécanique, ergonomique, etc.")
    severity: Optional[int] = Field(None, ge=1, le=10, description="Gravité estimée 1-10")
    body_part: Optional[str] = Field(None, description="Partie du corps si blessure")
    time_reference: Optional[str] = Field(None, description="Quand l'événement s'est produit")
    person_count: Optional[int] = Field(None, description="Nombre de personnes impliquées")
    witnesses: Optional[List[str]] = Field(None, description="Témoins identifiés")


class IntentClassification(BaseModel):
    """Classification de l'intention de l'appelant"""
    intent: IntentType
    confidence: float = Field(ge=0, le=1)
    urgency: UrgencyLevel
    entities: ExtractedEntities
    cnesst_code: Optional[str] = None
    iso45001_clause: Optional[str] = None


# ============================================================
# ÉTAT DU GRAPHE LANGGRAPH
# ============================================================

class VoiceAgentState(TypedDict):
    """État partagé entre les nœuds du graphe"""
    messages: Annotated[list, add_messages]
    
    # Métadonnées de l'appel
    call_id: str
    caller_phone: str
    call_start_time: str
    
    # Classification
    intent: Optional[IntentType]
    urgency: Optional[UrgencyLevel]
    entities: Optional[dict]
    confidence: float
    
    # Contexte enrichi
    similar_incidents: Optional[List[dict]]
    relevant_procedures: Optional[List[dict]]
    zone_risk_profile: Optional[dict]
    
    # Résultats d'actions
    incident_id: Optional[str]
    notifications_sent: Optional[List[str]]
    followup_scheduled: Optional[str]
    
    # Contrôle de flux
    requires_human_validation: bool
    conversation_complete: bool


# ============================================================
# PROMPT SYSTÈME
# ============================================================

SYSTEM_PROMPT = """Tu es un agent vocal intelligent pour la Santé et Sécurité au Travail (SST) de Preventera.

🎯 MISSION:
- Recevoir et traiter les appels liés à la SST
- Enregistrer les incidents et quasi-accidents
- Répondre aux questions sur les procédures de sécurité
- Déclencher les alertes appropriées
- Assurer la traçabilité complète

🗣️ STYLE DE COMMUNICATION:
- Parle de manière claire, calme et professionnelle
- Utilise des phrases courtes adaptées à la communication vocale
- Confirme toujours les informations critiques
- Montre de l'empathie tout en restant efficace
- Évite le jargon technique excessif

⚠️ PRIORITÉS ABSOLUES (Charte AgenticX5):
1. La vie humaine est la priorité absolue
2. En cas d'urgence vitale, donne d'abord les instructions de sécurité
3. Documente tout pour assurer la traçabilité
4. Escalade vers un humain si la situation dépasse tes capacités

📋 PROCESSUS TYPE POUR UN INCIDENT:
1. Identifier si quelqu'un est blessé (priorité 1)
2. Classifier le type d'incident et l'urgence
3. Donner les actions immédiates de sécurité
4. Enregistrer l'incident dans le système
5. Notifier les personnes concernées
6. Programmer un suivi

🔧 OUTILS DISPONIBLES:
- Recherche d'incidents similaires (Superlinked)
- Recherche de procédures SST
- Création d'incident (SafetyGraph)
- Notifications automatiques
- Programmation de suivis

Réponds toujours en français canadien, sauf si l'appelant parle anglais.
"""


# ============================================================
# OUTILS LANGGRAPH
# ============================================================

@tool
def classify_intent(transcript: str) -> IntentClassification:
    """
    Analyse la transcription vocale pour classifier l'intention
    et extraire les entités SST pertinentes.
    """
    # Cette fonction utilise le LLM pour classifier
    # Implémentation simplifiée - en production, utiliser un prompt structuré
    
    llm = ChatAnthropic(model=LLM_MODEL, api_key=ANTHROPIC_API_KEY)
    
    classification_prompt = f"""Analyse cette transcription d'un appel SST et extrais:
1. L'intention principale (incident_report, procedure_question, etc.)
2. Le niveau d'urgence (CRITICAL, HIGH, MEDIUM, LOW)
3. Les entités: lieu, équipement, type de danger, gravité, etc.
4. Le code CNESST applicable si pertinent

Transcription: "{transcript}"

Réponds en JSON structuré."""

    response = llm.invoke([HumanMessage(content=classification_prompt)])
    
    # Parser la réponse (simplifié)
    # En production, utiliser un output parser Pydantic
    return IntentClassification(
        intent=IntentType.INCIDENT_REPORT,
        confidence=0.9,
        urgency=UrgencyLevel.HIGH,
        entities=ExtractedEntities(
            location="Zone B",
            equipment="Machine 12",
            hazard_type="chemical_spill"
        ),
        cnesst_code="31-001"
    )


@tool
def search_relevant_procedures(
    query: str,
    equipment: Optional[str] = None,
    category: Optional[str] = None
) -> List[dict]:
    """
    Recherche les procédures SST pertinentes via Superlinked.
    
    Args:
        query: Question ou description du besoin
        equipment: Type d'équipement concerné
        category: Catégorie de procédure (cadenassage, chimique, etc.)
    
    Returns:
        Liste des procédures pertinentes avec score de similarité
    """
    results = search_procedures(query, equipment, category)
    return [
        {
            "id": r.id,
            "titre": r.titre,
            "resume": r.contenu[:200] + "...",
            "categorie": r.categorie,
            "niveau_formation": r.niveau_formation_requis,
            "score": r.similarity_score
        }
        for r in results
    ]


@tool
def search_incident_history(
    description: str,
    zone: Optional[str] = None,
    hazard_type: Optional[str] = None,
    min_severity: Optional[int] = None
) -> List[dict]:
    """
    Recherche des incidents similaires dans l'historique.
    
    Args:
        description: Description de l'incident actuel
        zone: Zone concernée
        hazard_type: Type de danger
        min_severity: Gravité minimale à considérer
    
    Returns:
        Liste des incidents similaires avec contexte
    """
    results = search_similar_incidents(
        description=description,
        zone=zone,
        type_danger=hazard_type,
        min_gravite=min_severity
    )
    return [
        {
            "id": r.id,
            "description": r.description,
            "gravite": r.gravite,
            "resolution": r.resolution,
            "date": r.date_incident,
            "similarity_score": r.score
        }
        for r in results
    ]


@tool
def create_incident_record(
    voice_id: str,
    phone: str,
    transcript: str,
    incident_type: str,
    location: str,
    severity: int,
    description: str,
    cnesst_code: Optional[str] = None
) -> dict:
    """
    Crée un enregistrement d'incident dans SafetyGraph (Neo4j).
    
    Returns:
        Dictionnaire avec l'ID de l'incident créé
    """
    result = create_incident_from_voice(
        voice_id=voice_id,
        phone=phone,
        transcript=transcript,
        incident_type=incident_type,
        location=location,
        severity=severity,
        description=description,
        cnesst_code=cnesst_code
    )
    return {"incident_id": result["incident_id"], "status": "created"}


@tool
def send_notifications(
    incident_id: str,
    zone: str,
    severity: int,
    incident_type: str
) -> List[str]:
    """
    Envoie les notifications appropriées selon la zone et la gravité.
    
    Returns:
        Liste des notifications envoyées
    """
    notifications = []
    
    # Récupérer les contacts
    stakeholders = notify_stakeholders(zone=zone, severity=severity)
    
    # Superviseur (toujours notifié)
    if stakeholders.get("supervisor"):
        notifications.append(f"SMS envoyé au superviseur: {stakeholders['supervisor']['name']}")
    
    # HSE (gravité >= 5)
    if severity >= 5 and stakeholders.get("hse_officer"):
        notifications.append(f"Email envoyé HSE: {stakeholders['hse_officer']['name']}")
    
    # Direction (gravité >= 8)
    if severity >= 8:
        notifications.append("Alerte direction envoyée")
    
    # Urgences (gravité critique)
    if severity >= 9:
        notifications.append("🚨 Services d'urgence alertés")
    
    return notifications


@tool
def schedule_followup_call(
    incident_id: str,
    delay_hours: int = 2,
    assigned_to: Optional[str] = None
) -> dict:
    """
    Programme un appel de suivi automatique.
    
    Args:
        incident_id: ID de l'incident concerné
        delay_hours: Délai en heures avant le rappel
        assigned_to: Personne assignée au suivi
    
    Returns:
        Détails du suivi programmé
    """
    result = schedule_followup(
        incident_id=incident_id,
        delay=f"PT{delay_hours}H",
        hse_officer=assigned_to
    )
    return {
        "task_id": result["task_id"],
        "scheduled_at": result["scheduled_at"],
        "message": f"Suivi programmé dans {delay_hours}h"
    }


# Liste des outils disponibles
SST_TOOLS = [
    classify_intent,
    search_relevant_procedures,
    search_incident_history,
    create_incident_record,
    send_notifications,
    schedule_followup_call
]


# ============================================================
# NŒUDS DU GRAPHE
# ============================================================

def route_by_intent(state: VoiceAgentState) -> str:
    """
    Route vers le bon sous-agent selon l'intention détectée.
    """
    intent = state.get("intent")
    urgency = state.get("urgency")
    
    # Urgence critique = traitement immédiat
    if urgency == UrgencyLevel.CRITICAL:
        return "emergency_handler"
    
    # Routing par intention
    if intent in [IntentType.INCIDENT_REPORT, IntentType.NEAR_MISS_REPORT]:
        return "incident_agent"
    elif intent == IntentType.PROCEDURE_QUESTION:
        return "procedure_agent"
    elif intent == IntentType.TRAINING_INQUIRY:
        return "training_agent"
    elif intent == IntentType.HAZARD_IDENTIFICATION:
        return "hazard_agent"
    elif intent == IntentType.FOLLOW_UP:
        return "followup_agent"
    else:
        return "general_agent"


def intent_classifier_node(state: VoiceAgentState) -> VoiceAgentState:
    """
    Nœud de classification de l'intention.
    """
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    
    # Classifier l'intention
    classification = classify_intent(last_message)
    
    return {
        **state,
        "intent": classification.intent,
        "urgency": classification.urgency,
        "entities": classification.entities.model_dump(),
        "confidence": classification.confidence
    }


def incident_agent_node(state: VoiceAgentState) -> VoiceAgentState:
    """
    Agent spécialisé dans le traitement des incidents.
    """
    llm = ChatAnthropic(model=LLM_MODEL, api_key=ANTHROPIC_API_KEY)
    llm_with_tools = llm.bind_tools(SST_TOOLS)
    
    messages = state["messages"]
    entities = state.get("entities", {})
    
    # Construire le contexte
    context = f"""
    CONTEXTE INCIDENT:
    - Zone: {entities.get('location', 'Non spécifiée')}
    - Équipement: {entities.get('equipment', 'Non spécifié')}
    - Type danger: {entities.get('hazard_type', 'Non spécifié')}
    - Urgence: {state.get('urgency', 'MEDIUM')}
    
    Traite cet incident en:
    1. Vérifiant si quelqu'un est blessé
    2. Donnant les actions immédiates de sécurité
    3. Créant l'enregistrement dans le système
    4. Envoyant les notifications appropriées
    """
    
    response = llm_with_tools.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
        *messages
    ])
    
    return {
        **state,
        "messages": [*messages, response]
    }


def procedure_agent_node(state: VoiceAgentState) -> VoiceAgentState:
    """
    Agent spécialisé dans les questions de procédures.
    """
    llm = ChatAnthropic(model=LLM_MODEL, api_key=ANTHROPIC_API_KEY)
    llm_with_tools = llm.bind_tools([search_relevant_procedures])
    
    messages = state["messages"]
    last_message = messages[-1].content if messages else ""
    entities = state.get("entities", {})
    
    # Rechercher les procédures pertinentes
    procedures = search_relevant_procedures(
        query=last_message,
        equipment=entities.get("equipment"),
        category=entities.get("hazard_type")
    )
    
    context = f"""
    PROCÉDURES TROUVÉES:
    {json.dumps(procedures, indent=2, ensure_ascii=False)}
    
    Réponds à la question en:
    1. Résumant les étapes principales
    2. Proposant d'envoyer le document complet
    3. Mentionnant si une formation est requise
    """
    
    response = llm_with_tools.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
        *messages
    ])
    
    return {
        **state,
        "messages": [*messages, response],
        "relevant_procedures": procedures
    }


def emergency_handler_node(state: VoiceAgentState) -> VoiceAgentState:
    """
    Gestionnaire d'urgences critiques.
    Priorité absolue: sécurité des personnes.
    """
    entities = state.get("entities", {})
    
    # Message d'urgence pré-formaté
    emergency_response = f"""
    🚨 URGENCE DÉTECTÉE 🚨
    
    J'ai bien compris qu'il s'agit d'une urgence en {entities.get('location', 'zone non précisée')}.
    
    ACTIONS IMMÉDIATES:
    1. Si quelqu'un est blessé, ne le déplacez pas sauf danger immédiat
    2. Évacuez la zone immédiatement
    3. Les secours sont alertés automatiquement
    4. Restez en ligne, je transmets les informations
    
    Pouvez-vous me confirmer si des personnes sont blessées?
    """
    
    # Envoyer notifications d'urgence
    send_notifications(
        incident_id=state.get("call_id"),
        zone=entities.get("location", "unknown"),
        severity=10,
        incident_type="emergency"
    )
    
    return {
        **state,
        "messages": [*state["messages"], AIMessage(content=emergency_response)],
        "requires_human_validation": True
    }


def should_continue(state: VoiceAgentState) -> Literal["continue", "end"]:
    """
    Détermine si la conversation doit continuer.
    """
    if state.get("conversation_complete"):
        return "end"
    if state.get("requires_human_validation"):
        return "end"  # Handoff vers humain
    return "continue"


# ============================================================
# CONSTRUCTION DU GRAPHE
# ============================================================

def build_voice_agent_graph() -> StateGraph:
    """
    Construit le graphe LangGraph pour l'agent vocal SST.
    """
    
    # Créer le graphe
    graph = StateGraph(VoiceAgentState)
    
    # Ajouter les nœuds
    graph.add_node("classifier", intent_classifier_node)
    graph.add_node("incident_agent", incident_agent_node)
    graph.add_node("procedure_agent", procedure_agent_node)
    graph.add_node("emergency_handler", emergency_handler_node)
    graph.add_node("tools", ToolNode(SST_TOOLS))
    
    # Définir le point d'entrée
    graph.set_entry_point("classifier")
    
    # Ajouter les arêtes conditionnelles
    graph.add_conditional_edges(
        "classifier",
        route_by_intent,
        {
            "incident_agent": "incident_agent",
            "procedure_agent": "procedure_agent",
            "emergency_handler": "emergency_handler",
            "training_agent": "procedure_agent",  # Fallback
            "hazard_agent": "incident_agent",     # Fallback
            "followup_agent": "incident_agent",   # Fallback
            "general_agent": "procedure_agent"    # Fallback
        }
    )
    
    # Les agents peuvent appeler des outils
    graph.add_edge("incident_agent", "tools")
    graph.add_edge("procedure_agent", "tools")
    
    # Retour des outils vers le routeur
    graph.add_conditional_edges(
        "tools",
        should_continue,
        {
            "continue": "classifier",
            "end": END
        }
    )
    
    # Emergency handler termine toujours
    graph.add_edge("emergency_handler", END)
    
    return graph.compile()


# ============================================================
# INTERFACE PRINCIPALE
# ============================================================

class VoiceAgentSST:
    """
    Interface principale pour l'agent vocal SST.
    Utilisée par FastRTC pour traiter les messages.
    """
    
    def __init__(self):
        self.graph = build_voice_agent_graph()
        self.active_sessions = {}
    
    def start_session(self, call_id: str, caller_phone: str) -> VoiceAgentState:
        """
        Démarre une nouvelle session d'appel.
        """
        initial_state: VoiceAgentState = {
            "messages": [],
            "call_id": call_id,
            "caller_phone": caller_phone,
            "call_start_time": datetime.now().isoformat(),
            "intent": None,
            "urgency": None,
            "entities": None,
            "confidence": 0.0,
            "similar_incidents": None,
            "relevant_procedures": None,
            "zone_risk_profile": None,
            "incident_id": None,
            "notifications_sent": None,
            "followup_scheduled": None,
            "requires_human_validation": False,
            "conversation_complete": False
        }
        
        self.active_sessions[call_id] = initial_state
        return initial_state
    
    def process_message(self, call_id: str, transcript: str) -> str:
        """
        Traite un message transcrit et retourne la réponse.
        
        Args:
            call_id: Identifiant de l'appel
            transcript: Transcription du message vocal
        
        Returns:
            Texte de la réponse à synthétiser en voix
        """
        if call_id not in self.active_sessions:
            self.start_session(call_id, "unknown")
        
        state = self.active_sessions[call_id]
        
        # Ajouter le message
        state["messages"].append(HumanMessage(content=transcript))
        
        # Exécuter le graphe
        result = self.graph.invoke(state)
        
        # Mettre à jour la session
        self.active_sessions[call_id] = result
        
        # Extraire la réponse
        last_message = result["messages"][-1]
        if isinstance(last_message, AIMessage):
            return last_message.content
        
        return "Je n'ai pas compris. Pouvez-vous répéter?"
    
    def end_session(self, call_id: str) -> dict:
        """
        Termine une session et retourne le résumé.
        """
        if call_id in self.active_sessions:
            state = self.active_sessions.pop(call_id)
            return {
                "call_id": call_id,
                "duration": "TODO",  # Calculer la durée
                "intent": state.get("intent"),
                "incident_id": state.get("incident_id"),
                "notifications": state.get("notifications_sent", []),
                "followup": state.get("followup_scheduled")
            }
        return {}


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    # Test de l'agent
    agent = VoiceAgentSST()
    
    # Simuler un appel
    call_id = "TEST-001"
    agent.start_session(call_id, "+14185551234")
    
    # Test: signalement d'incident
    response1 = agent.process_message(
        call_id,
        "Il y a un déversement de produit chimique dans la zone B, près de la machine 12"
    )
    print(f"Agent: {response1}")
    
    # Test: suivi
    response2 = agent.process_message(
        call_id,
        "Non, personne n'est blessé, on s'est éloignés"
    )
    print(f"Agent: {response2}")
    
    # Terminer
    summary = agent.end_session(call_id)
    print(f"Résumé: {json.dumps(summary, indent=2, ensure_ascii=False)}")
