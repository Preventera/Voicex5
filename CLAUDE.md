# CLAUDE.md — VoiceX5 + SafeTalkX5

**Dernière mise à jour :** 31 mars 2026
**Lead :** Mario Deshaies (VP AI | CTO) — Preventera / ReadinessX5 International Inc.
**Repo :** https://github.com/Preventera/Voicex5 — 17 commits

---

## 1. VUE D'ENSEMBLE

VoiceX5 est un hub vocal SST avec 2 produits dans un seul repo :
- **Quiz Radar Vocal** (`voice/`) — Évalue la littératie IA en SST via Gemini Live
- **SafeTalkX5** (`safetalk/`) — Causeries SST interactives vocales 6 phases

Stack : Gemini Live API (`gemini-3.1-flash-live-preview`), FastAPI (port 8003), Supabase, Chart.js, React 18 CDN

---

## 2. ARCHITECTURE

```
VoiceX5/
├── voice/                    # Quiz Radar Vocal
│   ├── voice_config.py       # Config Gemini, 18 questions, prompts, Pydantic models
│   ├── gemini_live_service.py # WebSocket Gemini Live (keepalive, reconnexion)
│   ├── voice_quiz_agent.py   # Scoring, calcul axes, dedup, résultats partiels
│   ├── skills_gap_agent.py   # Agent Claude #2 (EN ATTENTE CRÉDITS)
│   ├── api_voice.py          # Serveur FastAPI principal (voice + safetalk intégré)
│   ├── test_supabase.py      # Script test connexion Supabase
│   └── voice-quiz-demo.html  # Frontend quiz (React 18, Chart.js, Tailwind)
│
├── safetalk/                 # SafeTalkX5 Causeries SST
│   ├── prevention_data.py    # Base prévention statique 7 secteurs 9 risques
│   ├── cnesst_parser.py      # Parse 697K records CNESST + fallback synthétique 500
│   ├── osha_scraper.py       # API OSHA severe injuries + cache + fallback 100
│   ├── analysis_engine.py    # 4 méthodes (ADC/ICAM/BowTie/HFACS) règles + Claude
│   ├── safetalk_generator.py # V4 6 phases avec données prévention
│   ├── safetalk_voice.py     # System prompt Gemini 6 phases + SafeTalkLiveSession
│   ├── api_safetalk.py       # FastAPI endpoints (router intégré dans api_voice)
│   ├── safetalk-demo.html    # Frontend 3 écrans (sélection, live, résumé)
│   └── data/                 # CSV CNESST (placeholder — à copier)
│
├── .env                      # GEMINI_API_KEY, ANTHROPIC_API_KEY, SUPABASE_URL/KEY
├── CLAUDE.md                 # Ce fichier
└── requirements.txt
```

---

## 3. SAFETALKX5 V4 — 6 PHASES (refonte 29-31 mars 2026)

Structure basée sur meilleures pratiques CNESST/APSAM/CCHST et 100 principes de communication SST :

| Phase | Nom | Durée | Objectif |
|---|---|---|---|
| 1 | Ouverture | 1-2 min | Objectif clair, lien travail réel, ton positif |
| 2 | Retour d'expérience | 3-4 min | Incident anonymisé, storytelling humain |
| 3 | Dialogue participatif | 4-5 min | 3-4 questions ouvertes, écoute active |
| 4 | Reconnaissance | 2 min | Nommer comportements sécuritaires positifs |
| 5 | Actions & Retour | 2-3 min | Retour sur Phase 3, moyens prévention, engagement |
| 6 | Clôture | 1 min | Réflexe du jour, "encore une inquiétude?", ressource |

**Principes clés :**
- Participatif > confrontant
- Ton positif : "on fait comme ça" plutôt que "il ne faut pas"
- Normes techniques → PDF post-causerie SEULEMENT (pas oral)
- Reconnaissance des pratiques, pas juste absence d'accident
- Transitions explicites entre chaque phase (max 3 échanges par phase)

---

## 4. PREVENTION_DATA.PY — Données prévention statiques

7 secteurs, 9 types de risques, 2 sorties :
- **ORAL** : moyens_prevention, questions_dialogue, exemples_reconnaissance, reflexe_du_jour, ressource_reference, ouverture_theme
- **PDF** : normes_csa, articles_rsst, guides_asp, urls

**Secteurs :** Construction (23), Fabrication (31-33), Mines (21), Transport (48-49), Santé (62), Énergie (22), Général (*)

**RISK_ALIASES** : 30 entrées de normalisation (chute→chute, Machines→machine, RPS→psy, etc.)
**Lookup** : match exact → préfixe SCIAN → générique (*) → fallback EPI

---

## 5. QUIZ RADAR VOCAL — État

- 18 questions × 6 axes radar literacy IA (Compréhension technique, Usage opérationnel, Pensée critique, Éthique & Conformité, Collaboration Humain-IA, Apprentissage continu)
- Gemini Live scoring via function calling (score_response + finalize_quiz)
- Supabase : voice_sessions + radar_results (4+ sessions confirmées)
- Dedup scores (garde-fou question_id unique)
- Résultats partiels si 12+ questions (completed_partial)
- Keepalive silence 15s anti-timeout
- VAD automaticActivityDetection activé
- **Agent Claude #2 Skills Gap : EN ATTENTE CRÉDITS ANTHROPIC**

---

## 6. SUPABASE

- **URL** : https://tpvqyyiukvuciaaagfyj.supabase.co
- **Projet** : INITIA-X5
- **Région** : us-east-1 (à migrer ca-central-1 pour Loi 25)
- **Tables** : voice_sessions, radar_results, safetalk_sessions
- **RLS** : activé avec policy permissive (anon access)
- **Colonnes voice_sessions** : id, session_id, user_id, status, language, question_scores, axes_scores, overall_score, level, summary, duration_seconds, questions_answered, started_at, completed_at, gemini_model, audio_stored, consent_given

---

## 7. GEMINI LIVE API

- **Modèle** : `gemini-3.1-flash-live-preview` (lancé 27 mars 2026 — SEUL QUI FONCTIONNE)
- **URI** : `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=API_KEY`
- **Audio** : PCM16, 16kHz input, 24kHz output
- **Keepalive** : chunk silence 320 bytes / 15s
- **Format audio** : `{"realtime_input": {"audio": {"data": base64, "mime_type": "audio/pcm;rate=16000"}}}`
- **Coût** : ~0,15$ USD / quiz, free tier ~1000 req/jour
- **Narration texte→audio** : ne fonctionne PAS avec client_content (erreur 1007) — fallback speechSynthesis navigateur

### Modèles testés (historique debug)
- ❌ gemini-2.5-flash-native-audio
- ❌ gemini-2.0-flash-live-001
- ❌ gemini-2.5-flash-preview-native-audio-dialog
- ✅ gemini-3.1-flash-live-preview

---

## 8. API ENDPOINTS

| Route | Méthode | Rôle |
|---|---|---|
| `/ws/voice/quiz` | WebSocket | Quiz vocal bidirectionnel |
| `/ws/safetalk/live` | WebSocket | Causerie interactive bidirectionnelle |
| `/api/voice/skills-gap` | POST | Agent Claude #2 analyse post-quiz |
| `/api/voice/sessions/{id}` | GET | État session quiz |
| `/api/safetalk/generate` | POST | Génère causerie 6 phases |
| `/api/safetalk/sectors` | GET | Liste secteurs SCIAN |
| `/api/safetalk/risk-types` | GET | Types de risques disponibles |
| `/api/safetalk/stats` | GET | Stats globales SafeTalkX5 |
| `/health` | GET | Status API + Supabase |

---

## 9. BUGS CONNUS ET ITEMS EN ATTENTE

### Bugs à corriger
- [ ] Gemini ne laisse pas assez parler les participants (Approche B — pilotage serveur à implémenter)
- [ ] Incident synthétique pas toujours cohérent avec le type de risque demandé (fallback amélioré mais données synthétiques limitées)
- [ ] Encodage UTF-8 possible dans certains contextes (vÃ©rifie au lieu de vérifie)

### Items en attente
- [ ] Approche B : pilotage serveur avec bouton "Phase suivante" dans le frontend
- [ ] Copier 6 CSV CNESST réels dans safetalk/data/ (actuellement fallback synthétique 500 records)
- [ ] Crédits API Anthropic → Agent Claude #2 Skills Gap + mode Claude SafeTalkX5
- [ ] Fiche PDF post-causerie (bouton placeholder créé, générateur PDF à implémenter)
- [ ] Connecteur SafeTwinX5 (Couche 3 — données organisationnelles)
- [ ] Intégration SCRAPLING-X5 pour données prévention dynamiques
- [ ] Migration Supabase ca-central-1 (Loi 25)
- [ ] Déploiement en ligne (Netlify)
- [ ] Mise à jour transfert de dossier

---

## 10. COMMANDES

```bash
# Lancer le serveur API (port 8003)
cd VoiceX5 && python -m voice.api_voice

# Lancer le frontend (port 8080)
cd VoiceX5 && python -m http.server 8080

# URLs
# Quiz :    http://localhost:8080/voice/voice-quiz-demo.html
# SafeTalk : http://localhost:8080/safetalk/safetalk-demo.html
# API :     http://localhost:8003/health

# Test Supabase
python -m voice.test_supabase

# Test CNESST Parser
python -m safetalk.cnesst_parser

# Test SafeTalk standalone
python -m safetalk.api_safetalk  # port 8002
```

---

## 11. PROTOCOLE DE TRAVAIL

- "Une étape à la fois / point d'arrêt"
- Nom de code et localisation avant tout code
- Pas de code sans OK explicite
- Claude Code pour implémentation, Claude.ai pour stratégie

---

## 12. CONFORMITÉ LOI 25

- Audio JAMAIS stocké (audio_stored = FALSE par défaut)
- Consentement explicite requis (popup Loi 25 avant activation micro)
- Seuls les scores et transcriptions sont persistés
- Supabase actuellement us-east-1 — migrer ca-central-1 pour production
- Données anonymisables (user_id = identifiant choisi par l'utilisateur)

---

## 13. REPOS ÉCOSYSTÈME LIÉS

| Repo | Rôle |
|---|---|
| Preventera/SafeTwinX5 | Jumeau numérique SST (Couche 3 future) |
| Preventera/scrapling-x5 | Extraction données SST (SCRAPLING-X5) |
| Preventera/Preventera-RiskSense-X5 | Profils risque + PDFs normes + site Netlify |
| Preventera/safetygraph-core | Knowledge graph Neo4j HSE (squelette) |
| Preventera/PROGRAMME-PR-VENTION-AgenticX5 | Ontologies OWL/RDF programme prévention |

---

**Document Version :** 2.0.0
**Next Review :** Après implémentation Approche B + CSV CNESST réels
