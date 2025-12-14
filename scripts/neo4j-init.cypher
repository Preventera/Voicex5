// ============================================================
// VoiceX5 - SafetyGraph Neo4j Initialization
// Schema for Voice Interactions and SST Incidents
// ============================================================

// === CONSTRAINTS ===

// VoiceInteraction
CREATE CONSTRAINT voice_interaction_id IF NOT EXISTS
FOR (v:VoiceInteraction) REQUIRE v.id IS UNIQUE;

// Incident
CREATE CONSTRAINT incident_id IF NOT EXISTS
FOR (i:Incident) REQUIRE i.id IS UNIQUE;

// Task
CREATE CONSTRAINT task_id IF NOT EXISTS
FOR (t:Task) REQUIRE t.id IS UNIQUE;

// Procedure
CREATE CONSTRAINT procedure_id IF NOT EXISTS
FOR (p:Procedure) REQUIRE p.id IS UNIQUE;

// Zone
CREATE CONSTRAINT zone_name IF NOT EXISTS
FOR (z:Zone) REQUIRE z.name IS UNIQUE;

// Worker
CREATE CONSTRAINT worker_phone IF NOT EXISTS
FOR (w:Worker) REQUIRE w.phone IS UNIQUE;

// Agent
CREATE CONSTRAINT agent_name IF NOT EXISTS
FOR (a:Agent) REQUIRE a.name IS UNIQUE;


// === INDEXES ===

CREATE INDEX incident_timestamp IF NOT EXISTS
FOR (i:Incident) ON (i.timestamp);

CREATE INDEX incident_location IF NOT EXISTS
FOR (i:Incident) ON (i.location);

CREATE INDEX incident_type IF NOT EXISTS
FOR (i:Incident) ON (i.type);

CREATE INDEX incident_severity IF NOT EXISTS
FOR (i:Incident) ON (i.severity);

CREATE INDEX voice_timestamp IF NOT EXISTS
FOR (v:VoiceInteraction) ON (v.timestamp);

CREATE INDEX voice_intent IF NOT EXISTS
FOR (v:VoiceInteraction) ON (v.intent);


// === INITIAL DATA: Agents ===

MERGE (a1:Agent {name: 'VoiceAgent-Incident'})
SET a1.description = 'Agent spécialisé dans le traitement des incidents',
    a1.type = 'incident_handler',
    a1.version = '1.0.0';

MERGE (a2:Agent {name: 'VoiceAgent-Procedure'})
SET a2.description = 'Agent spécialisé dans les questions de procédures',
    a2.type = 'procedure_handler',
    a2.version = '1.0.0';

MERGE (a3:Agent {name: 'VoiceAgent-Emergency'})
SET a3.description = 'Agent de gestion des urgences vitales',
    a3.type = 'emergency_handler',
    a3.version = '1.0.0';

MERGE (a4:Agent {name: 'HUGO-Maestro'})
SET a4.description = 'Orchestrateur principal VoiceX5',
    a4.type = 'orchestrator',
    a4.version = '1.0.0';


// === INITIAL DATA: Zones (Exemple) ===

MERGE (z1:Zone {name: 'Zone A'})
SET z1.description = 'Zone de production principale',
    z1.risk_level = 'MEDIUM';

MERGE (z2:Zone {name: 'Zone B'})
SET z2.description = 'Zone d assemblage',
    z2.risk_level = 'HIGH';

MERGE (z3:Zone {name: 'Zone C'})
SET z3.description = 'Atelier de soudure',
    z3.risk_level = 'HIGH';

MERGE (z4:Zone {name: 'Laboratoire'})
SET z4.description = 'Laboratoire contrôle qualité',
    z4.risk_level = 'MEDIUM';

MERGE (z5:Zone {name: 'Entrepôt'})
SET z5.description = 'Entrepôt de stockage',
    z5.risk_level = 'LOW';


// === INITIAL DATA: Supervisors (Exemple) ===

MERGE (s1:Supervisor {name: 'Jean Tremblay'})
SET s1.phone = '+14185550001',
    s1.email = 'jean.tremblay@company.com';

MERGE (s2:Supervisor {name: 'Marie Dubois'})
SET s2.phone = '+14185550002',
    s2.email = 'marie.dubois@company.com',
    s2.role = 'HSE Officer';

// Relations Supervisor -> Zone
MATCH (s1:Supervisor {name: 'Jean Tremblay'}), (z:Zone)
WHERE z.name IN ['Zone A', 'Zone B']
MERGE (s1)-[:SUPERVISES]->(z);

MATCH (s2:Supervisor {name: 'Marie Dubois'}), (z:Zone)
MERGE (s2)-[:HSE_RESPONSIBLE_FOR]->(z);


// === INITIAL DATA: Sample Procedures ===

MERGE (p1:Procedure {id: 'PRO-CAD-008'})
SET p1.titre = 'Cadenassage presse hydraulique',
    p1.categorie = 'cadenassage',
    p1.equipement = 'presse_hydraulique',
    p1.niveau_formation = 2,
    p1.version = '2.1';

MERGE (p2:Procedure {id: 'PRO-CHM-015'})
SET p2.titre = 'Gestion déversement produit chimique',
    p2.categorie = 'chimique',
    p2.equipement = 'general',
    p2.niveau_formation = 1,
    p2.version = '3.0';

MERGE (p3:Procedure {id: 'PRO-ERG-003'})
SET p3.titre = 'Manutention charges lourdes',
    p3.categorie = 'ergonomique',
    p3.equipement = 'general',
    p3.niveau_formation = 1,
    p3.version = '1.5';


// === STATISTICS NODE ===

MERGE (stats:Statistics {id: 'voicex5-stats'})
SET stats.initialized_at = datetime(),
    stats.total_calls = 0,
    stats.total_incidents = 0,
    stats.last_updated = datetime();


// === VERIFICATION ===

MATCH (n) 
RETURN labels(n) AS type, count(n) AS count
ORDER BY count DESC;
