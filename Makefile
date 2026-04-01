.PHONY: help generate test check-updates build-85 build-85-node22 lint clean

help: ## Show this help message
	@echo "Docker PHP Build System - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

generate: ## Regenerate all Dockerfiles and workflows from templates
	@echo "→ Generating Dockerfiles..."
	@./generate-dockerfiles.py
	@echo "→ Generating workflows..."
	@./generate-workflows.py
	@echo "✓ All files regenerated"

test: build-85 ## Run quick test build for PHP 8.5
	@echo "✓ Test build completed"

check-updates: ## Check for new PHP releases
	@echo "→ Checking for PHP updates..."
	@./check-php-releases.py || echo "→ Updates available (exit code 1 = updates found)"

build-85: ## Build PHP 8.5 base image for testing
	@echo "→ Building PHP 8.5 base image..."
	@docker build -f src/8.5/src/Dockerfile -t wilmadigital/php:8.5-test src/8.5/src/

build-85-node22: ## Build PHP 8.5 + Node.js 22 for testing
	@echo "→ Building PHP 8.5 + Node.js 22 image..."
	@docker build -f src/8.5/node22/src/Dockerfile -t wilmadigital/php:8.5-node22-test src/8.5/node22/src/

build-85-toolbox: ## Build PHP 8.5 toolbox image for testing
	@echo "→ Building PHP 8.5 toolbox image..."
	@docker build -f src/8.5/src/Dockerfile --target toolbox -t wilmadigital/php:8.5-toolbox-test src/8.5/src/

lint: ## Lint all base Dockerfiles with hadolint
	@echo "→ Linting Dockerfiles..."
	@for v in 8.1 8.2 8.3 8.4 8.5; do \
		echo "  Checking PHP $$v..."; \
		docker run --rm -i hadolint/hadolint < src/$$v/src/Dockerfile || exit 1; \
	done
	@echo "✓ All Dockerfiles passed linting"

clean: ## Remove test images
	@echo "→ Removing test images..."
	@docker rmi -f wilmadigital/php:8.5-test wilmadigital/php:8.5-node22-test wilmadigital/php:8.5-toolbox-test 2>/dev/null || true
	@echo "✓ Test images removed"

verify: build-85 ## Build and verify PHP 8.5 image
	@echo "→ Verifying PHP 8.5 image..."
	@docker run --rm wilmadigital/php:8.5-test php -v
	@docker run --rm wilmadigital/php:8.5-test php -m | grep -E "redis|imagick|opcache"
	@docker run --rm wilmadigital/php:8.5-test composer --version
	@echo "✓ PHP 8.5 image verified"

verify-node: build-85-node22 ## Build and verify PHP 8.5 + Node.js image
	@echo "→ Verifying PHP 8.5 + Node.js 22 image..."
	@docker run --rm wilmadigital/php:8.5-node22-test php -v
	@docker run --rm wilmadigital/php:8.5-node22-test node -v
	@docker run --rm wilmadigital/php:8.5-node22-test npm -v
	@echo "✓ PHP 8.5 + Node.js 22 image verified"

# Development helpers
dev-shell: build-85 ## Start interactive shell in PHP 8.5 container
	@docker run --rm -it wilmadigital/php:8.5-test bash

dev-shell-node: build-85-node22 ## Start interactive shell in PHP 8.5 + Node.js container
	@docker run --rm -it wilmadigital/php:8.5-node22-test bash

# CI simulation
ci-test: lint verify verify-node ## Run full CI test suite locally
	@echo "✓ All CI tests passed"

# Multi-arch build (requires buildx)
buildx-setup: ## Set up Docker buildx for multi-architecture builds
	@docker buildx create --name php-builder --use 2>/dev/null || true
	@docker buildx inspect php-builder --bootstrap

buildx-85: buildx-setup ## Build and load multi-arch PHP 8.5 image
	@echo "→ Building multi-arch PHP 8.5 image..."
	@cd src/8.5/src && docker buildx build --platform linux/amd64,linux/arm64 --load -t wilmadigital/php:8.5-multiarch .
	@echo "✓ Multi-arch build completed"
