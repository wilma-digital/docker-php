# OpenMage → WilMa Migration Guide

## Übersicht

Migration von OpenMage-Namespace zu WilMa-Namespace für gesamten Docker-Stack.

### Stack-Hierarchie

```
openmage/debian           → wilmadigital/debian
    ↓                        ↓
openmage/php-base         → wilmadigital/php-base
    ↓                        ↓
openmage/php              → wilmadigital/php
```

## Phase 1: Vorbereitung

### 1.1 Inventar

**OpenMage Repos** (zu archivieren):
- [ ] `openmage/docker-debian`
- [ ] `openmage/php-base`
- [ ] `openmage/docker-php`

**WilMa Forks** (zu de-forken):
- [ ] `wilma-digital/docker-debian`
- [ ] `wilma-digital/php-base`
- [ ] `wilma-digital/docker-php`

**Abhängige Projekte** (zu aktualisieren):
- [ ] WilMa GitLab Projects (Liste erstellen)
- [ ] gitlab.com Projects (Liste erstellen)
- [ ] Produktion Server (Liste erstellen)

### 1.2 Docker Hub Setup

1. **Organisation erstellen/verifizieren**
   ```
   https://hub.docker.com/orgs/wilmadigital
   ```

2. **Repositories erstellen**
   - `wilmadigital/debian`
   - `wilmadigital/php-base`
   - `wilmadigital/php`

3. **Access Token generieren**
   ```
   Settings → Security → Access Tokens
   Name: github-actions-wilma
   Scopes: Read, Write, Delete
   ```

4. **Token notieren** → Für GitHub Secrets

### 1.3 GitHub Secrets

Für **jedes** wilma-digital Repo:

```bash
# Settings → Secrets and variables → Actions → New repository secret

DOCKER_HUB_USERNAME=wilmadigital
DOCKER_HUB_ACCESS_TOKEN=dckr_pat_xxxxxxxxxxxxx
```

## Phase 2: OpenMage Archivierung

### 2.1 README Updates

Für jedes OpenMage Repo (`docker-debian`, `php-base`, `docker-php`):

**Deprecation Notice** am Anfang der README.md:

```markdown
# ⚠️ DEPRECATED - This repository has been archived

This project has been moved to [wilma-digital/XXX](https://github.com/wilma-digital/XXX).

**New Docker Hub namespace**: `wilmadigital/XXX`

## Migration

Old images will remain available but will no longer receive updates.

Please update your projects to use the new namespace:

```yaml
# Old
FROM openmage/php:8.5.3

# New
FROM wilmadigital/php:8.5.3
```

For migration assistance, see: https://github.com/wilma-digital/docker-php/blob/main/MIGRATION.md

---

**Original README below:**
```

### 2.2 Repos archivieren

1. Go to Repo Settings
2. Scroll to "Danger Zone"
3. Click "Archive this repository"
4. Confirm

Reihenfolge (bottom-up, damit Links funktionieren):
1. `openmage/docker-php` (zuerst)
2. `openmage/php-base`
3. `openmage/docker-debian` (zuletzt)

## Phase 3: Fork → Main Repo

### Option A: GitHub Support (Empfohlen)

Für jedes Repo:

1. Contact GitHub Support: https://support.github.com/
2. Request: "Convert fork to standalone repository"
3. Provide:
   - Repo URL: `https://github.com/wilma-digital/XXX`
   - Reason: "Original project archived, taking over maintenance"

**Vorteil**: Behält History, Stars, Issues, etc.

### Option B: Manuell (Fallback)

Falls GitHub Support nicht antwortet:

```bash
# Für jedes Repo
REPO_NAME="docker-debian"  # oder php-base, docker-php

# 1. Backup klonen
git clone git@github.com:wilma-digital/$REPO_NAME.git
cd $REPO_NAME

# 2. Neues Repo auf GitHub erstellen (ohne Fork-Checkbox!)
# https://github.com/organizations/wilma-digital/repositories/new

# 3. Remote umbiegen
git remote set-url origin git@github.com:wilma-digital/$REPO_NAME-new.git
git push -u origin main --force

# 4. Altes Repo umbenennen auf GitHub
# wilma-digital/docker-debian → wilma-digital/docker-debian-OLD

# 5. Neues Repo umbenennen
# wilma-digital/docker-debian-new → wilma-digital/docker-debian

# 6. Altes Repo löschen
```

### 3.1 GitHub Actions aktivieren

Für jedes de-forkte Repo:

1. Go to "Actions" Tab
2. Click "I understand my workflows, go ahead and enable them"
3. Verify workflows erscheinen

### 3.2 Branch Protection

Settings → Branches → Add rule for `main`:
- [ ] Require pull request reviews before merging
- [ ] Require status checks to pass (optional)
- [ ] Include administrators (optional)

## Phase 4: Migration Bottom-Up

### 4.1 docker-debian (Base)

```bash
cd /path/to/wilma-digital/docker-debian

# 1. Update namespace in alle Dockerfiles
find . -name "Dockerfile*" -type f -exec sed -i '' 's/openmage\/debian/wilmadigital\/debian/g' {} +

# 2. Update workflows
find .github/workflows -name "*.yml" -exec sed -i '' 's/openmage\/debian/wilmadigital\/debian/g' {} +

# 3. Update README
sed -i '' 's/openmage\/debian/wilmadigital\/debian/g' README.md
sed -i '' 's/openmage\/docker-debian/wilmadigital\/docker-debian/g' README.md

# 4. Commit
git add .
git commit -m "[INFRA] Migrate namespace openmage → wilmadigital"
git push

# 5. Trigger build (GitHub Actions)
# → Verify auf Docker Hub: https://hub.docker.com/r/wilmadigital/debian
```

### 4.2 php-base (Middle Layer)

```bash
cd /path/to/wilma-digital/php-base

# 1. Update FROM statements (debian base)
find . -name "Dockerfile*" -type f -exec sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' {} +
find . -name "Dockerfile*" -type f -exec sed -i '' 's/FROM openmage\/debian/FROM wilmadigital\/debian/g' {} +

# 2. Update workflows
find .github/workflows -name "*.yml" -exec sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' {} +

# 3. Update README
sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' README.md
sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' README.md
sed -i '' 's/openmage\/debian/wilmadigital\/debian/g' README.md

# 4. Commit
git add .
git commit -m "[INFRA] Migrate namespace openmage → wilmadigital"
git push

# 5. Trigger build
# → Verify auf Docker Hub: https://hub.docker.com/r/wilmadigital/php-base
```

### 4.3 docker-php (Top Layer)

Dieses Repo (aktuell):

```bash
cd /Users/amautz/www/03\ RESSOURCEN/INFRA/docker-php

# 1. Update Dockerfile.template
sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' Dockerfile.template

# 2. Update versions.json
sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' versions.json

# 3. Update workflows (auto-generated, aber fix Hardcodes)
find .github/workflows -name "*.yml" -exec sed -i '' 's/openmage\/php/wilmadigital\/php/g' {} +

# 4. Update README & Docs
sed -i '' 's/openmage\/php/wilmadigital\/php/g' README.md
sed -i '' 's/openmage\/php/wilmadigital\/php/g' CLAUDE.md
sed -i '' 's/openmage\/php/wilmadigital\/php/g' SUMMARY.md

# 5. Regenerate Dockerfiles
./generate-dockerfiles.py

# 6. Regenerate workflows
./generate-workflows.py

# 7. Commit
git add .
git commit -m "[INFRA] Migrate namespace openmage → wilmadigital"
git push

# 8. Trigger builds
# → Verify auf Docker Hub: https://hub.docker.com/r/wilmadigital/php
```

## Phase 5: Projekt-Updates

### 5.1 Inventar erstellen

```bash
# Find all docker-compose files
find ~/www -name "docker-compose*.yml" -o -name "Dockerfile" | \
  xargs grep -l "openmage/" > /tmp/openmage-references.txt

# Review
cat /tmp/openmage-references.txt
```

### 5.2 Automated Update

```bash
# Script für alle Files
for file in $(cat /tmp/openmage-references.txt); do
  echo "Updating: $file"

  # Backup
  cp "$file" "$file.bak"

  # Replace
  sed -i '' 's/openmage\/debian/wilmadigital\/debian/g' "$file"
  sed -i '' 's/openmage\/php-base/wilmadigital\/php-base/g' "$file"
  sed -i '' 's/openmage\/php/wilmadigital\/php/g' "$file"

  # Show diff
  diff "$file.bak" "$file" || true
done

# Review changes, then commit per project
```

### 5.3 GitLab CI/CD

Für jedes Projekt mit `.gitlab-ci.yml`:

```yaml
# Update image references
image: wilmadigital/php:8.5.3  # statt openmage/php:8.5.3

services:
  - wilmadigital/php:8.5.3     # statt openmage/php:8.5.3
```

### 5.4 Testing

Pro Projekt:
1. Pull new images: `docker-compose pull`
2. Rebuild: `docker-compose build`
3. Test: `docker-compose up -d`
4. Verify: Check logs, run tests
5. Commit & Deploy

## Phase 6: Cleanup

### 6.1 Old Images

Docker Hub behalten (read-only):
- `openmage/debian:*` → Deprecated, aber verfügbar
- `openmage/php-base:*` → Deprecated, aber verfügbar
- `openmage/php:*` → Deprecated, aber verfügbar

**Kein Force-Pull für User** - alte Images bleiben funktional.

### 6.2 Documentation

Final documentation update:
- [ ] MIGRATION.md in alle 3 Repos kopieren
- [ ] Link in READMEs
- [ ] Blog post (optional)
- [ ] Team informieren

## Timeline

**Geschätzt**: 4-8 Stunden (je nach Anzahl Projekte)

| Phase | Zeit | Blocking |
|-------|------|----------|
| 1. Vorbereitung | 30min | - |
| 2. OpenMage Archivierung | 30min | Phase 3 |
| 3. Fork → Main | 1h | - |
| 4. docker-debian Migration | 30min | Phase 5 |
| 5. php-base Migration | 30min | Phase 5 |
| 6. docker-php Migration | 1h | Phase 5 |
| 7. Projekt-Updates | 2-4h | - |
| 8. Testing & Verification | 1-2h | - |

## Rollback Plan

Falls Probleme auftreten:

```bash
# Images sind auf Docker Hub verfügbar:
docker pull openmage/php:8.5.3  # Alt funktioniert noch

# Revert Git changes:
git revert <commit-hash>
git push

# Update Projekte zurück (umgekehrte Sed-Commands)
```

## Support

Bei Problemen:
1. Check GitHub Actions Logs
2. Check Docker Hub Build Status
3. Test lokal: `docker build -f Dockerfile -t test .`
4. Rollback möglich (alte Images bleiben)

## Checklist

- [ ] Docker Hub wilmadigital/* Organisation setup
- [ ] GitHub Secrets konfiguriert (alle 3 Repos)
- [ ] OpenMage READMEs updated
- [ ] OpenMage Repos archiviert
- [ ] wilma-digital Forks de-forked
- [ ] docker-debian migriert & gebaut
- [ ] php-base migriert & gebaut
- [ ] docker-php migriert & gebaut
- [ ] WilMa Projekte inventory erstellt
- [ ] Projekt docker-compose Files updated
- [ ] Projekt Dockerfiles updated
- [ ] GitLab CI/CD updated
- [ ] Testing durchgeführt
- [ ] Production deployed
- [ ] Team informiert
- [ ] Documentation updated

---

**Erstellt**: 2025-04-01
**Autor**: Andreas Mautz
