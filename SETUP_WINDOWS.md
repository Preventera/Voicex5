# 🚀 VoiceX5 - Guide de Déploiement Windows + GitHub

## 📁 Votre environnement

```
Chemin local: C:\Users\Mario\Documents\2025\Projets de développement Agentique\VoiceX5
IDE: Visual Studio / VS Code
GitHub: https://github.com/Preventera/Voicex5
```

---

## 📋 Étape 1: Prérequis Windows

### 1.1 Installer Docker Desktop
1. Télécharger: https://www.docker.com/products/docker-desktop/
2. Installer avec WSL 2 backend (recommandé)
3. Redémarrer Windows
4. Lancer Docker Desktop

### 1.2 Installer Git (si pas déjà fait)
1. Télécharger: https://git-scm.com/download/win
2. Installer avec les options par défaut

### 1.3 Clé API Anthropic
1. Aller sur https://console.anthropic.com/
2. Créer une clé API
3. Copier la clé (commence par `sk-ant-...`)

---

## 📋 Étape 2: Cloner et Configurer

### Ouvrir PowerShell (Admin) et exécuter:

```powershell
# Naviguer vers votre dossier projets
cd "C:\Users\Mario\Documents\2025\Projets de développement Agentique"

# Cloner le repo (si vide) ou initialiser
git clone https://github.com/Preventera/Voicex5.git VoiceX5
cd VoiceX5

# OU si le dossier existe déjà avec les fichiers:
cd VoiceX5
git init
git remote add origin https://github.com/Preventera/Voicex5.git
```

### Copier les fichiers VoiceX5
Extraire `VoiceX5.zip` dans ce dossier, puis:

```powershell
# Configurer l'environnement
Copy-Item .env.example .env

# Éditer .env avec VS Code
code .env
```

### Dans le fichier `.env`, modifier:
```env
ANTHROPIC_API_KEY=sk-ant-api03-VOTRE_VRAIE_CLE_ICI
```

---

## 📋 Étape 3: Push vers GitHub

```powershell
# Ajouter tous les fichiers
git add .

# Premier commit
git commit -m "🎙️ Initial commit - VoiceX5 Voice Agents SST

- Architecture 5 niveaux AgenticX5
- Agents LangGraph (Incident, Procedure, Emergency)
- FastRTC audio streaming
- Superlinked vector search
- Neo4j SafetyGraph integration
- Docker Compose stack complet"

# Push vers GitHub
git branch -M main
git push -u origin main
```

---

## 📋 Étape 4: Lancer VoiceX5

### Option A: Script PowerShell (recommandé)
```powershell
# Exécuter le script de démarrage
.\scripts\start.ps1
```

### Option B: Commandes manuelles
```powershell
# Démarrer Docker Desktop d'abord, puis:
docker compose up -d

# Vérifier les logs
docker logs -f voicex5-api

# Tester l'API
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

---

## 📋 Étape 5: Tester

### Test via PowerShell:
```powershell
# Test signalement incident
$body = @{
    message = "Il y a un déversement de produit chimique dans la zone B, près de la machine 12"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/message" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

### Test via navigateur:
- Ouvrir: http://localhost:8000/docs
- Tester l'endpoint `/api/v1/message`

---

## 🔧 Commandes Utiles

### Docker
```powershell
# Voir les conteneurs
docker ps

# Logs en temps réel
docker logs -f voicex5-api

# Arrêter tout
docker compose down

# Redémarrer
docker compose restart

# Rebuild après modifications
docker compose up -d --build
```

### Git
```powershell
# Voir le statut
git status

# Nouveau commit
git add .
git commit -m "Description des changements"
git push

# Récupérer les dernières modifications
git pull
```

---

## 🌐 Points d'accès après démarrage

| Service | URL |
|---------|-----|
| VoiceX5 API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |
| Grafana | http://localhost:3000 |

---

## ⚠️ Troubleshooting

### Docker ne démarre pas
```powershell
# Vérifier que WSL 2 est installé
wsl --status

# Installer WSL 2 si nécessaire
wsl --install
```

### Port déjà utilisé
```powershell
# Trouver le processus
netstat -ano | findstr :8000

# Arrêter le processus (remplacer PID)
taskkill /PID <PID> /F
```

### Erreur ANTHROPIC_API_KEY
1. Vérifier que `.env` contient la clé
2. Vérifier qu'il n'y a pas d'espaces autour du `=`
3. Rebuild: `docker compose up -d --build`

---

## 📂 Structure dans VS

```
C:\Users\Mario\Documents\2025\Projets de développement Agentique\VoiceX5\
│
├── 📄 README.md
├── 📄 docker-compose.yml
├── 📄 Dockerfile
├── 📄 requirements.txt
├── 📄 .env                    ← Votre configuration
├── 📄 .env.example
├── 📄 .gitignore
│
├── 📁 src\
│   ├── 📁 agents\
│   │   └── 📄 voice_agent.py      ← Agent principal
│   ├── 📁 audio\
│   │   └── 📄 fastrtc_handler.py  ← Streaming audio
│   ├── 📁 knowledge\
│   │   ├── 📄 neo4j_tools.py      ← SafetyGraph
│   │   └── 📄 superlinked_tools.py← Vector search
│   └── 📁 api\
│       └── 📄 main.py             ← FastAPI app
│
├── 📁 scripts\
│   ├── 📄 start.ps1               ← Script Windows
│   └── 📄 neo4j-init.cypher       ← Schema DB
│
└── 📁 config\
```

---

## 🎯 Prochaines étapes

1. ✅ Setup local fonctionnel
2. ⬜ Configurer Twilio pour vrais appels
3. ⬜ Charger données CNESST dans Qdrant
4. ⬜ Déployer sur Azure/Runpod
5. ⬜ Pilote site industriel

---

**Questions?** Ouvrez une issue sur GitHub ou contactez l'équipe Preventera.
