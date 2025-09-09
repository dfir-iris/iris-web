#!/bin/bash

# DFIR-IRIS Ansible Quick Start Script
# This script helps you get started with deploying DFIR-IRIS using Ansible

set -e

echo "=========================================="
echo "  DFIR-IRIS Ansible Quick Start"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [[ ! -f "ansible.cfg" || ! -d "roles" ]]; then
    print_error "This script must be run from the deploy/ansible directory"
    print_status "Please run: cd deploy/ansible && ./quick-start.sh"
    exit 1
fi

print_status "Checking prerequisites..."

# Check if Ansible is installed
if ! command -v ansible &> /dev/null; then
    print_error "Ansible is not installed. Please install Ansible first:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install ansible"
    echo "  CentOS/RHEL: sudo yum install ansible"
    echo "  macOS: brew install ansible"
    exit 1
fi

# Check Ansible version
ANSIBLE_VERSION=$(ansible --version | head -n1 | cut -d' ' -f2 | cut -d'[' -f1)
print_success "Ansible $ANSIBLE_VERSION found"

# Step 1: Setup inventory
print_status "Step 1: Setting up inventory..."
if [[ ! -f "inventory/hosts.yml" ]]; then
    if [[ -f "inventory/hosts.yml.example" ]]; then
        cp inventory/hosts.yml.example inventory/hosts.yml
        print_success "Created inventory/hosts.yml from example"
        print_warning "Please edit inventory/hosts.yml with your server details"
    else
        print_error "No inventory example found"
        exit 1
    fi
else
    print_success "inventory/hosts.yml already exists"
fi

# Step 2: Setup secrets
print_status "Step 2: Setting up secrets..."
if [[ ! -f "vars/secrets.yml" ]]; then
    if [[ -f "vars/secrets.yml.example" ]]; then
        cp vars/secrets.yml.example vars/secrets.yml
        print_success "Created vars/secrets.yml from example"
        print_warning "Please edit vars/secrets.yml with your secure passwords"
        
        echo ""
        echo "Would you like to encrypt the secrets file now? (y/n)"
        read -r encrypt_response
        if [[ "$encrypt_response" =~ ^[Yy]$ ]]; then
            ansible-vault encrypt vars/secrets.yml
            print_success "Secrets file encrypted with Ansible Vault"
        else
            print_warning "Remember to encrypt your secrets file before deployment:"
            echo "  ansible-vault encrypt vars/secrets.yml"
        fi
    else
        print_error "No secrets example found"
        exit 1
    fi
else
    print_success "vars/secrets.yml already exists"
fi

# Step 3: Test connectivity
print_status "Step 3: Testing connectivity to target servers..."
echo ""
echo "Would you like to test connectivity to your servers now? (y/n)"
read -r test_response
if [[ "$test_response" =~ ^[Yy]$ ]]; then
    if ansible all -m ping -i inventory/hosts.yml; then
        print_success "Connectivity test passed!"
    else
        print_warning "Connectivity test failed. Please check your inventory configuration."
    fi
fi

# Step 4: Deployment options
echo ""
print_status "Step 4: Ready for deployment!"
echo ""
echo "Deployment options:"
echo "  1. Full deployment:"
echo "     ansible-playbook playbooks/site.yml --ask-vault-pass"
echo ""
echo "  2. Test Docker installation only:"
echo "     ansible-playbook playbooks/site.yml --tags='docker' --ask-vault-pass"
echo ""
echo "  3. Deploy IRIS application only:"
echo "     ansible-playbook playbooks/site.yml --tags='iris-app' --ask-vault-pass"
echo ""

echo "Would you like to start the deployment now? (y/n)"
read -r deploy_response
if [[ "$deploy_response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Choose deployment type:"
    echo "  1) Full deployment (recommended for first time)"
    echo "  2) Docker installation only"
    echo "  3) IRIS application only"
    echo -n "Enter choice [1-3]: "
    read -r deploy_choice
    
    case $deploy_choice in
        1)
            print_status "Starting full DFIR-IRIS deployment..."
            ansible-playbook playbooks/site.yml --ask-vault-pass
            ;;
        2)
            print_status "Installing Docker environment..."
            ansible-playbook playbooks/site.yml --tags="docker" --ask-vault-pass
            ;;
        3)
            print_status "Deploying IRIS application..."
            ansible-playbook playbooks/site.yml --tags="iris-app" --ask-vault-pass
            ;;
        *)
            print_warning "Invalid choice. You can run the deployment manually later."
            ;;
    esac
else
    print_success "Setup complete! You can now run the deployment manually."
fi

echo ""
print_success "DFIR-IRIS Ansible setup complete!"
echo ""
echo "Next steps:"
echo "  1. Verify your inventory/hosts.yml configuration"
echo "  2. Update vars/secrets.yml with secure passwords"
echo "  3. Run deployment: ansible-playbook playbooks/site.yml --ask-vault-pass"
echo ""
echo "For more information, see README.md"
echo "=========================================="
