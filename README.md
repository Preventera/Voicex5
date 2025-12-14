# 🎙️ VoiceX5 - Agents Vocaux SST Intelligents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1.svg)](https://neo4j.com/)

> **La voix qui protège vos équipes** | *The voice that protects your teams*

VoiceX5 est une plateforme d'agents vocaux temps réel dédiée à la Santé et Sécurité au Travail (SST/HSE), propulsée par l'architecture AgenticX5 et le framework EDGY.

---

## 🎯 Fonctionnalités

| Fonctionnalité | Description |
|----------------|-------------|
| 📞 **Ligne SST 24/7** | Réception d'appels téléphoniques réels via Twilio |
| 🎤 **Transcription FR-CA** | STT haute précision avec faster-whisper |
| 🧠 **Agents Intelligents** | LangGraph multi-agents spécialisés SST |
| 🔍 **Recherche Sémantique** | 793K incidents CNESST via Superlinked |
| 📊 **Knowledge Graph** | SafetyGraph Neo4j avec traçabilité complète |
| 🔔 **Notifications Auto** | SMS, Email, Slack selon gravité |
| 🗣️ **Synthèse Vocale** | Orpheus 3B pour réponses naturelles |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           VoiceX5 ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  📞 ENTRÉE          🧠 TRAITEMENT           📤 SORTIE                   │
│  ─────────          ────────────           ────────                    │
│                                                                         │
│  ┌─────────┐       ┌─────────────────┐     ┌─────────────┐             │
│  │ Twilio  │──────▶│  FastRTC        │────▶│ Orpheus TTS │             │
│  │ Phone   │       │  Gateway        │     │ Voice Out   │             │
│  └─────────┘       └────────┬────────┘     └─────────────┘             │
│                             │                                           │
│  ┌─────────┐       ┌────────▼────────┐     ┌─────────────┐             │
│  │ Gradio  │──────▶│  faster-whisper │────▶│ SMS/Email   │             │
│  │ Web UI  │       │  STT FR-CA      │     │ Alerts      │             │
│  └─────────┘       └────────┬────────┘     └─────────────┘             │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │   LangGraph     │                                  │
│                    │   Voice Agent   │                                  │
│                    │   ┌───────────┐ │                                  │
│                    │   │ Incident  │ │                                  │
│                    │   │ Procedure │ │                                  │
│                    │   │ Emergency │ │                                  │
│                    │   └───────────┘ │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│           ┌─────────────────┼─────────────────┐                        │
│           │                 │                 │                        │
│   ┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐               │
│   │  Superlinked  │ │   Neo4j       │ │    Claude     │               │
│   │  Vector DB    │ │  SafetyGraph  │ │    LLM        │               │
│   │  (Qdrant)     │ │               │ │               │               │
│   └───────────────┘ └───────────────┘ └───────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Architecture 5 Niveaux AgenticX5

| Niveau | Rôle | Composants VoiceX5 |
|--------|------|-------------------|
| **N1** | Collecte | FastRTC, Twilio, faster-whisper |
| **N2** | Normalisation | Intent Classification, Entity Extraction |
| **N3** | Analyse | Superlinked Search, Risk Scoring |
| **N4** | Recommandation | Agent Procédures, Notifications |
| **N5** | Orchestration | HUGO Maestro, Human-in-the-loop |

---

## 🚀 Quick Start

### Prérequis

- Python 3.11+
- Docker & Docker Compose
- GPU NVIDIA (recommandé pour TTS)
- Clé API Anthropic Claude
- Compte Twilio (optionnel pour téléphonie)

### Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/Preventera/VoiceX5.git
cd VoiceX5

# 2. Copier la configuration
cp .env.example .env

# 3. Éditer .env avec vos clés API
nano .env

# 4. Lancer les services
docker-compose up -d

# 5. Vérifier le statut
curl http://localhost:8000/health
```

### Test Local (Gradio)

```bash
# Interface web locale
python -m src.audio.fastrtc_handler --gradio --port 8001

# Ouvrir http://localhost:8001
```

### Test Téléphone (Twilio)

```bash
# Configurer le webhook Twilio vers:
# https://votre-domaine.com/twilio/voice

# Appeler votre numéro Twilio
```

---

## 📁 Structure du Projet

```
VoiceX5/
├── README.md
├── docker-compose.yml
├── .env.example
├── requirements.txt
│
├── src/
│   ├── agents/                 # Agents LangGraph
│   │   ├── voice_agent.py      # Agent principal
│   │   ├── incident_agent.py   # Gestion incidents
│   │   ├── procedure_agent.py  # Questions procédures
│   │   └── emergency_agent.py  # Urgences vitales
│   │
│   ├── audio/                  # Traitement audio
│   │   ├── fastrtc_handler.py  # Gateway audio
│   │   ├── stt_processor.py    # Speech-to-Text
│   │   └── tts_processor.py    # Text-to-Speech
│   │
│   ├── knowledge/              # Bases de connaissances
│   │   ├── neo4j_tools.py      # SafetyGraph
│   │   ├── superlinked_tools.py# Recherche vectorielle
│   │   └── schemas/            # Schémas Cypher/RDF
│   │
│   └── api/                    # API REST
│       ├── main.py             # FastAPI app
│       ├── routes/             # Endpoints
│       └── middleware/         # Auth, logging
│
├── config/
│   ├── agents.yaml             # Config agents
│   ├── intents.yaml            # Classification intents
│   └── notifications.yaml      # Config alertes
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── API.md
│
└── scripts/
    ├── init_neo4j.py           # Init SafetyGraph
    ├── load_cnesst_data.py     # Charger incidents
    └── deploy_runpod.sh        # Déploiement cloud
```

---

## 🔧 Configuration

### Variables d'environnement (.env)

```bash
# === API KEYS ===
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# === DATABASES ===
NEO4J_URI=bolt://neo4j:7687
NEO4J_PASSWORD=voicex5secure
QDRANT_URL=http://qdrant:6333

# === AUDIO ===
STT_MODEL=large-v3
STT_LANGUAGE=fr
TTS_ENDPOINT=http://orpheus:8080

# === OBSERVABILITY ===
OPIK_API_KEY=...
GRAFANA_PASSWORD=admin
```

---

## 📞 Cas d'Usage

### 1. Signalement Incident

```
👷 "Il y a un déversement chimique en zone B, machine 12"

🤖 "J'ai enregistré l'incident INC-2025-0847. 
    Évacuez un périmètre de 15 mètres.
    J'ai alerté votre superviseur Jean Tremblay.
    La fiche de sécurité vous est envoyée par SMS."
```

### 2. Question Procédure

```
👷 "Comment faire le cadenassage de la presse hydraulique?"

🤖 "Voici les 6 étapes principales:
    1. Arrêter la presse au bouton d'urgence
    2. Attendre l'arrêt du volant d'inertie
    3. Couper au sectionneur principal
    [...]
    Je vous envoie le document complet par SMS."
```

### 3. Urgence Vitale

```
👷 "Il y a un blessé grave, chute de hauteur!"

🤖 "URGENCE ENREGISTRÉE.
    Ne bougez pas le blessé.
    Les secours sont alertés.
    Restez en ligne, un responsable HSE arrive."
```

---

## 📊 Métriques & Observabilité

### Dashboard Grafana

Accès: http://localhost:3000 (admin/admin)

- **Appels**: Volume, durée moyenne, taux résolution
- **Incidents**: Créations, gravité, zones à risque
- **Performance**: Latence STT/TTS, temps réponse agent
- **Qualité**: Précision intent, satisfaction (si feedback)

### Traçabilité Opik

Toutes les interactions LLM sont tracées pour:
- Debugging des conversations
- Amélioration continue des prompts
- Audit de conformité

---

## 🔒 Sécurité & Conformité

| Standard | Statut |
|----------|--------|
| CNESST | ✅ Codes intégrés |
| ISO 45001 | ✅ Mapping clauses |
| Loi 25 (Québec) | ✅ Données personnelles |
| RGPD | ✅ Consentement, effacement |
| EU AI Act | 🟡 En préparation |

---

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

---

## 📄 Licence

MIT License - voir [LICENSE](LICENSE)

---

## 🙏 Crédits

- **Inspiration**: [neural-maze/realtime-phone-agents-course](https://github.com/neural-maze/realtime-phone-agents-course)
- **Framework**: [FastRTC](https://github.com/gradio-app/fastrtc) by Hugging Face
- **Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/)
- **Vector Search**: [Superlinked](https://superlinked.com/)

---

<div align="center">

**VoiceX5** - Propulsé par **EDGY-AgenticX5**

*Preventera / GenAISafety*

🎙️ La voix qui protège vos équipes

</div>
