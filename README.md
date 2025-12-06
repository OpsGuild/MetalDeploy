# MetalDeploy Action

A comprehensive GitHub Action for deploying applications to baremetal servers via SSH. This action supports three deployment modes: baremetal (direct to server), Docker, and Kubernetes.

## Features

- 🔐 **Secure SSH Authentication** - Support for SSH keys or password authentication
- 🎯 **Multiple Deployment Types** - Choose between baremetal (default), Docker, or Kubernetes deployments
- 🐳 **Docker Support** - Automatic Docker and Docker Compose installation
- ☸️ **Kubernetes Support** - Automatic k3s, kubectl, and helm installation
- 🔧 **Auto Dependency Installation** - Installs git and other required tools
- 🏷️ **Registry Support** - Supports GHCR, Docker Hub, and AWS ECR
- 🌿 **Branch Management** - Automatic branch switching based on environment
- ⚡ **Smart Defaults** - Automatically uses current repository and GitHub actor for Git operations

## Default Values

MetalDeploy provides smart defaults to minimize configuration:

- **`git_url`**: Defaults to `${{ github.repositoryUrl }}` - automatically uses the current repository
- **`git_user`**: Defaults to `${{ github.actor }}` - automatically uses the GitHub user triggering the workflow
- **`deployment_type`**: Defaults to `baremetal` - direct server deployment without containers
- **`git_auth_method`**: Defaults to `token` - uses HTTPS with token authentication
- **`environment`**: Defaults to `dev` - development environment
- **`remote_user`**: Defaults to `root` - root user on remote server
- **`registry_type`**: Defaults to `ghcr` - GitHub Container Registry

These defaults mean you can deploy with minimal configuration when using GitHub Actions in the same repository.

## Usage

### Basic Example

This example shows a minimal deployment configuration. Notice that `git_url` and `git_user` are omitted because they default to the current repository URL and GitHub actor:

```yaml
name: Deploy with MetalDeploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy with MetalDeploy
        uses: OpsGuild/MetalDeploy@v1
        with:
          # git_url defaults to ${{ github.repositoryUrl }}
          # git_user defaults to ${{ github.actor }}
          git_auth_method: token
          git_token: ${{ secrets.GITHUB_TOKEN }}
          remote_host: ${{ secrets.REMOTE_HOST }}
          ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
          deployment_type: baremetal  # This is the default
          environment: prod
```

### Advanced Example with Docker Hub

This example shows a Docker deployment with explicit configuration. You can override the defaults for `git_url` and `git_user` if needed:

```yaml
name: Deploy with MetalDeploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy with MetalDeploy
        uses: OpsGuild/MetalDeploy@v1
        with:
          # Override defaults if deploying a different repository
          git_url: https://github.com/username/repo.git
          git_token: ${{ secrets.GITHUB_TOKEN }}
          # git_user defaults to ${{ github.actor }}, but can be overridden
          remote_host: ${{ secrets.REMOTE_HOST }}
          remote_user: deploy
          ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
          deployment_type: docker
          environment: prod
          registry_type: dockerhub
          registry_username: ${{ secrets.DOCKERHUB_USERNAME }}
          registry_password: ${{ secrets.DOCKERHUB_PASSWORD }}
          profile: production
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `git_url` | Git repository URL to clone and deploy | ❌ | `${{ github.repositoryUrl }}` |
| `git_auth_method` | Git authentication method: token, ssh, or none | ❌ | `token` |
| `git_token` | GitHub token for authentication (required if git_auth_method is token) | ❌ | - |
| `git_user` | GitHub username (required if git_auth_method is token) | ❌ | `${{ github.actor }}` |
| `git_ssh_key` | SSH private key for Git authentication (required if git_auth_method is ssh) | ❌ | - |
| `deployment_type` | Deployment type: baremetal, docker, or k8s | ❌ | `baremetal` |
| `remote_host` | SSH remote host IP or domain | ✅ | - |
| `remote_user` | SSH remote user | ❌ | `root` |
| `remote_dir` | Remote directory path for deployment | ❌ | `/home/{remote_user}` |
| `ssh_key` | SSH private key for authentication | ❌ | - |
| `remote_password` | SSH password (if not using SSH key) | ❌ | - |
| `environment` | Deployment environment (dev, staging, prod) | ❌ | `dev` |
| `registry_type` | Docker registry type (ghcr, dockerhub, ecr) | ❌ | `ghcr` |
| `registry_username` | Docker registry username (for dockerhub) | ❌ | - |
| `registry_password` | Docker registry password (for dockerhub) | ❌ | - |
| `aws_region` | AWS region (for ECR) | ❌ | - |
| `aws_account_id` | AWS account ID (for ECR) | ❌ | - |
| `profile` | Docker Compose profile to use (for docker deployment) | ❌ | - |
| `deploy_command` | Command to run for baremetal deployment (e.g., "make deploy") | ❌ | - |
| `k8s_manifest_path` | Path to Kubernetes manifest file or directory | ❌ | - |
| `k8s_namespace` | Kubernetes namespace to deploy to | ❌ | `default` |
| `use_sudo` | Use sudo for commands (true/false). Some system commands may still require sudo | ❌ | `false` |

## Outputs

| Output | Description |
|-------|-------------|
| `deployment_status` | Deployment status (success/failed) |
| `remote_hostname` | Hostname of the remote server |

## Deployment Types

The `deployment_type` parameter determines how your application is deployed to the remote server. MetalDeploy supports three deployment types, each optimized for different use cases. **By default, MetalDeploy uses `baremetal` deployment**, which provides direct server deployment without containerization overhead.

### 1. Baremetal Deployment (Default)

Baremetal deployment is the default deployment type and deploys your application directly to the server without Docker or Kubernetes. This is perfect for:
- Simple applications that don't require containerization
- Applications with system-level dependencies
- When you want full control over the deployment process
- Fast deployments without container overhead
- Legacy applications that aren't containerized

**How it works:**
1. The action clones your repository to the remote server
2. It then executes your deployment command in the repository directory
3. The deployment command can be specified explicitly or auto-detected

**Usage:**
```yaml
deployment_type: baremetal  # This is the default, so you can omit it
deploy_command: make deploy  # Optional: custom command to run
```

**Default Behavior (Command Resolution Order):**
1. If `deploy_command` is specified, runs that exact command
2. Otherwise, looks for `deploy.sh` in the repository root and runs it (with execute permissions)
3. If no `deploy.sh` exists, looks for `Makefile` and runs `make {environment}` (e.g., `make dev`, `make staging`, `make prod`)
4. If none of the above are found, the deployment will fail with an error asking you to specify `deploy_command`

**Example with explicit command:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: baremetal  # Optional since it's the default
    deploy_command: "npm install && npm run build && pm2 restart app"
    environment: prod
```

**Example with auto-detection (using Makefile):**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    # deployment_type defaults to baremetal
    environment: staging
    # Will automatically run: make staging
```

**Example with deploy.sh script:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    environment: prod
    # Will automatically run: ./deploy.sh
```

**Best Practices:**
- Create a `deploy.sh` script for complex deployments with multiple steps
- Use a `Makefile` if you have multiple environments and want to keep commands organized
- Use `deploy_command` for simple one-off deployments or when you need dynamic commands

### 2. Docker Deployment

Docker deployment uses Docker Compose to deploy containerized applications. This is ideal for:
- Applications that are already containerized
- Multi-container applications (web, database, cache, etc.)
- Applications that need isolated environments
- Microservices architectures
- Applications requiring consistent runtime environments

**How it works:**
1. The action automatically installs Docker and Docker Compose if not already present
2. It clones your repository to the remote server
3. It authenticates with your Docker registry (GHCR, Docker Hub, or ECR)
4. It runs `docker compose up --build -d` to build and start your containers
5. Optionally uses Docker Compose profiles to deploy specific service sets

**Usage:**
```yaml
deployment_type: docker
profile: production  # Optional: use Docker Compose profiles
registry_type: ghcr  # or dockerhub, ecr
```

**Example with GitHub Container Registry (GHCR):**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: docker
    git_token: ${{ secrets.GITHUB_TOKEN }}
    git_user: ${{ github.actor }}  # Default, can be omitted
    registry_type: ghcr  # Uses git_user and git_token for auth
    profile: production  # Optional: deploy only services with this profile
```

**Example with Docker Hub:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: docker
    registry_type: dockerhub
    registry_username: ${{ secrets.DOCKERHUB_USERNAME }}
    registry_password: ${{ secrets.DOCKERHUB_PASSWORD }}
    profile: production
```

**Example with AWS ECR:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: docker
    registry_type: ecr
    aws_region: us-east-1
    aws_account_id: ${{ secrets.AWS_ACCOUNT_ID }}
    # Requires AWS credentials configured on the remote server
```

**Requirements:**
- Your repository must have a `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, or `compose.yaml` file
- Your Docker images must be available in the specified registry
- The remote server must have internet access to pull images

**Docker Compose Profiles:**
Profiles allow you to deploy specific subsets of services defined in your `docker-compose.yml`. For example:
```yaml
services:
  web:
    profiles: ["production"]
  worker:
    profiles: ["production", "staging"]
  dev-tools:
    profiles: ["dev"]
```
When you specify `profile: production`, only services with the `production` profile will be deployed.

### 3. Kubernetes Deployment

Kubernetes deployment uses k3s (a lightweight Kubernetes distribution) to deploy containerized applications. This is ideal for:
- Production-grade container orchestration
- Applications requiring high availability and scaling
- Complex multi-service applications
- Applications that need service discovery and load balancing
- Teams familiar with Kubernetes

**How it works:**
1. The action automatically installs k3s, kubectl, and helm if not already present
2. It installs Docker (required by k3s for container runtime)
3. It clones your repository to the remote server
4. It authenticates with your Docker registry
5. It creates the specified Kubernetes namespace (if it doesn't exist)
6. It applies all Kubernetes manifests from the specified path

**k3s Overview:**
k3s is a certified Kubernetes distribution designed for resource-constrained environments. It's perfect for:
- Single-node Kubernetes clusters
- Edge computing deployments
- Development and testing environments
- Small to medium production workloads

**Usage:**
```yaml
deployment_type: k8s
k8s_manifest_path: k8s/  # Optional: auto-detected if not specified
k8s_namespace: production  # Optional: defaults to 'default'
registry_type: ghcr  # Required for pulling container images
```

**Default Behavior (Manifest Path Resolution):**
The action will automatically search for Kubernetes manifests in this order:
1. If `k8s_manifest_path` is specified, uses that path
2. Otherwise, looks for directories: `k8s/`, `manifests/`, or `kubernetes/`
3. If no directory found, looks for files: `k8s.yaml`, `k8s.yml`, `deployment.yaml`, or `deployment.yml`
4. If nothing is found, the deployment will fail with an error

**Example with directory of manifests:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: k8s
    k8s_manifest_path: k8s/  # Directory containing YAML files
    k8s_namespace: production
    registry_type: ghcr
    git_token: ${{ secrets.GITHUB_TOKEN }}
```

**Example with single manifest file:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: k8s
    k8s_manifest_path: deployment.yaml  # Single file
    k8s_namespace: staging
```

**Example with auto-detection:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: k8s
    # Will automatically find k8s/, manifests/, or kubernetes/ directory
    k8s_namespace: production
```

**Requirements:**
- Your repository should have Kubernetes manifest files (YAML) in a `k8s/`, `manifests/`, or `kubernetes/` directory, or a single manifest file
- Your container images must be available in the specified registry
- The remote server must have sufficient resources (RAM, CPU) for k3s and your workloads
- At least 512MB RAM recommended for k3s alone

**Namespace Management:**
- The action automatically creates the namespace if it doesn't exist
- All resources are deployed to the specified namespace
- Use different namespaces for different environments (dev, staging, prod)

**k3s Configuration:**
- k3s is installed with Traefik disabled (you can use your own ingress controller)
- kubeconfig is automatically configured at `/etc/rancher/k3s/k3s.yaml`
- The action sets `KUBECONFIG` environment variable for kubectl commands

## Registry Types

### GitHub Container Registry (GHCR)

Uses `git_user` and `git_token` for authentication.

```yaml
registry_type: ghcr
```

### Docker Hub

Requires `registry_username` and `registry_password`.

```yaml
registry_type: dockerhub
registry_username: ${{ secrets.DOCKERHUB_USERNAME }}
registry_password: ${{ secrets.DOCKERHUB_PASSWORD }}
```

### AWS ECR

Requires `aws_region` and `aws_account_id`. The action will use AWS CLI to authenticate.

```yaml
registry_type: ecr
aws_region: us-east-1
aws_account_id: 123456789012
```

## What Gets Installed

The action automatically installs dependencies based on the deployment type. It only installs what's needed, checking if tools are already present before installing to save time.

### All Deployments

These tools are installed for every deployment type:

- **Git**: Version control system for cloning repositories
- **Python 3 and pip**: Required for running the deployment script and some build tools
- **Build tools**: Essential compilation tools including:
  - `build-essential`: GCC compiler and make utilities
  - `libssl-dev`: OpenSSL development libraries
  - `libffi-dev`: Foreign Function Interface library

**Installation Method:** Uses `apt-get` package manager (Ubuntu/Debian)

### Docker Deployments

For `deployment_type: docker` or `deployment_type: k8s`, the following are installed:

- **Docker**: Container runtime engine
  - Installed from Docker's official repository
  - Latest stable version
  - Docker daemon is enabled and started automatically
- **Docker Compose**: Multi-container orchestration tool
  - Version 1.29.2 (stable)
  - Installed to `/usr/local/bin/docker-compose`
  - Made executable automatically

**Installation Method:** Official Docker installation script and direct download

**Post-Installation:**
- Current user is added to the `docker` group (requires logout/login to take effect)
- Docker service is enabled to start on boot
- Docker daemon is started immediately

### Kubernetes Deployments

For `deployment_type: k8s` only, the following are additionally installed:

- **kubectl**: Kubernetes command-line tool
  - Latest stable version from Kubernetes official releases
  - Installed to `/usr/local/bin/kubectl`
  - Used to interact with the k3s cluster

- **Helm**: Kubernetes package manager
  - Latest version from official Helm installation script
  - Used for deploying Helm charts (if needed)

- **k3s**: Lightweight Kubernetes distribution
  - Installed via official k3s installation script
  - Traefik ingress controller is disabled by default
  - Automatically enabled and started as a systemd service
  - kubeconfig is configured at `/etc/rancher/k3s/k3s.yaml`
  - Environment variable `KUBECONFIG` is set in `.bashrc`

**Installation Method:** Official installation scripts from respective projects

**Post-Installation:**
- k3s service is enabled to start on boot
- k3s service is started immediately
- KUBECONFIG environment variable is configured

### Installation Behavior

- **Idempotent**: The action checks if tools are already installed before attempting installation
- **Non-destructive**: Existing installations are not modified or removed
- **Fast**: Skips installation if tools are already present
- **Automatic**: No manual intervention required

**Note:** All installations require sudo/root access. The action handles this automatically.

## Sudo Usage

By default, the action doesnt use `sudo` for commands. You can enable this by setting `use_sudo: true`:

```yaml
use_sudo: true  # Run commands with sudo
```

**Note:** Some system-level commands (like `apt-get`, `systemctl`, `usermod`) will still use sudo regardless of this setting. Deployment commands (like `docker compose`, `make`, custom scripts) will respect the `use_sudo` setting.

This is useful when:
- Your SSH user already has necessary permissions
- You're using a non-root user with proper group memberships (e.g., docker group)
- You want to avoid password prompts for sudo

## Git Authentication Methods

The action supports three methods for authenticating with Git repositories. The authentication method determines how the action clones your repository on the remote server.

### 1. Token Authentication (Default)

Uses HTTPS with a GitHub Personal Access Token or GitHub Actions token. This is the default and recommended method for most use cases.

```yaml
git_auth_method: token  # This is the default
git_token: ${{ secrets.GITHUB_TOKEN }}
git_user: ${{ github.actor }}  # Defaults to ${{ github.actor }}, can be omitted
```

**How it works:**
- The action embeds the token in the Git URL: `https://{git_user}:{git_token}@github.com/owner/repo.git`
- This allows authenticated access to private repositories
- The token is only used during the clone operation

**Use when:**
- Using GitHub Actions (can use `GITHUB_TOKEN` which is automatically available)
- You have a Personal Access Token with repository access
- You prefer HTTPS over SSH
- You want the simplest setup

**Note:** `git_user` defaults to `${{ github.actor }}` (the GitHub username triggering the workflow), so you typically don't need to specify it unless you're using a different account's token.

### 2. SSH Authentication

Uses SSH keys for Git operations. This method is useful when you have deploy keys configured or prefer SSH-based authentication.

```yaml
git_auth_method: ssh
git_ssh_key: ${{ secrets.GIT_SSH_KEY }}
# Or use the same key as server SSH:
# git_ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
```

**How it works:**
- The action creates a temporary SSH key file on the remote server
- It configures Git to use this key for authentication
- Automatically converts HTTPS URLs to SSH format (e.g., `https://github.com/user/repo.git` → `git@github.com:user/repo.git`)
- The key is cleaned up after the deployment

**Use when:**
- You have deploy keys set up in your repository
- You prefer SSH authentication over HTTPS
- You want to use the same SSH key for both server access and Git operations
- Your organization requires SSH for Git access

**Setting up Deploy Keys:**
1. Generate an SSH key pair: `ssh-keygen -t ed25519 -C "deploy@yourproject"`
2. Add the public key to your repository: Settings → Deploy keys → Add deploy key
3. Store the private key in GitHub Secrets as `GIT_SSH_KEY`

**Note:** The action automatically converts HTTPS URLs to SSH format (e.g., `https://github.com/user/repo.git` → `git@github.com:user/repo.git`)

### 3. No Authentication

For public repositories that don't require authentication. This is the simplest method but only works for public repositories.

```yaml
git_auth_method: none
```

**How it works:**
- The action clones the repository using standard Git commands without authentication
- Works exactly like cloning a public repository locally: `git clone https://github.com/user/repo.git`

**Use when:**
- Repository is public and doesn't require authentication
- You want the simplest possible configuration
- You're deploying open-source applications

**Limitations:**
- Cannot access private repositories
- Cannot access repositories that require authentication even for public access
- May hit rate limits for large repositories or frequent deployments

## Branch Management

MetalDeploy automatically manages Git branches based on your environment setting. This ensures you're always deploying the correct code for each environment.

**Branch Selection Logic:**
- **Production environments** (`prod` or `production`): Automatically uses `main` or `master` branch (whichever exists in the repository)
- **Other environments** (e.g., `dev`, `staging`, `test`): Uses the branch matching the environment name

**How it works:**
1. The action clones or updates the repository on the remote server
2. It checks which branch to use based on the `environment` parameter
3. It switches to the appropriate branch (stashing any local changes if needed)
4. It pulls the latest changes from the remote branch
5. It then proceeds with the deployment

**Example:**
```yaml
environment: prod      # Will use 'main' or 'master' branch
environment: staging    # Will use 'staging' branch
environment: dev        # Will use 'dev' branch
```

**Important Notes:**
- The branch must exist in your remote repository
- If you're using `prod` or `production`, the action will look for `origin/main` first, then `origin/master`
- If the target branch doesn't exist, the deployment will fail
- Any uncommitted changes on the remote server will be stashed before switching branches

## Security Best Practices

1. **Use SSH Keys**: Prefer `ssh_key` over `remote_password` for better security
2. **Use Secrets**: Store all sensitive values in GitHub Secrets
3. **Limit Permissions**: Use a dedicated deployment user with limited sudo permissions
4. **Rotate Credentials**: Regularly rotate SSH keys and tokens

## Requirements

- Remote server must be accessible via SSH
- Sudo access required on remote server (unless using root user)

## Supported Server Types

This action supports the following server operating systems:

### Linux Distributions

- **Ubuntu** (all LTS and current versions)
- **Debian** (9+)
- Any other Debian/Ubuntu-based distributions that use:
  - `apt-get` package manager
  - `systemd` for service management
  - Standard Linux command-line tools

### Server Requirements

- SSH access (port 22 or custom port)
- Internet connectivity for package installation
- Sufficient disk space for dependencies and your application
- Root or sudo access for system-level operations

**Note:** The action is optimized for Ubuntu/Debian systems. Other Linux distributions may work but are not officially tested.

## Technical Details

This action is built using [Fabric](https://www.fabfile.org/) (Python library for SSH deployment and system administration) to handle remote server connections and command execution. Fabric provides secure SSH communication and robust command execution capabilities.

## Example Workflows

Check out the example workflows in the [`.github/workflows/`](.github/workflows/) directory:

- **example-baremetal.yml** - Baremetal deployment example
- **example-docker.yml** - Docker Compose deployment example
- **example-k8s.yml** - Kubernetes deployment example

## Development

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to ensure code quality. Install it with:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install
```

The hooks will automatically run:
- Code formatting (Black)
- Import sorting (isort)
- Linting (flake8)
- Basic file checks (trailing whitespace, end-of-file, YAML validation, etc.)

### Testing

This action includes a comprehensive test suite. See [tests/README.md](tests/README.md) for details.

### Quick Start

Using Make (recommended):
```bash
make install-dev  # Install test dependencies
make test         # Run all tests
make test-unit    # Run only fast unit tests
make test-coverage # Run with coverage report
```

Or manually:
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=deploy --cov-report=html
```

### Test Structure

- **Unit Tests** (`tests/test_deploy.py`) - Fast tests using mocks, no external dependencies
- **Integration Tests** (`tests/test_integration.py`) - Tests requiring real infrastructure (skipped by default)

Tests run automatically in CI on every push and pull request. See [tests/README.md](tests/README.md) for detailed testing documentation.

## License

MIT License - see [LICENSE](LICENSE) file for details

## Support

For issues and feature requests, please open an issue on the [GitHub repository](https://github.com/OpsGuild/MetalDeploy).
