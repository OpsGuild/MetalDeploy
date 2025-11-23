# MetalDeploy Action

A comprehensive GitHub Action for deploying applications to baremetal servers via SSH. This action supports three deployment modes: baremetal (direct to server), Docker, and Kubernetes.

## Features

- 🔐 **Secure SSH Authentication** - Support for SSH keys or password authentication
- 🎯 **Multiple Deployment Types** - Choose between baremetal, Docker, or Kubernetes deployments
- 🐳 **Docker Support** - Automatic Docker and Docker Compose installation
- ☸️ **Kubernetes Support** - Automatic k3s, kubectl, and helm installation
- 🔧 **Auto Dependency Installation** - Installs git and other required tools
- 🏷️ **Registry Support** - Supports GHCR, Docker Hub, and AWS ECR
- 🌿 **Branch Management** - Automatic branch switching based on environment

## Usage

### Basic Example

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
          git_url: ${{ secrets.GIT_URL }}
          git_auth_method: token
          git_token: ${{ secrets.GITHUB_TOKEN }}
          git_user: ${{ github.actor }}
          remote_host: ${{ secrets.REMOTE_HOST }}
          ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
          deployment_type: docker
          environment: prod
```

### Advanced Example with Docker Hub

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
          git_url: https://github.com/username/repo.git
          git_token: ${{ secrets.GITHUB_TOKEN }}
          git_user: ${{ github.actor }}
          remote_host: ${{ secrets.REMOTE_HOST }}
          remote_user: deploy
          ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
          environment: prod
          registry_type: dockerhub
          registry_username: ${{ secrets.DOCKERHUB_USERNAME }}
          registry_password: ${{ secrets.DOCKERHUB_PASSWORD }}
          profile: production
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `git_url` | Git repository URL to clone and deploy | ✅ | - |
| `git_auth_method` | Git authentication method: token, ssh, or none | ❌ | `token` |
| `git_token` | GitHub token for authentication (required if git_auth_method is token) | ❌ | - |
| `git_user` | GitHub username (required if git_auth_method is token) | ❌ | - |
| `git_ssh_key` | SSH private key for Git authentication (required if git_auth_method is ssh) | ❌ | - |
| `deployment_type` | Deployment type: baremetal, docker, or k8s | ❌ | `docker` |
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
| `baremetal_command` | Command to run for baremetal deployment (e.g., "make deploy") | ❌ | - |
| `k8s_manifest_path` | Path to Kubernetes manifest file or directory | ❌ | - |
| `k8s_namespace` | Kubernetes namespace to deploy to | ❌ | `default` |
| `use_sudo` | Use sudo for commands (true/false). Some system commands may still require sudo | ❌ | `true` |

## Outputs

| Output | Description |
|-------|-------------|
| `deployment_status` | Deployment status (success/failed) |
| `remote_hostname` | Hostname of the remote server |

## Deployment Types

### 1. Baremetal Deployment

Deploy directly to the server without Docker or Kubernetes. Perfect for simple applications or when you want full control.

**Usage:**
```yaml
deployment_type: baremetal
baremetal_command: make deploy  # Optional: custom command to run
```

**Default Behavior:**
- If `baremetal_command` is specified, runs that command
- Otherwise, looks for `Makefile` and runs `make {environment}`
- If no Makefile, looks for `deploy.sh` and runs it
- If none found, requires `baremetal_command` to be specified

**Example:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: baremetal
    baremetal_command: "npm install && npm run build && pm2 restart app"
    # Or let it auto-detect: make dev, make staging, make prod
```

### 2. Docker Deployment

Deploy using Docker Compose. The action automatically installs Docker and Docker Compose.

**Usage:**
```yaml
deployment_type: docker
profile: production  # Optional: use Docker Compose profiles
```

**Example:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: docker
    profile: production
    registry_type: dockerhub
    registry_username: ${{ secrets.DOCKERHUB_USERNAME }}
    registry_password: ${{ secrets.DOCKERHUB_PASSWORD }}
```

**Requirements:** Your repository must have a `docker-compose.yml` or `compose.yml` file.

### 3. Kubernetes Deployment

Deploy to Kubernetes using k3s. The action automatically installs k3s, kubectl, and helm.

**Usage:**
```yaml
deployment_type: k8s
k8s_manifest_path: k8s/  # Optional: defaults to k8s/, manifests/, or kubernetes/
k8s_namespace: production  # Optional: defaults to 'default'
```

**Default Behavior:**
- Looks for manifests in `k8s/`, `manifests/`, or `kubernetes/` directories
- Or looks for `k8s.yaml`, `k8s.yml`, `deployment.yaml`, or `deployment.yml` files
- Creates namespace if it doesn't exist
- Applies all manifests in the specified path

**Example:**
```yaml
- name: Deploy with MetalDeploy
  uses: OpsGuild/MetalDeploy@v1
  with:
    deployment_type: k8s
    k8s_manifest_path: k8s/
    k8s_namespace: production
    registry_type: ghcr
```

**Requirements:** Your repository should have Kubernetes manifest files (YAML) in a `k8s/`, `manifests/`, or `kubernetes/` directory.

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

The action automatically installs dependencies based on the deployment type:

**All deployments:**
- Git
- Python 3 and pip
- Build tools (build-essential, libssl-dev, libffi-dev)

**Docker deployments (docker or k8s):**
- Docker and Docker Compose

**Kubernetes deployments (k8s only):**
- kubectl (Kubernetes CLI)
- Helm (Kubernetes package manager)
- k3s (lightweight Kubernetes distribution)

## Sudo Usage

By default, the action uses `sudo` for commands. You can disable this by setting `use_sudo: false`:

```yaml
use_sudo: false  # Run commands without sudo
```

**Note:** Some system-level commands (like `apt-get`, `systemctl`, `usermod`) will still require sudo regardless of this setting. Deployment commands (like `docker compose`, `make`, custom scripts) will respect the `use_sudo` setting.

This is useful when:
- Your SSH user already has necessary permissions
- You're using a non-root user with proper group memberships (e.g., docker group)
- You want to avoid password prompts for sudo

## Git Authentication Methods

The action supports three methods for authenticating with Git repositories:

### 1. Token Authentication (Default)

Uses HTTPS with a GitHub Personal Access Token or GitHub Actions token:

```yaml
git_auth_method: token
git_token: ${{ secrets.GITHUB_TOKEN }}
git_user: ${{ github.actor }}
```

**Use when:**
- Using GitHub Actions (can use `GITHUB_TOKEN`)
- You have a Personal Access Token
- You prefer HTTPS over SSH

### 2. SSH Authentication

Uses SSH keys for Git operations:

```yaml
git_auth_method: ssh
git_ssh_key: ${{ secrets.GIT_SSH_KEY }}
# Or use the same key as server SSH:
# git_ssh_key: ${{ secrets.SSH_PRIVATE_KEY }}
```

**Use when:**
- You have deploy keys set up
- You prefer SSH authentication
- You want to use the same SSH key for server and Git

**Note:** The action automatically converts HTTPS URLs to SSH format (e.g., `https://github.com/user/repo.git` → `git@github.com:user/repo.git`)

### 3. No Authentication

For public repositories only:

```yaml
git_auth_method: none
```

**Use when:**
- Repository is public
- No authentication needed

## Branch Management

- **Production**: Automatically uses `main` or `master` branch
- **Other environments**: Uses the branch matching the environment name (e.g., `dev`, `staging`)

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
