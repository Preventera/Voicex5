# ============================================================
# VoiceX5 - Script de démarrage Windows PowerShell
# Agents Vocaux SST Intelligents
# ============================================================

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "║   🎙️  VOICEX5 - Setup Windows                               ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "║   Agents Vocaux SST Intelligents                             ║" -ForegroundColor Magenta
Write-Host "║   Propulsé par EDGY-AgenticX5                                ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

# === Vérification des prérequis ===
Write-Host "📋 Vérification des prérequis..." -ForegroundColor Cyan

# Docker Desktop
$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "❌ Docker Desktop n'est pas installé" -ForegroundColor Red
    Write-Host "   Téléchargez-le sur: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Docker trouvé" -ForegroundColor Green

# Docker running
$dockerRunning = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker Desktop n'est pas démarré" -ForegroundColor Red
    Write-Host "   Lancez Docker Desktop et réessayez" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Docker Desktop actif" -ForegroundColor Green

# Git
$gitInstalled = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitInstalled) {
    Write-Host "❌ Git n'est pas installé" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Git trouvé" -ForegroundColor Green

# === Configuration .env ===
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Fichier .env non trouvé" -ForegroundColor Yellow
    Write-Host "   Création depuis .env.example..." -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "   ⚠️  IMPORTANT: Éditez .env et ajoutez votre ANTHROPIC_API_KEY" -ForegroundColor Yellow
    Write-Host "   Ouvrez .env dans VS Code ou Notepad" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "   Appuyez sur Entrée après avoir configuré .env"
}
Write-Host "✅ Fichier .env trouvé" -ForegroundColor Green

# Vérifier ANTHROPIC_API_KEY
$envContent = Get-Content ".env" -Raw
if ($envContent -match "ANTHROPIC_API_KEY=sk-ant-api03-VOTRE_CLE_ICI" -or $envContent -notmatch "ANTHROPIC_API_KEY=sk-") {
    Write-Host "❌ ANTHROPIC_API_KEY non configurée dans .env" -ForegroundColor Red
    Write-Host "   Obtenez une clé sur: https://console.anthropic.com/" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ ANTHROPIC_API_KEY configurée" -ForegroundColor Green

Write-Host ""
Write-Host "🚀 Démarrage des services VoiceX5..." -ForegroundColor Cyan
Write-Host ""

# === Démarrage Docker Compose ===
Write-Host "📦 Téléchargement des images Docker..." -ForegroundColor Blue
docker compose pull

Write-Host ""
Write-Host "🏗️  Construction de l'image VoiceX5..." -ForegroundColor Blue
docker compose build

Write-Host ""
Write-Host "🚀 Démarrage des services..." -ForegroundColor Blue
docker compose up -d

# === Attente et vérification ===
Write-Host ""
Write-Host "⏳ Attente du démarrage (30 sec)..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "🔍 Vérification des services..." -ForegroundColor Cyan

# Test API
$maxRetries = 10
$retryCount = 0
$apiReady = $false

while ($retryCount -lt $maxRetries -and -not $apiReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $apiReady = $true
        }
    } catch {
        $retryCount++
        Write-Host "   ⏳ VoiceX5 API en cours de démarrage... ($retryCount/$maxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}

Write-Host ""
Write-Host "══════════════════════════════════════════════════════════════" -ForegroundColor Magenta
Write-Host ""

if ($apiReady) {
    Write-Host "🎉 VoiceX5 est prêt!" -ForegroundColor Green
} else {
    Write-Host "⚠️  VoiceX5 prend plus de temps à démarrer" -ForegroundColor Yellow
    Write-Host "   Vérifiez les logs: docker logs voicex5-api" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📡 Points d'accès:" -ForegroundColor Cyan
Write-Host "   🌐 API:           http://localhost:8000" -ForegroundColor White
Write-Host "   📚 Documentation: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   🎤 WebSocket:     ws://localhost:8000/ws/audio" -ForegroundColor White
Write-Host "   📊 Neo4j Browser: http://localhost:7474" -ForegroundColor White
Write-Host ""
Write-Host "📝 Commandes utiles (PowerShell):" -ForegroundColor Cyan
Write-Host "   Logs:    docker logs -f voicex5-api" -ForegroundColor Yellow
Write-Host "   Stop:    docker compose down" -ForegroundColor Yellow
Write-Host "   Restart: docker compose restart" -ForegroundColor Yellow
Write-Host ""
Write-Host "🧪 Test rapide:" -ForegroundColor Cyan
Write-Host '   Invoke-RestMethod -Uri "http://localhost:8000/api/v1/message" -Method Post -ContentType "application/json" -Body ''{"message": "Il y a un déversement chimique en zone B"}''' -ForegroundColor Yellow
Write-Host ""
Write-Host "══════════════════════════════════════════════════════════════" -ForegroundColor Magenta

# Ouvrir le navigateur
Start-Process "http://localhost:8000/docs"
