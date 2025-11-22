#!/bin/bash

################################################################################
# Trading Bot Deployment Script
# Automates the entire deployment process to Minikube
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🚀 TRADING BOT DEPLOYMENT SCRIPT${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"

# Check prerequisites
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"
command -v kubectl >/dev/null 2>&1 || { echo -e "${RED}kubectl not found${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}docker not found${NC}"; exit 1; }
command -v minikube >/dev/null 2>&1 || { echo -e "${RED}minikube not found${NC}"; exit 1; }
echo -e "${GREEN}✓ All prerequisites found${NC}"

# Check if Minikube is running
echo -e "${YELLOW}[2/6] Checking Minikube status...${NC}"
if ! minikube status >/dev/null 2>&1; then
    echo -e "${YELLOW}Starting Minikube...${NC}"
    minikube start --driver=docker
fi
echo -e "${GREEN}✓ Minikube is running${NC}"

# Point Docker to Minikube's Docker daemon
echo -e "${YELLOW}[3/6] Setting up Docker environment...${NC}"
eval $(minikube docker-env)
echo -e "${GREEN}✓ Docker environment configured${NC}"

# Build Docker image
echo -e "${YELLOW}[4/6] Building Docker image...${NC}"
docker build --no-cache -t trading-bot:latest .
echo -e "${GREEN}✓ Docker image built successfully${NC}"

# Apply Kubernetes manifests
echo -e "${YELLOW}[5/6] Applying Kubernetes manifests...${NC}"
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
echo -e "${GREEN}✓ Kubernetes manifests applied${NC}"

# Wait for pod to be ready
echo -e "${YELLOW}[6/6] Waiting for pod to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=trading-bot --timeout=120s
echo -e "${GREEN}✓ Pod is ready${NC}"

# Display status
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"

echo ""
echo -e "${YELLOW}📊 Deployment Status:${NC}"
echo ""

echo "Pods:"
kubectl get pods -l app=trading-bot

echo ""
echo "Services:"
kubectl get svc trading-bot-service

echo ""
echo -e "${YELLOW}🔗 Access Points:${NC}"
echo "Local: $(minikube service trading-bot-service --url)"
echo ""

echo -e "${YELLOW}📝 Available Endpoints:${NC}"
BOT_URL=$(minikube service trading-bot-service --url)
echo "Health Check:    ${BOT_URL}/"
echo "All Trades:      ${BOT_URL}/trades"
echo "Test Connection: ${BOT_URL}/test"
echo ""

echo -e "${YELLOW}📖 Usage:${NC}"
echo "1. Use ngrok to expose to external:"
echo "   ngrok http 192.168.49.2:32378"
echo ""
echo "2. Use ngrok URL in TradingView webhook"
echo ""
echo "3. View logs:"
echo "   kubectl logs -f deployment/trading-bot"
echo ""

echo -e "${GREEN}🎉 Ready for trading signals!${NC}"
