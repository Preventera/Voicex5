#!/bin/bash

# ============================================================
# VoiceX5 - Quick Start Script
# Agents Vocaux SST Intelligents
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${PURPLE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   🎙️  VOICEX5 - Quick Start                                 ║"
echo "║                                                              ║"
echo "║   Agents Vocaux SST Intelligents                             ║"
echo "║   Propulsé par EDGY-AgenticX5                                ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${CYAN}📋 Vérification des prérequis...${NC}"

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker n'est pas installé${NC}"
    echo "   Installez Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✅ Docker trouvé${NC}"

# Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose n'est pas installé${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose trouvé${NC}"

# Check .env
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Fichier .env non trouvé${NC}"
    echo -e "${CYAN}   Création depuis .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   ⚠️  Éditez .env et ajoutez votre ANTHROPIC_API_KEY${NC}"
    echo ""
    read -p "   Appuyez sur Entrée après avoir configuré .env..."
fi
echo -e "${GREEN}✅ Fichier .env trouvé${NC}"

# Check ANTHROPIC_API_KEY
source .env
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" == "sk-ant-api03-VOTRE_CLE_ICI" ]; then
    echo -e "${RED}❌ ANTHROPIC_API_KEY non configurée dans .env${NC}"
    echo "   Obtenez une clé sur: https://console.anthropic.com/"
    exit 1
fi
echo -e "${GREEN}✅ ANTHROPIC_API_KEY configurée${NC}"

echo ""
echo -e "${CYAN}🚀 Démarrage des services VoiceX5...${NC}"
echo ""

# Determine compose command
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Start services
echo -e "${BLUE}📦 Téléchargement des images Docker...${NC}"
$COMPOSE_CMD pull

echo ""
echo -e "${BLUE}🏗️  Construction de l'image VoiceX5...${NC}"
$COMPOSE_CMD build

echo ""
echo -e "${BLUE}🚀 Démarrage des services...${NC}"
$COMPOSE_CMD up -d

# Wait for services
echo ""
echo -e "${CYAN}⏳ Attente du démarrage des services...${NC}"
sleep 10

# Check health
echo ""
echo -e "${CYAN}🔍 Vérification de l'état des services...${NC}"

# Neo4j
if curl -s http://localhost:7474 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Neo4j: http://localhost:7474${NC}"
else
    echo -e "${YELLOW}⏳ Neo4j en cours de démarrage...${NC}"
fi

# Qdrant
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant: http://localhost:6333${NC}"
else
    echo -e "${YELLOW}⏳ Qdrant en cours de démarrage...${NC}"
fi

# VoiceX5 API
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ VoiceX5 API: http://localhost:8000${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "${YELLOW}⏳ VoiceX5 API en cours de démarrage... ($RETRY_COUNT/$MAX_RETRIES)${NC}"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ VoiceX5 API n'a pas démarré${NC}"
    echo "   Vérifiez les logs: docker logs voicex5-api"
fi

echo ""
echo -e "${PURPLE}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🎉 VoiceX5 est prêt!${NC}"
echo ""
echo -e "${CYAN}📡 Points d'accès:${NC}"
echo -e "   🌐 API:          ${BLUE}http://localhost:8000${NC}"
echo -e "   📚 Documentation: ${BLUE}http://localhost:8000/docs${NC}"
echo -e "   🎤 WebSocket:     ${BLUE}ws://localhost:8000/ws/audio${NC}"
echo -e "   📊 Neo4j Browser: ${BLUE}http://localhost:7474${NC}"
echo ""
echo -e "${CYAN}📝 Commandes utiles:${NC}"
echo -e "   Logs:      ${YELLOW}docker logs -f voicex5-api${NC}"
echo -e "   Stop:      ${YELLOW}docker compose down${NC}"
echo -e "   Restart:   ${YELLOW}docker compose restart${NC}"
echo ""
echo -e "${CYAN}🧪 Test rapide:${NC}"
echo -e "   ${YELLOW}curl -X POST http://localhost:8000/api/v1/message \\${NC}"
echo -e "   ${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
echo -e "   ${YELLOW}  -d '{\"message\": \"Il y a un déversement chimique en zone B\"}'"${NC}
echo ""
echo -e "${PURPLE}══════════════════════════════════════════════════════════════${NC}"
