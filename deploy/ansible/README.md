# DFIR-IRIS Ansible Deployment

Automated deployment of DFIR-IRIS using Ansible for traditional infrastructure management.

## 🚀 Quick Start

Deploy DFIR-IRIS to your infrastructure with a single command:

```bash
ansible-playbook deploy/ansible/playbooks/site.yml --ask-vault-pass
```

## 📋 Prerequisites

### Control Node (Your Machine)
- Ansible Core 2.9+
- Python 3.6+ with pip  
- SSH key access to target servers

### Target Servers
- **OS**: Ubuntu 18.04+, CentOS 7+, or RHEL 7+
- **Resources**: 4GB+ RAM, 2+ CPU cores, 20GB+ disk
- **Access**: SSH access with sudo privileges
- **Network**: Open ports 80, 443, 5432

## 🏗️ Architecture

This Ansible deployment:
- Installs Docker and Docker Compose
- Clones the DFIR-IRIS repository
- Configures environment variables
- Launches DFIR-IRIS containers
- Sets up SSL certificates
- Configures system services

## ⚙️ Configuration

### 1. Inventory Setup

Edit `inventory/hosts.yml`:

```yaml
all:
  children:
    iris_servers:
      hosts:
        iris-prod:
          ansible_host: 192.168.1.100
          ansible_user: ubuntu
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
```

### 2. Variables Configuration

**Global settings** (`inventory/group_vars/all.yml`):
```yaml
iris_base_path: /opt/iris
iris_https_port: 443
docker_compose_version: "2.20.0"
project_version: "v2.4.12"
```

**IRIS-specific** (`inventory/group_vars/iris_servers.yml`):
```yaml
iris_server_name: iris.example.com
postgres_user: iris
postgres_admin_user: postgres
iris_authentication_type: local
```

### 3. Secrets Management

Create and encrypt sensitive data:

```bash
# Create secrets file
cp vars/secrets.yml.example vars/secrets.yml

# Edit with your values
nano vars/secrets.yml

# Encrypt the file
ansible-vault encrypt vars/secrets.yml
```

Example `vars/secrets.yml`:
```yaml
# Database passwords
postgres_password: "your-secure-db-password"
postgres_admin_password: "your-admin-password"

# IRIS configuration
iris_secret_key: "your-secret-key"
iris_security_password_salt: "your-salt"

# Admin credentials
iris_adm_username: admin
iris_adm_password: "your-admin-password"
iris_adm_email: admin@example.com
```

## 🎯 Deployment Options

### Full Deployment
```bash
ansible-playbook deploy/ansible/playbooks/site.yml --ask-vault-pass
```

### Selective Deployment
```bash
# Install only Docker
ansible-playbook deploy/ansible/playbooks/site.yml --tags="docker" --ask-vault-pass

# Deploy only IRIS application
ansible-playbook deploy/ansible/playbooks/site.yml --tags="iris-app" --ask-vault-pass

# Update configuration only
ansible-playbook deploy/ansible/playbooks/site.yml --tags="config" --ask-vault-pass
```

### Test Connectivity
```bash
ansible all -m ping -i deploy/ansible/inventory/hosts.yml
```

## 📁 Directory Structure

```
deploy/ansible/
├── ansible.cfg              # Ansible configuration
├── inventory/               # Infrastructure definition
│   ├── hosts.yml           # Server inventory
│   └── group_vars/
│       ├── all.yml         # Global variables
│       └── iris_servers.yml # IRIS-specific variables
├── playbooks/
│   ├── site.yml            # Main deployment playbook
│   ├── setup-docker.yml    # Docker installation only
│   └── deploy-iris.yml     # IRIS deployment only
├── roles/
│   ├── common/             # System preparation
│   ├── docker/             # Docker installation
│   └── iris-app/          # IRIS application deployment
├── vars/
│   └── secrets.yml         # Encrypted sensitive variables
├── templates/              # Configuration templates
└── files/                  # Static files
```

## 🏷️ Available Tags

Use tags for targeted deployments:

| Tag | Description |
|-----|-------------|
| `system` | System setup and package installation |
| `docker` | Docker and Docker Compose installation |
| `iris-app` | IRIS application deployment |
| `config` | Configuration files and environment |
| `certificates` | SSL certificate generation |
| `services` | System service configuration |

## 🔐 Security Features

### SSL/TLS
- Automatic self-signed certificate generation
- Production certificate support
- NGINX reverse proxy with SSL termination

### Secrets Management
- Ansible Vault encryption for sensitive data
- Secure environment variable injection
- Database credential rotation support

### System Security
- Firewall configuration
- Service hardening
- User permission management

## 🐳 Docker Services

The deployment creates these services:

| Service | Description | Port |
|---------|-------------|------|
| `app` | IRIS web application | 8000 |
| `db` | PostgreSQL database | 5432 |
| `rabbitmq` | Message broker | 5672/15672 |
| `worker` | Background task processor | - |
| `nginx` | Reverse proxy + SSL | 80/443 |

## 🔍 Troubleshooting

### Service Status
```bash
# Check IRIS system service
sudo systemctl status iris

# Check Docker containers
docker-compose -f /opt/iris/iris-web/docker-compose.yml ps
```

### View Logs
```bash
# IRIS application logs
docker-compose -f /opt/iris/iris-web/docker-compose.yml logs app

# All service logs
docker-compose -f /opt/iris/iris-web/docker-compose.yml logs
```

### Common Issues

**Connection Refused (Port 443)**:
```bash
# Check if NGINX is running
docker-compose ps nginx
sudo netstat -tlnp | grep :443
```

**Database Connection Failed**:
```bash
# Test database connectivity
docker exec -it iris-web_db psql -U postgres -d iris_db -c "SELECT version();"
```

**Permission Denied**:
```bash
# Verify SSH access
ssh -i ~/.ssh/id_rsa user@your-server
sudo -l  # Check sudo privileges
```

## 📊 Monitoring & Health Checks

### Application Health
```bash
# Test web interface
curl -k https://your-server-ip

# API health check
curl -k https://your-server-ip/manage/health
```

### Database Health
```bash
# Database connection test
docker exec iris-web_db pg_isready -U postgres
```

## 🔄 Updates & Maintenance

### Update IRIS Version
1. Update `project_version` in `inventory/group_vars/all.yml`
2. Run deployment: `ansible-playbook deploy/ansible/playbooks/site.yml --ask-vault-pass`

### Backup Database
```bash
# Create backup
docker exec iris-web_db pg_dump -U postgres iris_db > iris_backup_$(date +%Y%m%d).sql

# Restore backup (if needed)
docker exec -i iris-web_db psql -U postgres iris_db < iris_backup.sql
```

### Certificate Renewal
```bash
# Regenerate self-signed certificates
ansible-playbook deploy/ansible/playbooks/site.yml --tags="certificates" --ask-vault-pass
```

## 🆚 Deployment Comparison

| Method | Use Case | Complexity | Scalability |
|--------|----------|------------|-------------|
| **Ansible** | Traditional VMs, existing Ansible infrastructure | Medium | High |
| **Docker Compose** | Single server, development | Low | Low |
| **Kubernetes** | Container orchestration, cloud-native | High | Very High |

## 🤝 Contributing

To improve this Ansible deployment:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/ansible-improvement`
3. Test your changes
4. Submit a pull request

## 📝 License

This Ansible deployment follows the same license as DFIR-IRIS. See [LICENSE.txt](../../LICENSE.txt) for details.

## 🆘 Support

- **Documentation**: [DFIR-IRIS Docs](https://docs.dfir-iris.org/)
- **Issues**: [GitHub Issues](https://github.com/dfir-iris/iris-web/issues)
- **Community**: [DFIR-IRIS Discord](https://discord.gg/76DUSsKfBt)
