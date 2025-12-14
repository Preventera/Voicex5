"""
Neo4j SafetyGraph Tools - EDGY AgenticX5
Outils de gestion du Knowledge Graph SST pour l'agent vocal

Pour: Preventera / GenAISafety
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


# ============================================================
# CLIENT NEO4J (Simulation)
# ============================================================

class SafetyGraphClient:
    """
    Client pour interagir avec SafetyGraph (Neo4j).
    En production, utiliser le driver officiel neo4j-python.
    """
    
    def __init__(self):
        # En production: connexion réelle
        # self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Simulation: stockage en mémoire
        self._incidents = {}
        self._voice_interactions = {}
        self._tasks = {}
        self._notifications = {}
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """Exécute une requête Cypher (simulation)"""
        # En production: self.driver.session().run(query, parameters)
        print(f"📊 Cypher Query: {query[:100]}...")
        return []
    
    def close(self):
        """Ferme la connexion"""
        pass


# Instance globale
_graph_client = SafetyGraphClient()


# ============================================================
# FONCTIONS SAFETYGRAPH
# ============================================================

def create_incident_from_voice(
    voice_id: str,
    phone: str,
    transcript: str,
    incident_type: str,
    location: str,
    severity: int,
    description: str,
    cnesst_code: Optional[str] = None
) -> Dict[str, str]:
    """
    Crée un incident dans SafetyGraph à partir d'une interaction vocale.
    
    Crée deux nœuds:
    1. VoiceInteraction - L'enregistrement de l'appel
    2. Incident - L'incident signalé
    
    Et une relation CREATED_INCIDENT entre les deux.
    
    Args:
        voice_id: Identifiant de l'interaction vocale
        phone: Numéro de téléphone de l'appelant
        transcript: Transcription complète de l'appel
        incident_type: Type d'incident (chimique, mécanique, etc.)
        location: Lieu de l'incident
        severity: Gravité (1-10)
        description: Description de l'incident
        cnesst_code: Code CNESST si applicable
    
    Returns:
        Dictionnaire avec l'ID de l'incident créé
    """
    incident_id = f"INC-{datetime.now().strftime('%Y')}-{uuid.uuid4().hex[:4].upper()}"
    
    # Requête Cypher (simulation)
    query = """
    // Créer l'interaction vocale
    CREATE (v:VoiceInteraction {
        id: $voice_id,
        timestamp: datetime(),
        caller_phone: $phone,
        transcript: $transcript,
        intent: 'incident_report',
        handled_by: 'VoiceAgent-SST'
    })
    
    // Créer l'incident
    CREATE (i:Incident {
        id: $incident_id,
        type: $incident_type,
        location: $location,
        severity: $severity,
        description: $description,
        status: 'OPEN',
        created_via: 'voice',
        cnesst_code: $cnesst_code,
        created_at: datetime()
    })
    
    // Créer la relation
    CREATE (v)-[:CREATED_INCIDENT]->(i)
    
    RETURN i.id AS incident_id
    """
    
    parameters = {
        "voice_id": voice_id,
        "phone": phone,
        "transcript": transcript,
        "incident_id": incident_id,
        "incident_type": incident_type,
        "location": location,
        "severity": severity,
        "description": description,
        "cnesst_code": cnesst_code or ""
    }
    
    # Simulation: stocker localement
    _graph_client._voice_interactions[voice_id] = {
        "id": voice_id,
        "timestamp": datetime.now().isoformat(),
        "caller_phone": phone,
        "transcript": transcript
    }
    
    _graph_client._incidents[incident_id] = {
        "id": incident_id,
        "type": incident_type,
        "location": location,
        "severity": severity,
        "description": description,
        "status": "OPEN",
        "cnesst_code": cnesst_code,
        "created_at": datetime.now().isoformat(),
        "voice_id": voice_id
    }
    
    print(f"✅ Incident créé: {incident_id}")
    print(f"   Type: {incident_type}")
    print(f"   Lieu: {location}")
    print(f"   Gravité: {severity}")
    
    return {"incident_id": incident_id}


def find_similar_incidents(
    location: str,
    incident_type: str,
    days_back: int = 365
) -> List[Dict]:
    """
    Recherche des incidents similaires dans SafetyGraph.
    
    Args:
        location: Zone/lieu de l'incident
        incident_type: Type d'incident
        days_back: Nombre de jours d'historique
    
    Returns:
        Liste des incidents similaires
    """
    query = """
    MATCH (i:Incident)
    WHERE i.location = $location
      AND i.type = $type
      AND i.timestamp > datetime() - duration('P' + $days + 'D')
    RETURN i.id AS id, 
           i.description AS description,
           i.severity AS severity,
           i.resolution AS resolution,
           duration.between(i.timestamp, datetime()).days AS days_ago
    ORDER BY i.timestamp DESC
    LIMIT 5
    """
    
    # Simulation
    results = []
    for inc_id, inc in _graph_client._incidents.items():
        if inc.get("location") == location or inc.get("type") == incident_type:
            results.append({
                "id": inc_id,
                "description": inc.get("description", ""),
                "severity": inc.get("severity", 5),
                "resolution": inc.get("resolution"),
                "days_ago": 30  # Simulation
            })
    
    return results[:5]


def get_zone_risk_profile(zone: str) -> Dict[str, Any]:
    """
    Récupère le profil de risque d'une zone.
    
    Args:
        zone: Identifiant de la zone
    
    Returns:
        Profil de risque avec statistiques
    """
    query = """
    MATCH (i:Incident {location: $zone})
    WHERE i.timestamp > datetime() - duration('P180D')
    WITH count(i) AS total,
         sum(CASE WHEN i.severity >= 7 THEN 1 ELSE 0 END) AS severe,
         collect(DISTINCT i.type) AS types
    RETURN total AS incidents_6_months,
           severe AS severe_incidents,
           types AS incident_types,
           toFloat(severe)/total AS severity_ratio
    """
    
    # Simulation
    zone_incidents = [
        inc for inc in _graph_client._incidents.values()
        if inc.get("location") == zone
    ]
    
    total = len(zone_incidents)
    severe = len([i for i in zone_incidents if i.get("severity", 0) >= 7])
    types = list(set(i.get("type", "unknown") for i in zone_incidents))
    
    return {
        "zone": zone,
        "incidents_6_months": total,
        "severe_incidents": severe,
        "incident_types": types,
        "severity_ratio": severe / max(total, 1),
        "risk_level": "HIGH" if severe > 2 else "MEDIUM" if total > 5 else "LOW"
    }


def notify_stakeholders(zone: str, severity: int) -> Dict[str, Dict]:
    """
    Identifie les personnes à notifier selon la zone et la gravité.
    
    Args:
        zone: Zone de l'incident
        severity: Gravité (1-10)
    
    Returns:
        Contacts à notifier avec leurs informations
    """
    query = """
    MATCH (z:Zone {name: $zone})<-[:SUPERVISES]-(s:Supervisor)
    MATCH (z)<-[:HSE_RESPONSIBLE_FOR]-(h:HSEOfficer)
    RETURN s.name AS supervisor_name, 
           s.phone AS supervisor_phone,
           s.email AS supervisor_email,
           h.name AS hse_name,
           h.phone AS hse_phone,
           h.email AS hse_email
    LIMIT 1
    """
    
    # Simulation: contacts par défaut
    contacts = {}
    
    # Superviseur (toujours)
    contacts["supervisor"] = {
        "name": f"Superviseur {zone}",
        "phone": "+14185550001",
        "email": f"superviseur.{zone.lower().replace(' ', '')}@company.com"
    }
    
    # HSE (gravité >= 5)
    if severity >= 5:
        contacts["hse_officer"] = {
            "name": "Marie Dubois - HSE",
            "phone": "+14185550002",
            "email": "marie.dubois@company.com"
        }
    
    # Direction (gravité >= 8)
    if severity >= 8:
        contacts["direction"] = {
            "name": "Direction SST",
            "phone": "+14185550003",
            "email": "direction.sst@company.com"
        }
    
    # Services d'urgence (gravité >= 9)
    if severity >= 9:
        contacts["emergency"] = {
            "name": "Services d'urgence",
            "phone": "911",
            "email": None
        }
    
    print(f"🔔 Contacts identifiés pour {zone} (gravité {severity}):")
    for role, contact in contacts.items():
        print(f"   - {role}: {contact['name']} ({contact['phone']})")
    
    return contacts


def schedule_followup(
    incident_id: str,
    delay: str = "PT2H",
    hse_officer: Optional[str] = None
) -> Dict[str, Any]:
    """
    Programme un suivi automatique pour un incident.
    
    Args:
        incident_id: ID de l'incident
        delay: Délai au format ISO 8601 (PT2H = 2 heures)
        hse_officer: Responsable assigné
    
    Returns:
        Détails de la tâche programmée
    """
    task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
    
    query = """
    CREATE (t:Task {
        id: $task_id,
        type: 'voice_followup',
        scheduled_at: datetime() + duration($delay),
        related_incident: $incident_id,
        assigned_to: $hse_officer,
        status: 'SCHEDULED'
    })
    RETURN t.id AS task_id, 
           toString(t.scheduled_at) AS scheduled_at
    """
    
    # Calculer l'heure programmée
    from datetime import timedelta
    hours = int(delay.replace("PT", "").replace("H", ""))
    scheduled_at = datetime.now() + timedelta(hours=hours)
    
    # Simulation
    _graph_client._tasks[task_id] = {
        "id": task_id,
        "type": "voice_followup",
        "scheduled_at": scheduled_at.isoformat(),
        "related_incident": incident_id,
        "assigned_to": hse_officer or "HSE Team",
        "status": "SCHEDULED"
    }
    
    print(f"⏰ Suivi programmé: {task_id}")
    print(f"   Incident: {incident_id}")
    print(f"   Heure: {scheduled_at.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Assigné à: {hse_officer or 'HSE Team'}")
    
    return {
        "task_id": task_id,
        "scheduled_at": scheduled_at.isoformat()
    }


def log_voice_interaction(
    call_id: str,
    caller_phone: str,
    duration_seconds: int,
    intent: str,
    resolved: bool,
    incident_id: Optional[str] = None,
    transcript: Optional[str] = None
) -> Dict[str, str]:
    """
    Enregistre une interaction vocale complète dans SafetyGraph.
    
    Args:
        call_id: Identifiant de l'appel
        caller_phone: Numéro de l'appelant
        duration_seconds: Durée de l'appel
        intent: Intention détectée
        resolved: Si l'appel a été résolu
        incident_id: ID de l'incident créé (si applicable)
        transcript: Transcription complète
    
    Returns:
        Confirmation de l'enregistrement
    """
    query = """
    CREATE (v:VoiceInteraction {
        id: $call_id,
        timestamp: datetime(),
        caller_phone: $caller_phone,
        duration_seconds: $duration,
        intent: $intent,
        resolved: $resolved,
        transcript: $transcript,
        related_incident: $incident_id
    })
    RETURN v.id AS voice_id
    """
    
    # Simulation
    _graph_client._voice_interactions[call_id] = {
        "id": call_id,
        "timestamp": datetime.now().isoformat(),
        "caller_phone": caller_phone,
        "duration_seconds": duration_seconds,
        "intent": intent,
        "resolved": resolved,
        "transcript": transcript,
        "related_incident": incident_id
    }
    
    print(f"📝 Interaction vocale enregistrée: {call_id}")
    print(f"   Durée: {duration_seconds}s | Intent: {intent} | Résolu: {'Oui' if resolved else 'Non'}")
    
    return {"voice_id": call_id, "status": "logged"}


def get_incident_status(incident_id: str) -> Dict[str, Any]:
    """
    Récupère le statut d'un incident.
    
    Args:
        incident_id: ID de l'incident
    
    Returns:
        Statut complet de l'incident
    """
    query = """
    MATCH (i:Incident {id: $incident_id})
    OPTIONAL MATCH (i)<-[:CREATED_INCIDENT]-(v:VoiceInteraction)
    OPTIONAL MATCH (i)-[:HAS_ACTION]->(a:Action)
    RETURN i.id AS id,
           i.status AS status,
           i.severity AS severity,
           i.description AS description,
           v.caller_phone AS reported_by,
           collect(a.description) AS actions
    """
    
    # Simulation
    if incident_id in _graph_client._incidents:
        inc = _graph_client._incidents[incident_id]
        return {
            "id": inc["id"],
            "status": inc["status"],
            "severity": inc["severity"],
            "description": inc["description"],
            "location": inc["location"],
            "type": inc["type"],
            "created_at": inc["created_at"]
        }
    
    return {"error": f"Incident {incident_id} non trouvé"}


def update_incident_status(
    incident_id: str,
    new_status: str,
    notes: Optional[str] = None
) -> Dict[str, str]:
    """
    Met à jour le statut d'un incident.
    
    Args:
        incident_id: ID de l'incident
        new_status: Nouveau statut (OPEN, IN_PROGRESS, RESOLVED, CLOSED)
        notes: Notes de mise à jour
    
    Returns:
        Confirmation de la mise à jour
    """
    query = """
    MATCH (i:Incident {id: $incident_id})
    SET i.status = $new_status,
        i.updated_at = datetime(),
        i.status_notes = $notes
    RETURN i.id AS id, i.status AS status
    """
    
    # Simulation
    if incident_id in _graph_client._incidents:
        _graph_client._incidents[incident_id]["status"] = new_status
        _graph_client._incidents[incident_id]["status_notes"] = notes
        
        print(f"✏️ Incident mis à jour: {incident_id}")
        print(f"   Nouveau statut: {new_status}")
        if notes:
            print(f"   Notes: {notes}")
        
        return {"id": incident_id, "status": new_status}
    
    return {"error": f"Incident {incident_id} non trouvé"}


# ============================================================
# STATISTIQUES ET RAPPORTS
# ============================================================

def get_voice_agent_stats(days: int = 7) -> Dict[str, Any]:
    """
    Récupère les statistiques de l'agent vocal.
    
    Args:
        days: Nombre de jours d'historique
    
    Returns:
        Statistiques d'utilisation
    """
    query = """
    MATCH (v:VoiceInteraction)
    WHERE v.timestamp > datetime() - duration('P' + $days + 'D')
    WITH count(v) AS total_calls,
         avg(v.duration_seconds) AS avg_duration,
         sum(CASE WHEN v.resolved THEN 1 ELSE 0 END) AS resolved,
         collect(v.intent) AS intents
    RETURN total_calls,
           avg_duration,
           toFloat(resolved)/total_calls * 100 AS resolution_rate,
           intents
    """
    
    # Simulation
    interactions = list(_graph_client._voice_interactions.values())
    total = len(interactions)
    resolved = len([i for i in interactions if i.get("resolved", False)])
    avg_duration = sum(i.get("duration_seconds", 0) for i in interactions) / max(total, 1)
    
    intents = {}
    for i in interactions:
        intent = i.get("intent", "unknown")
        intents[intent] = intents.get(intent, 0) + 1
    
    return {
        "period_days": days,
        "total_calls": total,
        "average_duration_seconds": avg_duration,
        "resolution_rate_percent": (resolved / max(total, 1)) * 100,
        "intents_distribution": intents,
        "incidents_created": len(_graph_client._incidents)
    }


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST: SafetyGraph Tools")
    print("=" * 60)
    
    # Test création incident
    print("\n📋 Test: Création incident")
    result = create_incident_from_voice(
        voice_id="TEST-VOICE-001",
        phone="+14185551234",
        transcript="Il y a un déversement de produit chimique dans la zone B",
        incident_type="chimique",
        location="Zone B",
        severity=7,
        description="Déversement de solvant près de la machine 12",
        cnesst_code="31-001"
    )
    print(f"   Résultat: {result}")
    
    # Test profil de risque
    print("\n📊 Test: Profil de risque zone")
    profile = get_zone_risk_profile("Zone B")
    print(f"   Résultat: {profile}")
    
    # Test contacts à notifier
    print("\n🔔 Test: Identification contacts")
    contacts = notify_stakeholders("Zone B", 7)
    print(f"   Résultat: {list(contacts.keys())}")
    
    # Test programmation suivi
    print("\n⏰ Test: Programmation suivi")
    followup = schedule_followup(
        incident_id=result["incident_id"],
        delay="PT2H",
        hse_officer="Marie Dubois"
    )
    print(f"   Résultat: {followup}")
    
    # Test statistiques
    print("\n📈 Test: Statistiques agent vocal")
    stats = get_voice_agent_stats()
    print(f"   Résultat: {stats}")
