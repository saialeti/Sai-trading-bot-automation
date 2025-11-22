#!/bin/bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_header() {
  echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
  print_header "Checking Prerequisites"
  
  if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
  fi
  print_success "Docker is installed"
  
  if ! command -v minikube &> /dev/null; then
    print_error "Minikube is not installed"
    exit 1
  fi
  print_success "Minikube is installed"
  
  if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed"
    exit 1
  fi
  print_success "kubectl is installed"
}

# Build Docker image
build_image() {
  print_header "Building Docker Image"
  docker build -t webhook-server:latest .
  print_success "Docker image built successfully"
}

# Start minikube
start_minikube() {
  print_header "Starting Minikube"
  
  if minikube status | grep -q "Running"; then
    print_success "Minikube is already running"
  else
    minikube start
    print_success "Minikube started"
  fi
}

# Load image to minikube
load_image() {
  print_header "Loading Image to Minikube"
  minikube image load webhook-server:latest
  print_success "Image loaded to minikube"
}

# Deploy to Kubernetes
deploy() {
  print_header "Deploying to Kubernetes"
  
  kubectl apply -f k8s/configmap.yaml
  print_success "ConfigMap created"
  
  kubectl apply -f k8s/secret.yaml
  print_success "Secret created"
  
  kubectl apply -f k8s/deployment.yaml
  print_success "Deployment created"
  
  kubectl apply -f k8s/service.yaml
  print_success "Service created"
  
  print_warning "Waiting for pods to be ready..."
  kubectl wait --for=condition=ready pod -l app=webhook-server --timeout=300s
  print_success "All pods are ready"
}

# Check status
check_status() {
  print_header "Checking Deployment Status"
  
  echo -e "\n${BLUE}Deployment:${NC}"
  kubectl get deployment webhook-server
  
  echo -e "\n${BLUE}Pods:${NC}"
  kubectl get pods -l app=webhook-server
  
  echo -e "\n${BLUE}Service:${NC}"
  kubectl get svc webhook-server
  
  echo -e "\n${BLUE}ConfigMap:${NC}"
  kubectl get configmap webhook-server-config
  
  echo -e "\n${BLUE}Secret:${NC}"
  kubectl get secret webhook-server-secrets
}

# View logs
view_logs() {
  print_header "Viewing Logs"
  kubectl logs -l app=webhook-server --all-containers=true -f
}

# Port forward
port_forward() {
  print_header "Port Forwarding"
  print_warning "Forwarding port 3001 to localhost:3001"
  kubectl port-forward svc/webhook-server 3001:80
}

# Test webhook
test_webhook() {
  print_header "Testing Webhook"
  
  echo -e "\n${BLUE}Testing health endpoints:${NC}"
  curl -s http://localhost:3001/health/live
  echo ""
  curl -s http://localhost:3001/health/ready
  echo ""
  
  echo -e "\n${BLUE}Testing main endpoint:${NC}"
  curl -s http://localhost:3001
  echo ""
  
  echo -e "\n${BLUE}Testing webhook endpoint:${NC}"
  curl -s -X POST http://localhost:3001/webhook \
    -H "Content-Type: application/json" \
    -d '{"signal": "TEST", "symbol": "EURUSD"}' | head -c 100
  echo ""
}

# Clean up
cleanup() {
  print_header "Cleaning Up"
  kubectl delete -f k8s/
  print_success "All resources deleted"
}

# Full setup
full_setup() {
  check_prerequisites
  build_image
  start_minikube
  load_image
  deploy
  check_status
  print_success "Full setup completed!"
}

# Help message
show_help() {
  cat << 'HELPEOF'

Webhook Server Deployment Script

Usage: ./deploy.sh [COMMAND]

Commands:
  help              Show this help message
  check             Check prerequisites
  build             Build Docker image
  start-minikube    Start minikube
  load-image        Load image to minikube
  deploy            Deploy to Kubernetes
  status            Check deployment status
  logs              View logs
  forward           Port forward (3001:80)
  test              Test webhook endpoint
  cleanup           Delete all resources
  full-setup        Complete setup from scratch (build → load → deploy)

Examples:
  ./deploy.sh full-setup     # Complete setup
  ./deploy.sh deploy         # Only deploy
  ./deploy.sh logs           # View logs
  ./deploy.sh test           # Test webhook

HELPEOF
}

# Main
case "${1:-help}" in
  help)
    show_help
    ;;
  check)
    check_prerequisites
    ;;
  build)
    build_image
    ;;
  start-minikube)
    start_minikube
    ;;
  load-image)
    load_image
    ;;
  deploy)
    deploy
    ;;
  status)
    check_status
    ;;
  logs)
    view_logs
    ;;
  forward)
    port_forward
    ;;
  test)
    test_webhook
    ;;
  cleanup)
    cleanup
    ;;
  full-setup)
    full_setup
    ;;
  *)
    print_error "Unknown command: $1"
    show_help
    exit 1
    ;;
esac
