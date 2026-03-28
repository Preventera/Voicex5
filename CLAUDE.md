# CLAUDE.md — VoiceX5 Project Memory

## Identity
**VoiceX5 / VOICEX5-GEMINI-LIVE** — Quiz vocal IA adaptatif pour évaluation de la littératie IA en santé-sécurité au travail (SST/HSE). Module vocal de la plateforme LiteraCIA, partie de l'écosystème AgenticX5 par Preventera.

**Nom de code MVP :** VOICEX5-GEMINI-LIVE
**Version :** 1.0.0-mvp
**Date :** 28 mars 2026
**Statut :** MVP fonctionnel — Quiz vocal + Persistance Supabase + Agent Claude #2 (en attente crédits API)
**Lead :** Mario Deshaies (VP AI | CTO)
**Repo :** https://github.com/Preventera/Voicex5

---

## Architecture
┌─────────────────────────────────────────────────┐
│  FRONTEND (HTML standalone + React 18 CDN)       │
│  voice/voice-quiz-demo.html                      │
│  - Accueil (6 axes, consentement Loi 25)         │
│  - Quiz actif (micro, transcription, progression)│
│  - Résultats (radar chart, barres, analyse)      │
│  Tech: React 18, Chart.js, Tailwind CSS, DM Sans │
└──────────────────┬──────────────────────────────┘
                   │ WebSocket (bidirectionnel)
┌──────────────────▼──────────────────────────────┐
│  BACKEND (FastAPI Python)                        │
│  voice/api_voice.py — Port 8003                  │
│  - WS /ws/voice/quiz (pont frontend↔Gemini)      │
│  - POST /api/voice/skills-gap (Agent Claude #2)  │
│  - GET /api/voice/sessions/{id}                  │
│  - GET /api/voice/results/{user_id}              │
│  - GET /health                                   │
└──────────────────┬──────────────────────────────┘
                   │ WebSocket          │ REST
┌──────────────────▼─────────┐  ┌──────▼──────────┐
│  GEMINI LIVE API            │  │  CLAUDE API      │
│  gemini-3.1-flash-live-     │  │  Sonnet 4.6      │
│  preview                    │  │  Skills Gap Agent │
│  Audio natif in/out <1s     │  │  Post-quiz        │
│  Function calling (scoring) │  │  Plan 12 semaines │
└────────────────────────────┘  └─────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│  SUPABASE (INITIA-X5 project)                    │
│  https://tpvqyyiukvuciaaagfyj.supabase.co       │
│  Tables: voice_sessions, radar_results           │
└─────────────────────────────────────────────────┘

**Approche LLM :** Hybride — Gemini Live pour le vocal temps réel, Claude pour les analyses texte post-quiz.

---

## Project Structure
VoiceX5/
├── voice/                           # MODULE VOICEX5-GEMINI-LIVE
│   ├── __init__.py                  # Exports
│   ├── voice_config.py              # Config Gemini, 18 questions, prompts, Pydantic models
│   ├── gemini_live_service.py       # Pont WebSocket Gemini Live API (keepalive, reconnexion)
│   ├── voice_quiz_agent.py          # Logique quiz (scoring, calcul axes, Supabase)
│   ├── skills_gap_agent.py          # Agent Claude #2 (analyse post-quiz, plan 12 semaines)
│   ├── api_voice.py                 # Serveur FastAPI (WebSocket + REST endpoints)
│   ├── test_supabase.py             # Script test connexion Supabase
│   └── voice-quiz-demo.html         # Frontend standalone (accueil, quiz, résultats)
│
├── {src/                            # ANCIEN CODE (Whisper+Piper+TEN — remplacé)
├── .env                             # Clés API (GEMINI_API_KEY, ANTHROPIC_API_KEY, SUPABASE_*)
├── .env.example                     # Template clés
├── CLAUDE.md                        # CE FICHIER
├── README.md                        # Documentation projet
├── requirements.txt                 # Dépendances Python (ancien)
├── Dockerfile                       # Docker (ancien)
└── docker-compose.yml               # Docker compose (ancien)

---

## Quick Start
```bash
# 1. Clés API dans .env
GEMINI_API_KEY=xxx          # https://aistudio.google.com/apikey (gratuit)
ANTHROPIC_API_KEY=xxx       # https://console.anthropic.com/settings/keys
SUPABASE_URL=https://tpvqyyiukvuciaaagfyj.supabase.co
SUPABASE_KEY=xxx            # anon key depuis Supabase Settings > API

# 2. Installer dépendances
pip install fastapi uvicorn websockets google-genai supabase anthropic python-dotenv

# 3. Lancer le serveur (port 8003)
cd VoiceX5
python -m voice.api_voice

# 4. Lancer le frontend (port 8080)
python -m http.server 8080 --directory voice

# 5. Ouvrir Chrome
http://localhost:8080/voice-quiz-demo.html
```

---

## Quiz Radar Vocal — 18 Questions × 6 Axes

### 6 Axes Radar Literacy
1. **Compréhension Technique IA** — Concepts IA, ML, modèles prédictifs
2. **Usage Opérationnel** — Outils IA en SST, déploiement, KPIs
3. **Pensée Critique** — Limites IA, biais, validation résultats
4. **Éthique & Conformité** — Vie privée, Loi 25, discrimination algorithmique
5. **Collaboration Humain-IA** — HITL, gestion changement, multidisciplinaire
6. **Apprentissage Continu** — Veille techno, plan formation, résilience

### Scoring
- 3 questions ouvertes par axe (18 total)
- Gemini score chaque réponse 0-20 via function calling
- Score axe = (sum 3 questions) / 60 × 100
- Score global = moyenne 6 axes
- Niveaux : Novice (0-20), Débutant (20-40), Intermédiaire (40-60), Avancé (60-80), Expert (80-100)

### Source des questions
- Générées par IA à partir des 6 axes LiteraCIA et du contexte SST québécois
- NON validées psychométriquement — MVP seulement
- Validation par experts SST requise avant déploiement production

---

## Database Schema (Supabase)
```sql
-- Sessions quiz vocaux
voice_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE,
    user_id TEXT,
    status TEXT DEFAULT 'active',        -- active|completed|completed_partial|abandoned
    language TEXT DEFAULT 'fr-CA',
    question_scores JSONB DEFAULT '[]',  -- [{question_id, axe_id, score, justification}]
    axes_scores JSONB,                   -- {"axe1": 70, "axe2": 55, ...}
    overall_score INTEGER,               -- 0-100
    level TEXT,                          -- Novice|Débutant|Intermédiaire|Avancé|Expert
    summary TEXT,                        -- Résumé Gemini
    duration_seconds INTEGER,
    questions_answered INTEGER DEFAULT 0,
    gemini_model TEXT DEFAULT 'gemini-3.1-flash-live-preview',
    audio_stored BOOLEAN DEFAULT FALSE,  -- JAMAIS stocké (Loi 25)
    consent_given BOOLEAN DEFAULT FALSE
)

-- Résultats radar (compatible LiteraCIA)
radar_results (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    overall_score INTEGER,
    level TEXT,
    axes JSONB,
    recommendations JSONB,
    source TEXT DEFAULT 'voice_quiz_gemini_live',
    created_at TIMESTAMP DEFAULT NOW()
)
```

---

## API Endpoints

| Route | Méthode | Rôle |
|---|---|---|
| /ws/voice/quiz | WebSocket | Pont bidirectionnel frontend ↔ Gemini Live |
| /api/voice/sessions | POST | Créer session (alternative REST) |
| /api/voice/sessions/{id} | GET | État session (scores partiels, progression) |
| /api/voice/results/{user_id} | GET | Historique quiz vocaux d'un utilisateur |
| /api/voice/skills-gap | POST | Agent Claude #2 — analyse post-quiz |
| /health | GET | Status API + Supabase + Gemini |

---

## Gemini Live API — Notes Techniques

- **Modèle :** gemini-3.1-flash-live-preview (lancé 27 mars 2026)
- **URI WebSocket :** wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=API_KEY
- **Audio format :** PCM16, 16kHz input, 24kHz output
- **Format envoi audio :** {"realtime_input": {"audio": {"data": base64, "mime_type": "audio/pcm;rate=16000"}}}
- **Keepalive :** Chunk silence 320 bytes toutes les 15s pour maintenir la session
- **VAD :** automaticActivityDetection activé
- **Function calling :** score_response (par question) + finalize_quiz (fin quiz)
- **Latence :** <1 seconde réponse
- **Coût estimé :** ~0,15$ USD par quiz complet (18 questions)

### Modèles testés (historique debug)
- ❌ gemini-2.5-flash-native-audio — n'existe pas
- ❌ gemini-2.0-flash-live-001 — n'existe pas en v1beta
- ❌ gemini-2.5-flash-preview-native-audio-dialog — n'existe pas
- ✅ gemini-3.1-flash-live-preview — FONCTIONNE

---

## Agent Claude #2 — Skills Gap Analyzer

- **Modèle :** Claude Sonnet 4.6 (claude-sonnet-4-6-20250514)
- **Trigger :** Bouton "Analyser mes résultats en profondeur" sur écran résultats
- **Input :** 6 scores axes + score global + niveau + summary Gemini
- **Output JSON structuré :**
  - analysis_summary (synthèse 3-5 phrases)
  - top_priorities (max 3, axes < 60%)
  - quick_wins (5 micro-learnings < 15 min)
  - plan_12_semaines (semaine par semaine, 4-8h/semaine)
  - forces_identifiees (axes >= 60%)
  - estimation_progression (niveau cible, semaines, heures)
- **Coût :** ~0,04$ USD par analyse
- **Statut :** Code prêt, en attente crédits API Anthropic

---

## Bugs Résolus

1. **Dedup scores** — Gemini re-score parfois la même question → garde-fou question_id unique
2. **Modèle Gemini** — 3 tentatives avant de trouver le bon identifiant (3.1-flash-live-preview)
3. **Format audio 3.1** — realtime_input.audio remplace realtime_input.media_chunks (déprécié)
4. **RLS Supabase** — GRANT + CREATE POLICY nécessaires pour insertion via anon key
5. **Colonnes Supabase** — Noms de colonnes dans le code ne matchaient pas la table
6. **Keepalive** — Session Gemini timeout après ~10 min → chunk silence toutes les 15s
7. **VAD/Turn-taking** — Gemini parlait sans écouter → automaticActivityDetection + prompt renforcé

---

## Conformité Loi 25

- Audio JAMAIS stocké (audio_stored = FALSE par défaut)
- Consentement explicite requis (popup Loi 25 avant activation micro)
- Seuls les scores et transcriptions sont persistés
- Supabase actuellement sur us-east-1 — migrer vers ca-central-1 pour production
- Données anonymisables (user_id = identifiant choisi par l'utilisateur)

---

## Coûts API

| Composant | Coût / quiz |
|---|---|
| Gemini Live (audio in/out + contexte) | ~0,15$ USD |
| Claude Skills Gap (post-quiz) | ~0,04$ USD |
| **Total par quiz complet** | **~0,19$ USD** |
| Free tier Gemini | ~1000 req/jour (suffisant pour dev) |

---

## Roadmap

### ✅ Fait (28 mars 2026)
- [x] MVP Quiz Radar Vocal fonctionnel
- [x] Gemini 3.1 Flash Live Preview intégré
- [x] 18 questions × 6 axes configurées
- [x] Persistance Supabase (voice_sessions + radar_results)
- [x] Frontend UX amélioré (radar chart, barres, forces/faiblesses)
- [x] Agent Claude #2 Skills Gap (code prêt)
- [x] Pushé sur GitHub (3 commits)

### En cours
- [ ] Activer crédits API Anthropic pour Agent Claude #2
- [ ] Quiz complet 18 questions test end-to-end
- [ ] Validation questions par experts SST

### Prochaines étapes
- [ ] Déploiement en ligne (Netlify ou Vercel)
- [ ] Réactiver Supabase LiteracIA (ca-central-1) pour conformité Loi 25
- [ ] Diagnostic Skills Gap Vocal (use case #2 — interview ouverte)
- [ ] Scénarios Immersifs Vocaux (use case #3)
- [ ] Intégration knowledge-base-complete-1000.json pour contextualiser les réponses
- [ ] Calibration scoring avec panel experts SST québécois
- [ ] Multilingual EN pour ReadinessX5 international

---

## Ecosystem Context

VoiceX5 est le module vocal de **LiteraCIA AgenticX5** dans l'écosystème AgenticX5 :

- **LiteraCIA** → Plateforme formation adaptative (FastAPI, Supabase, 2 agents IA)
- **IGNITIA** → Priorisation projets SST/IA (algorithme ELON)
- **SafetyGraph** → Neo4j Knowledge Graph (22M+ nodes, 40+ normes)
- **EDGY-AgenticX5** → Orchestrateur central (122+ agents)
- **SCRAPLING-X5** → Collecte données SST (web scraping adaptatif)
- **MEMORIA-X5** → Mémoire unifiée cross-cutting (Redis + Neo4j + Pinecone)

### Architecture WAVE 4 (5 niveaux)
- N1 Collection → SCRAPLING-X5
- N2 Normalisation → SafetyGraph
- N3 Intelligence → EDGY-AgenticX5
- N4 Coordination → SENTINEL·X5
- N5 Interface → **VoiceX5** / LiteraCIA / Dashboards

---

## Contributors

**Project Lead:** Mario Deshaies
**Role:** VP AI | CTO | Chief AI Strategy Officer
**Organization:** Preventera / ReadinessX5 International Inc.

---

**Last Updated:** 28 mars 2026
**Document Version:** 1.0.0
**Next Review:** Après activation Agent Claude #2
