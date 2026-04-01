# Production Deployment Guide

Best practices and recommendations for deploying these PHP containers in production environments.

## Resource Limits

### Recommended Limits

#### Base PHP Runtime

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

**Rationale**:
- PHP-FPM with 10 max children
- Each process ~30-50MB base memory
- OPcache: 512MB (shared across processes)
- Request memory accommodates ~5-8 concurrent PHP-FPM processes
- Limit allows burst to full pool

#### Toolbox Variant

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

**Rationale**:
- Additional development tools (git, deployer, rclone)
- Xdebug overhead when enabled (~30% more memory)
- Composer operations may require more memory

#### Node.js Variants

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

**Rationale**:
- Node.js heap typically 128-512MB
- npm/build operations memory-intensive
- Combined PHP + Node.js workloads

### PHP-FPM Tuning Based on Memory

Adjust PHP-FPM pool settings based on allocated memory:

**256-512MB Container**:
```ini
pm.max_children = 5
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
```

**512MB-1GB Container**:
```ini
pm.max_children = 10  # Default
pm.start_servers = 2
pm.min_spare_servers = 2
pm.max_spare_servers = 5
```

**1GB+ Container**:
```ini
pm.max_children = 20
pm.start_servers = 5
pm.min_spare_servers = 3
pm.max_spare_servers = 8
```

Override via custom config:
```dockerfile
FROM wilmadigital/php:8.5.3
COPY php-fpm.conf /usr/local/etc/php-fpm.d/zz-custom.conf
```

## Health Checks

### Docker Compose

```yaml
services:
  php:
    image: wilmadigital/php:8.5.3
    healthcheck:
      test: ["CMD", "pgrep", "-f", "php-fpm: master process"]
      interval: 30s
      timeout: 3s
      start_period: 40s
      retries: 3
```

### Kubernetes

```yaml
livenessProbe:
  exec:
    command:
      - pgrep
      - -f
      - "php-fpm: master process"
  initialDelaySeconds: 40
  periodSeconds: 30
  timeoutSeconds: 3
  failureThreshold: 3

readinessProbe:
  exec:
    command:
      - pgrep
      - -f
      - "php-fpm: master process"
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

## Security

### Non-Root User

All images run as `www-data` (UID 33) by default. No additional configuration needed.

### Read-Only Root Filesystem

For enhanced security, mount root filesystem as read-only:

```yaml
services:
  php:
    image: wilmadigital/php:8.5.3
    read_only: true
    tmpfs:
      - /tmp:mode=1777,size=512M,uid=33,gid=33
      - /var/run:mode=755,size=64M,uid=33,gid=33
      - /usr/local/var/log:mode=755,size=128M,uid=33,gid=33
```

**Note**: Ensure application doesn't write to other paths outside /var/www/html.

### Security Context (Kubernetes)

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 33
  runAsGroup: 33
  fsGroup: 33
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  seccompProfile:
    type: RuntimeDefault
```

## Networking

### PHP-FPM Configuration

- **Port**: 9000 (FastCGI)
- **Protocol**: FastCGI (not HTTP)
- **Status Endpoint**: `/status` (for monitoring)

### Nginx Integration

```nginx
location ~ \.php$ {
    fastcgi_pass php:9000;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    include fastcgi_params;
}
```

### Traefik Integration

```yaml
services:
  php:
    image: wilmadigital/php:8.5.3
    labels:
      - "traefik.enable=true"
      - "traefik.http.services.php.loadbalancer.server.port=9000"
```

## Monitoring

### Metrics Collection

PHP-FPM exposes status page on `/status`:

```nginx
location /php-fpm-status {
    access_log off;
    allow 127.0.0.1;
    deny all;
    fastcgi_pass php:9000;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    include fastcgi_params;
}
```

**Available metrics**:
- Pool name
- Process manager type
- Start time
- Active/idle/total processes
- Max active processes
- Slow requests

### Prometheus Integration

Use [php-fpm_exporter](https://github.com/hipages/php-fpm_exporter) to expose metrics:

```yaml
services:
  php-fpm-exporter:
    image: hipages/php-fpm_exporter
    environment:
      - PHP_FPM_SCRAPE_URI=tcp://php:9000/status
    ports:
      - "9253:9253"
```

## Storage

### Volume Mounts

**Application code** (read-only in production):
```yaml
volumes:
  - ./app:/var/www/html:ro
```

**Generated assets** (writable):
```yaml
volumes:
  - ./app:/var/www/html:ro
  - ./app/var:/var/www/html/var:rw
  - ./app/pub/media:/var/www/html/pub/media:rw
  - ./app/pub/static:/var/www/html/pub/static:rw
```

### Persistent Storage

For Magento/OpenMage installations:

```yaml
volumes:
  media:
    driver: local
  var:
    driver: local

services:
  php:
    volumes:
      - media:/var/www/html/pub/media
      - var:/var/www/html/var
```

**Production**: Use external storage (S3, NFS, etc.) for media files.

## Caching

### OPcache Configuration

Default: 512MB OPcache, 65406 max files.

**Monitor OPcache**:
```php
<?php
print_r(opcache_get_status());
```

**Increase for large applications**:
```dockerfile
FROM wilmadigital/php:8.5.3
RUN echo "opcache.memory_consumption = 1024" > /usr/local/etc/php/conf.d/opcache-custom.ini
```

### External Caching

**Redis** (recommended for session/cache):
```yaml
services:
  php:
    image: wilmadigital/php:8.5.3
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

## Environment Variables

### PHP Configuration

Override via environment variables:

```yaml
services:
  php:
    environment:
      - PHP_MEMORY_LIMIT=512M
      - PHP_MAX_EXECUTION_TIME=300
      - PHP_MAX_INPUT_VARS=10000
      - PHP_UPLOAD_MAX_FILESIZE=10M
      - PHP_POST_MAX_SIZE=10M
```

**Note**: Requires custom entrypoint script to process these variables.

### Application Settings

```yaml
services:
  php:
    environment:
      - APP_ENV=production
      - DATABASE_URL=mysql://user:pass@db:3306/dbname
      - REDIS_URL=redis://redis:6379
      - MAGE_MODE=production
```

## Scaling

### Horizontal Scaling

PHP-FPM is stateless - scale horizontally without session affinity:

**Docker Compose**:
```bash
docker-compose up --scale php=3
```

**Kubernetes**:
```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

### Vertical Scaling

Increase resources and adjust PHP-FPM pool:

1. Increase memory limit
2. Increase `pm.max_children`
3. Monitor `pm.status_path` for pool saturation

**Formula**:
```
max_children = (available_memory - opcache_memory - buffer) / process_memory
max_children = (1024MB - 512MB - 256MB) / 40MB = 6-7 processes
```

## Logging

### Centralized Logging

**Docker Compose** (Loki):
```yaml
services:
  php:
    logging:
      driver: loki
      options:
        loki-url: "http://loki:3100/loki/api/v1/push"
        loki-retries: "5"
        loki-batch-size: "400"
```

**Kubernetes** (FluentBit):
```yaml
annotations:
  fluentbit.io/parser: php-fpm
```

### Log Rotation

PHP-FPM logs to STDOUT/STDERR by default - rotation handled by container runtime.

## Updates and Rollbacks

### Zero-Downtime Updates

**Kubernetes Rolling Update**:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

**Docker Compose**:
```bash
docker-compose pull php
docker-compose up -d --no-deps php
```

### Version Pinning

**Pin to patch version** (recommended):
```yaml
services:
  php:
    image: wilmadigital/php:8.5.3
```

**Pin to minor version** (receives patch updates):
```yaml
services:
  php:
    image: wilmadigital/php:8.5.3  # Update manually when 8.5.4 released
```

### Rollback Strategy

Keep previous image version for quick rollback:

```bash
# Tag current production version
docker tag wilmadigital/php:8.5.3 myapp/php:production

# Update to new version
docker-compose pull php
docker-compose up -d

# Rollback if needed
docker tag myapp/php:production wilmadigital/php:current
docker-compose up -d
```

## Performance Tuning

### PHP-FPM Process Manager

**Dynamic** (default, best for variable load):
```ini
pm = dynamic
pm.max_children = 10
pm.start_servers = 2
pm.min_spare_servers = 2
pm.max_spare_servers = 5
```

**OnDemand** (for sporadic traffic):
```ini
pm = ondemand
pm.max_children = 10
pm.process_idle_timeout = 10s
```

**Static** (for consistent high load):
```ini
pm = static
pm.max_children = 10
```

### OPcache Preloading (PHP 7.4+)

```dockerfile
FROM wilmadigital/php:8.5.3
RUN echo "opcache.preload=/var/www/html/preload.php" >> /usr/local/etc/php/conf.d/opcache-preload.ini
RUN echo "opcache.preload_user=www-data" >> /usr/local/etc/php/conf.d/opcache-preload.ini
```

## Troubleshooting

### High Memory Usage

1. Check OPcache size: `opcache_get_status()`
2. Monitor PHP-FPM pool: `/status?full`
3. Adjust `pm.max_children`
4. Check for memory leaks in application code

### Slow Responses

1. Enable slow log:
   ```ini
   slowlog = /proc/self/fd/2
   request_slowlog_timeout = 5s
   ```
2. Check PHP-FPM queue: `/status`
3. Profile with xdebug (toolbox variant)

### Container Restarts

1. Check OOM kills: `docker inspect <container> | grep OOMKilled`
2. Review health check logs
3. Check PHP-FPM error log

## Compliance

### SBOM (Software Bill of Materials)

SBOM artifacts generated for all images:
- Format: SPDX JSON
- Available in GitHub Actions artifacts
- Retention: 90 days

Download SBOM:
```bash
gh run download <run-id> -n sbom-php-8.5.3
```

### Vulnerability Scanning

- **Trivy**: CRITICAL/HIGH vulnerabilities reported to GitHub Security
- **Dependency Review**: Automatic scanning on PRs
- **SARIF**: Results uploaded to GitHub Code Scanning

### License Compliance

Deny-listed licenses (will fail PR):
- GPL-3.0
- AGPL-3.0

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/wilma-digital/docker-php/issues
- Documentation: README.md, CLAUDE.md
- Docker Hub: https://hub.docker.com/r/wilmadigital/php
