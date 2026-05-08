# MetroStack Production Deployment Guide

Complete guide for deploying MetroStack to production environments.

---

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │  (nginx/Traefik)│
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐          ┌────────▼────────┐
     │  Frontend       │          │  Backend API    │
     │  (Static Files) │          │  (FastAPI)      │
     │  Port 80/443    │          │  Port 8000      │
     └─────────────────┘          └────────┬────────┘
                                           │
                                  ┌────────┴────────┐
                                  │                 │
                         ┌────────▼─────┐  ┌───────▼──────┐
                         │ PostgreSQL   │  │    Redis     │
                         │ + PostGIS    │  │ (Task Queue) │
                         └──────────────┘  └──────────────┘
```

---

## Option 1: Docker Swarm / Compose (Easiest)

### Prerequisites
- Docker 20.10+
- 16 GB RAM minimum
- 100 GB disk space
- SSL certificate (Let's Encrypt recommended)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/metrostack.git
cd metrostack
```

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with production values
```

**Critical settings:**
```bash
ENVIRONMENT=production
DEBUG=false
POSTGRES_PASSWORD=<strong-random-password>
CORS_ORIGINS='["https://metrostack.yourcompany.com"]'
```

### 3. Build Images

```bash
# Backend
cd backend
docker build -t metrostack-api:latest .

# Frontend (with production API URL)
cd ../frontend
VITE_API_URL=https://api.yourcompany.com npm run build
docker build -t metrostack-frontend:latest .
```

### 4. Deploy with Docker Compose

```yaml
# production-compose.yml
version: '3.8'

services:
  db:
    image: postgis/postgis:15-3.4
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: metrostack
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

  api:
    image: metrostack-api:latest
    environment:
      POSTGRES_HOST: db
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: production
    volumes:
      - upload_data:/app/uploads
    depends_on:
      - db
      - redis
    restart: always

  frontend:
    image: metrostack-frontend:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: always

volumes:
  postgres_data:
  upload_data:
```

```bash
docker-compose -f production-compose.yml up -d
```

---

## Option 2: Kubernetes (Enterprise)

### Prerequisites
- Kubernetes 1.24+
- kubectl configured
- Helm 3.0+
- Persistent storage class

### 1. Create Namespace

```bash
kubectl create namespace metrostack
```

### 2. Deploy PostgreSQL

```bash
helm install metrostack-db bitnami/postgresql \
  --namespace metrostack \
  --set auth.postgresPassword=your-password \
  --set primary.persistence.size=100Gi \
  --set image.tag=15.0.0-debian-11-r14
```

### 3. Apply Manifests

```yaml
# k8s/backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrostack-api
  namespace: metrostack
spec:
  replicas: 3
  selector:
    matchLabels:
      app: metrostack-api
  template:
    metadata:
      labels:
        app: metrostack-api
    spec:
      containers:
      - name: api
        image: metrostack-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          value: metrostack-db-postgresql
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: metrostack-secrets
              key: postgres-password
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
---
apiVersion: v1
kind: Service
metadata:
  name: metrostack-api
  namespace: metrostack
spec:
  selector:
    app: metrostack-api
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

---

## Option 3: Cloud-Native (AWS / GCP / Azure)

### AWS Architecture

```
┌──────────────────────────────────────────────────────┐
│                    CloudFront CDN                    │
│              (Frontend Static Files)                 │
└──────────────┬───────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│              Application Load Balancer               │
└──────────────┬───────────────────────────────────────┘
               │
     ┌─────────┴─────────┐
     │                   │
┌────▼─────┐      ┌──────▼──────┐
│  ECS/EKS │      │  Lambda     │
│  Backend │      │  (Workers)  │
└────┬─────┘      └─────────────┘
     │
┌────▼──────────────────┐
│  RDS PostgreSQL       │
│  (PostGIS extension)  │
└───────────────────────┘
```

### Terraform Setup

```hcl
# terraform/main.tf
provider "aws" {
  region = "us-west-2"
}

# RDS PostgreSQL
resource "aws_db_instance" "metrostack" {
  identifier        = "metrostack-db"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = "db.t3.large"
  allocated_storage = 100
  storage_encrypted = true
  
  db_name  = "metrostack"
  username = "postgres"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.metrostack.name
  
  backup_retention_period = 7
  skip_final_snapshot     = false
}

# ECS Cluster
resource "aws_ecs_cluster" "metrostack" {
  name = "metrostack-cluster"
}

# ECS Task Definition (Backend)
resource "aws_ecs_task_definition" "api" {
  family                   = "metrostack-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048"
  memory                   = "4096"

  container_definitions = jsonencode([{
    name  = "api"
    image = "your-ecr-repo/metrostack-api:latest"
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "POSTGRES_HOST", value = aws_db_instance.metrostack.endpoint },
      { name = "ENVIRONMENT", value = "production" }
    ]
  }])
}

# S3 + CloudFront for frontend
resource "aws_s3_bucket" "frontend" {
  bucket = "metrostack-frontend"
}

resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id   = "S3-metrostack-frontend"
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-metrostack-frontend"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  viewer_certificate {
    acm_certificate_arn = var.ssl_certificate_arn
    ssl_support_method  = "sni-only"
  }
}
```

Deploy:
```bash
cd terraform
terraform init
terraform apply
```

---

## SSL/TLS Configuration

### Let's Encrypt (Recommended)

```bash
# Install Certbot
apt-get install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d metrostack.yourcompany.com

# Auto-renewal (cron)
echo "0 0,12 * * * root certbot renew --quiet" >> /etc/crontab
```

### Manual Certificate

```nginx
# /etc/nginx/sites-available/metrostack
server {
    listen 443 ssl http2;
    server_name metrostack.yourcompany.com;

    ssl_certificate /etc/ssl/certs/metrostack.crt;
    ssl_certificate_key /etc/ssl/private/metrostack.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Database Backups

### Automated Backups

```bash
#!/bin/bash
# /etc/cron.daily/backup-metrostack

BACKUP_DIR=/backups/metrostack
DATE=$(date +%Y%m%d_%H%M%S)

# Dump database
docker exec metrostack_db pg_dump -U postgres metrostack \
  | gzip > $BACKUP_DIR/metrostack_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/metrostack_$DATE.sql.gz \
  s3://your-bucket/metrostack-backups/

# Keep last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Restore from Backup

```bash
gunzip < backup.sql.gz | docker exec -i metrostack_db \
  psql -U postgres metrostack
```

---

## Monitoring & Logging

### Prometheus + Grafana

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'metrostack-api'
    static_configs:
      - targets: ['localhost:8000']
```

```bash
docker run -d -p 9090:9090 \
  -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

docker run -d -p 3001:3000 grafana/grafana
```

### ELK Stack (Logs)

```yaml
# filebeat.yml
filebeat.inputs:
- type: container
  paths:
    - '/var/lib/docker/containers/*/*.log'

output.elasticsearch:
  hosts: ["localhost:9200"]
```

---

## Performance Tuning

### PostgreSQL

```sql
-- postgresql.conf
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 20MB
min_wal_size = 1GB
max_wal_size = 4GB
```

### FastAPI (Gunicorn)

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --max-requests 1000 \
  --max-requests-jitter 100
```

### Nginx Caching

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 
                 keys_zone=metrostack_cache:10m 
                 max_size=1g inactive=60m;

location /api/projects {
    proxy_cache metrostack_cache;
    proxy_cache_valid 200 5m;
}
```

---

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable HTTPS only (no HTTP)
- [ ] Configure firewall (ufw/iptables)
- [ ] Set up fail2ban for SSH
- [ ] Enable PostgreSQL SSL connections
- [ ] Implement rate limiting (slowapi)
- [ ] Add JWT authentication
- [ ] Scan uploaded files (ClamAV)
- [ ] Regular security updates
- [ ] Database encryption at rest
- [ ] Enable audit logging
- [ ] Restrict CORS to your domain
- [ ] Use secrets management (Vault/AWS Secrets Manager)

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker logs metrostack_api

# Common issues:
# - Database not ready: Wait 30 seconds
# - Migration failed: docker exec metrostack_api alembic upgrade head
# - Port conflict: Change port in docker-compose.yml
```

### Frontend shows blank page

```bash
# Check browser console
# Common issues:
# - Wrong API URL: Check VITE_API_URL
# - CORS error: Add frontend domain to backend CORS_ORIGINS
# - Build failed: npm run build and check for errors
```

### Slow performance

```bash
# Check database connections
docker exec metrostack_db psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check disk I/O
iostat -x 1

# Check memory
free -h
docker stats
```

---

## Support

For production deployment assistance:
- File an issue: https://github.com/yourusername/metrostack/issues
- Email: support@metrostack.io (if commercial support available)

---

**Production deployment requires expertise in:**
- Docker/Kubernetes
- PostgreSQL administration
- SSL/TLS certificates
- Linux system administration
- Network security

Consider hiring a DevOps engineer if this is your first production deployment.
