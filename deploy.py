#!/usr/bin/env python3
import base64
import os
import tempfile

from fabric import Connection
from invoke import Responder

# Configuration from environment variables
# Default GIT_URL to current repository if in GitHub Actions context
git_url_env = os.getenv("GIT_URL", "")
if not git_url_env and os.getenv("GITHUB_REPOSITORY"):
    # Construct GitHub repository URL from GITHUB_REPOSITORY (format: owner/repo)
    github_repo = os.getenv("GITHUB_REPOSITORY")
    GIT_URL = f"https://github.com/{github_repo}.git"
else:
    GIT_URL = git_url_env

GIT_AUTH_METHOD = os.getenv("GIT_AUTH_METHOD", "token").lower()
GIT_TOKEN = os.getenv("GIT_TOKEN", "")
GIT_USER = os.getenv("GIT_USER", os.getenv("GITHUB_ACTOR", ""))
GIT_SSH_KEY = os.getenv("GIT_SSH_KEY")
DEPLOYMENT_TYPE = os.getenv("DEPLOYMENT_TYPE", "baremetal").lower()
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
REMOTE_USER = os.getenv("REMOTE_USER", "root")
REMOTE_HOST = os.getenv("REMOTE_HOST", "127.0.0.1")
# Set default REMOTE_DIR based on user: /root for root, /home/{user} for others
if os.getenv("REMOTE_DIR"):
    REMOTE_DIR = os.getenv("REMOTE_DIR")
elif REMOTE_USER == "root":
    REMOTE_DIR = "/root"
else:
    REMOTE_DIR = f"/home/{REMOTE_USER}"
SSH_KEY = os.getenv("SSH_KEY")
REMOTE_PASSWORD = os.getenv("REMOTE_PASSWORD")
REGISTRY_TYPE = os.getenv("REGISTRY_TYPE", "ghcr")
PROFILE = os.getenv("PROFILE")
DEPLOY_COMMAND = os.getenv("DEPLOY_COMMAND")
K8S_MANIFEST_PATH = os.getenv("K8S_MANIFEST_PATH")
K8S_NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
USE_SUDO = os.getenv("USE_SUDO", "false").lower() == "true"
PROJECT_NAME = GIT_URL.split("/")[-1].split(".")[0] if GIT_URL else ""
GIT_DIR = os.path.join(REMOTE_DIR, PROJECT_NAME) if PROJECT_NAME else REMOTE_DIR
GIT_SUBDIR = os.path.join(GIT_DIR, "")
SSH_KEY_PATH = None
GIT_SSH_KEY_PATH = None
AUTH_GIT_URL = None


def setup_ssh_key():
    """Setup SSH key file from environment variable (supports raw or base64 encoded)"""
    global SSH_KEY_PATH

    if SSH_KEY:
        try:
            decoded_key = base64.b64decode(SSH_KEY).decode("utf-8")
            if "BEGIN" in decoded_key and "PRIVATE KEY" in decoded_key:
                key_content = decoded_key
            else:
                key_content = SSH_KEY
        except Exception:
            key_content = SSH_KEY

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem") as f:
            f.write(key_content)
            SSH_KEY_PATH = f.name
        os.chmod(SSH_KEY_PATH, 0o600)


def setup_git_auth():
    """
    Setup Git authentication based on GIT_AUTH_METHOD
    """

    global AUTH_GIT_URL, GIT_SSH_KEY_PATH

    if GIT_AUTH_METHOD == "token":
        if not GIT_TOKEN or not GIT_USER:
            raise ValueError("GIT_TOKEN and GIT_USER are required when git_auth_method is 'token'")
        prefix = f"https://{GIT_USER}:{GIT_TOKEN}@"
        suffix = GIT_URL.split("https://")[-1] if "https://" in GIT_URL else GIT_URL
        AUTH_GIT_URL = prefix + suffix
    elif GIT_AUTH_METHOD == "ssh":
        if not GIT_SSH_KEY:
            if SSH_KEY:
                git_ssh_key = SSH_KEY
            else:
                raise ValueError("GIT_SSH_KEY or SSH_KEY is required when git_auth_method is 'ssh'")
        else:
            git_ssh_key = GIT_SSH_KEY

        try:
            decoded_key = base64.b64decode(git_ssh_key).decode("utf-8")
            if "BEGIN" in decoded_key and "PRIVATE KEY" in decoded_key:
                key_content = decoded_key
            else:
                key_content = git_ssh_key
        except Exception:
            key_content = git_ssh_key

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem") as f:
            f.write(key_content)
            GIT_SSH_KEY_PATH = f.name
        os.chmod(GIT_SSH_KEY_PATH, 0o600)

        if GIT_URL.startswith("https://"):
            url_parts = GIT_URL.replace("https://", "").replace("http://", "")
            if "/" in url_parts:
                domain, path = url_parts.split("/", 1)
                AUTH_GIT_URL = f"git@{domain}:{path}"
            else:
                AUTH_GIT_URL = GIT_URL
        else:
            AUTH_GIT_URL = GIT_URL
    elif GIT_AUTH_METHOD == "none":
        AUTH_GIT_URL = GIT_URL
    else:
        raise ValueError(
            f"Invalid git_auth_method: {GIT_AUTH_METHOD}. Must be 'token', 'ssh', or 'none'"
        )


def run_command(conn, command, force_sudo=False):
    """
    Helper function to run commands with optional sudo support.
    When using sudo, sources the user's shell profile to ensure functions
    and aliases defined in .bashrc are available.
    """

    use_sudo_for_this = USE_SUDO or force_sudo

    if not use_sudo_for_this:
        return conn.run(command, warn=False)

    if REMOTE_USER == "root":
        home_dir = "/root"
    else:
        home_dir = f"/home/{REMOTE_USER}"

    escaped_command = command.replace("'", "'\"'\"'")

    # Wrap command in bash that sources the profile to make functions available
    wrapped_command = (
        f"bash -l -c '"
        f'export PS1="$ "; '
        f"set +e; "
        f"if [ -f {home_dir}/.bashrc ]; then "
        f"  source {home_dir}/.bashrc 2>/dev/null; "
        f"fi; "
        f"if [ -f {home_dir}/.bash_profile ]; then "
        f"  source {home_dir}/.bash_profile 2>/dev/null; "
        f"fi; "
        f"if [ -f {home_dir}/.profile ]; then "
        f"  source {home_dir}/.profile 2>/dev/null; "
        f"fi; "
        f"set -e; "
        f"{escaped_command}"
        f"'"
    )

    if REMOTE_PASSWORD:
        escaped_pwd = REMOTE_PASSWORD.replace("'", "'\"'\"'")
        full_command = f"printf '%s\\n' '{escaped_pwd}' | sudo -S {wrapped_command}"
        return conn.run(full_command, pty=False, warn=False)
    else:
        return conn.run(f"sudo {wrapped_command}", warn=False)


def install_dependencies(conn):
    """
    Install required system dependencies
    """

    deps = [
        "git",
        "python3-pip",
        "python3-dev",
        "build-essential",
        "libssl-dev",
        "libffi-dev",
    ]
    missing = []
    for dep in deps:
        result = conn.run(f"which {dep}", warn=True, hide=True)
        if not result.stdout.strip():
            missing.append(dep)

    if missing:
        print(f"======= Installing dependencies: {', '.join(missing)} =======")
        run_command(conn, "apt-get update", force_sudo=True)
        run_command(conn, f"apt-get install -y {' '.join(missing)}", force_sudo=True)
        print("======= Dependencies installed =======")
    else:
        print("======= All dependencies already installed =======")


def install_kubectl(conn):
    """
    Install kubectl if not already installed
    """

    kubectl_check = conn.run("which kubectl", warn=True, hide=True)
    if kubectl_check.stdout.strip():
        print("======= kubectl already installed =======")
        return

    print("======= Installing kubectl =======")
    version_result = conn.run(
        "curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt",
        hide=True,
    )
    latest_version = version_result.stdout.strip()

    conn.run(
        f"curl -LO https://storage.googleapis.com/kubernetes-release/release/{latest_version}/bin/linux/amd64/kubectl"
    )
    conn.run("chmod +x ./kubectl")
    run_command(conn, "mv ./kubectl /usr/local/bin/kubectl", force_sudo=True)
    print("======= kubectl installed =======")


def install_helm(conn):
    """
    Install helm if not already installed
    """

    helm_check = conn.run("which helm", warn=True, hide=True)
    if helm_check.stdout.strip():
        print("======= helm already installed =======")
        return

    print("======= Installing helm =======")
    if REMOTE_PASSWORD:
        escaped_pwd = REMOTE_PASSWORD.replace("'", "'\"'\"'")
        conn.run(
            f"cat > /tmp/helm-askpass.sh << 'HELMASKPASS_EOF'\n"
            f"#!/bin/sh\n"
            f"printf '%s\\n' '{escaped_pwd}'\n"
            f"HELMASKPASS_EOF",
            warn=False,
        )
        conn.run("chmod +x /tmp/helm-askpass.sh", warn=False)
        conn.run(
            "curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 > /tmp/get-helm-3.sh",
            warn=False,
        )
        conn.run(
            "sed -i 's/sudo /sudo -A /g' /tmp/get-helm-3.sh",
            warn=False,
        )
        conn.run("chmod +x /tmp/get-helm-3.sh", warn=False)
        conn.run(
            "SUDO_ASKPASS=/tmp/helm-askpass.sh bash /tmp/get-helm-3.sh",
            pty=False,
            warn=False,
        )
    else:
        conn.run(
            "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash",
            warn=False,
        )
    print("======= helm installed =======")


def install_k3s(conn):
    """
    Install k3s if not already installed
    """

    result = conn.run("which k3s", warn=True, hide=True)
    if result.stdout.strip():
        print("======= k3s already installed =======")
        return

    print("======= Installing k3s =======")
    conn.run(
        'curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -',
        pty=True,
    )
    run_command(conn, "systemctl enable k3s", force_sudo=True)
    run_command(conn, "systemctl start k3s", force_sudo=True)
    conn.run("echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc")

    version_result = conn.run("k3s --version", hide=True)
    print(f"Installed k3s version: {version_result.stdout.strip()}")
    print("======= k3s installed =======")


def install_docker(conn):
    """
    Install Docker and Docker Compose if not already installed
    """

    result = conn.run("which docker", warn=True, hide=True)
    if result.stdout.strip():
        print("======= Docker already installed =======")
        return

    run_command(conn, "apt-get update", force_sudo=True)
    run_command(
        conn,
        "apt-get install -y apt-transport-https ca-certificates curl " "software-properties-common",
        force_sudo=True,
    )

    run_command(
        conn,
        "bash -c 'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -'",
        force_sudo=True,
    )
    run_command(
        conn,
        'add-apt-repository "deb [arch=amd64] '
        'https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"',
        force_sudo=True,
    )
    run_command(conn, "apt-get update", force_sudo=True)
    run_command(conn, "apt-get install -y docker-ce", force_sudo=True)

    run_command(
        conn,
        "curl -L "
        '"https://github.com/docker/compose/releases/download/1.29.2/'
        'docker-compose-$(uname -s)-$(uname -m)" '
        "-o /usr/local/bin/docker-compose",
        force_sudo=True,
    )
    run_command(conn, "chmod +x /usr/local/bin/docker-compose", force_sudo=True)
    run_command(conn, "usermod -aG docker ${USER}", force_sudo=True)
    run_command(conn, "systemctl enable docker", force_sudo=True)
    run_command(conn, "systemctl start docker", force_sudo=True)
    print("======= Docker installed =======")


def clone_repo(conn):
    """
    Clone the Git repository to the remote server
    """

    promptpass = Responder(
        pattern=r"Are you sure you want to continue connecting " r"\(yes/no/\[fingerprint\]\)\?",
        response="yes\n",
    )

    conn.run(f"mkdir -p {REMOTE_DIR}", warn=True)

    if GIT_AUTH_METHOD == "ssh" and GIT_SSH_KEY_PATH:
        conn.put(GIT_SSH_KEY_PATH, "/tmp/git_deploy_key")
        conn.run("chmod 600 /tmp/git_deploy_key")

        ssh_config = """
Host github.com
    IdentityFile /tmp/git_deploy_key
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
"""
        conn.run("mkdir -p ~/.ssh", warn=True)
        conn.run(f'echo "{ssh_config}" >> ~/.ssh/config')
        conn.run("chmod 600 ~/.ssh/config")

    result = conn.run(
        f'test -d {GIT_DIR} && echo "exists" || echo "not exists"',
        hide=True,
    )

    if "not exists" in result.stdout:
        print("======= Cloning the repository =======")
        with conn.cd(REMOTE_DIR):
            if GIT_AUTH_METHOD == "ssh":
                conn.run(
                    f"GIT_SSH_COMMAND='ssh -i /tmp/git_deploy_key -o StrictHostKeyChecking=no' git clone {AUTH_GIT_URL} {PROJECT_NAME}",
                    pty=True,
                    watchers=[promptpass],
                )
            else:
                conn.run(
                    f"git clone {AUTH_GIT_URL} {PROJECT_NAME}",
                    pty=True,
                    watchers=[promptpass],
                )
    else:
        git_check = conn.run(
            f'test -d {GIT_DIR}/.git && echo "git_repo" || echo "not_git_repo"',
            hide=True,
        )
        if "not_git_repo" in git_check.stdout:
            print(f"======= Directory {GIT_DIR} exists but is not a git repository =======")
            print("======= Initializing git repository in existing directory =======")
            with conn.cd(GIT_DIR):
                conn.run("git init", warn=False)
                conn.run(f"git remote add origin {AUTH_GIT_URL}", warn=False)
                if GIT_AUTH_METHOD == "ssh":
                    conn.run(
                        "GIT_SSH_COMMAND='ssh -i /tmp/git_deploy_key -o StrictHostKeyChecking=no' git fetch origin",
                        pty=True,
                        watchers=[promptpass],
                    )
                else:
                    conn.run("git fetch origin", pty=True, watchers=[promptpass])
                conn.run(
                    "git branch -M main 2>/dev/null || git branch -M master 2>/dev/null || true",
                    warn=False,
                )
                conn.run(
                    "git checkout -b main origin/main 2>/dev/null || git checkout -b master origin/master 2>/dev/null || true",
                    warn=False,
                )
        else:
            print(f"======= Repository already exists at {GIT_DIR}, skipping clone =======")

    conn.run(f"git config --global --add safe.directory {GIT_DIR}")
    run_command(conn, f"chown -R $(whoami) {GIT_DIR}", force_sudo=True)

    with conn.cd(GIT_SUBDIR):
        if ENVIRONMENT in ["prod", "production"]:
            result = conn.run("git branch -r", hide=True)
            remote_branches = [line.strip() for line in result.stdout.strip().splitlines()]

            print(f"=== Remote branches: {remote_branches} ===")

            if "origin/main" in remote_branches:
                branch_name = "main"
            elif "origin/master" in remote_branches:
                branch_name = "master"
            else:
                raise Exception("Neither 'origin/main' nor 'origin/master' found in repo")
        else:
            branch_name = ENVIRONMENT

        current_branch = conn.run("git rev-parse --abbrev-ref HEAD", hide=True).stdout.strip()
        print(f"=== Current branch: {current_branch} ===")

        if current_branch != branch_name:
            print(f"=== Stashing changes on branch {current_branch} ===")
            conn.run("git stash", warn=True)
            print(f"Switching to branch {branch_name}...")
            conn.run(f"git checkout {branch_name}")

        if GIT_AUTH_METHOD == "ssh":
            conn.run(
                f"GIT_SSH_COMMAND='ssh -i /tmp/git_deploy_key -o StrictHostKeyChecking=no' git fetch origin && git reset --hard origin/{branch_name}"
            )
        else:
            conn.run(f"git fetch origin && git reset --hard origin/{branch_name}")

    print(f"=== Repository cloned & checked out to {branch_name} branch =======")


def docker_login(conn, registry_type=None):
    """
    Login to Docker registry based on registry_type
    """

    if not registry_type:
        print("No registry type provided, skipping Docker login.")
        return

    registry_type = registry_type.lower()

    if registry_type == "ghcr":
        username = GIT_USER
        password = GIT_TOKEN
        if not username or not password:
            raise ValueError("GIT_USER and GIT_TOKEN must be set for GHCR")
        print("Logging in to GHCR...")
        conn.run(f"echo '{password}' | docker login ghcr.io -u {username} --password-stdin")

    elif registry_type == "dockerhub":
        username = os.getenv("REGISTRY_USERNAME")
        password = os.getenv("REGISTRY_PASSWORD")
        if not username or not password:
            raise ValueError("REGISTRY_USERNAME and REGISTRY_PASSWORD must be set")
        print("Logging in to Docker Hub...")
        conn.run(f"echo '{password}' | docker login -u {username} --password-stdin")

    elif registry_type == "ecr":
        aws_region = os.getenv("AWS_REGION")
        aws_account_id = os.getenv("AWS_ACCOUNT_ID")
        if not aws_region or not aws_account_id:
            raise ValueError("AWS_REGION and AWS_ACCOUNT_ID must be set for ECR login.")
        print("Logging in to AWS ECR...")
        cmd = (
            f"aws ecr get-login-password --region {aws_region} | "
            f"docker login --username AWS --password-stdin {aws_account_id}.dkr.ecr.{aws_region}.amazonaws.com"
        )
        conn.run(cmd)

    else:
        raise ValueError(f"Unsupported registry_type: {registry_type}")


def deploy_baremetal(conn):
    """
    Deploy directly to server without Docker/K8s
    """

    with conn.cd(GIT_SUBDIR):
        if DEPLOY_COMMAND:
            print(f"======= Running deploy command: {DEPLOY_COMMAND} =======")
            run_command(conn, DEPLOY_COMMAND)
        else:
            # Check for deploy.sh first
            deploy_script_check = conn.run(
                "test -f deploy.sh && echo 'exists' || echo 'not exists'",
                hide=True,
            )
            if "exists" in deploy_script_check.stdout:
                print("======= Running deploy.sh =======")
                conn.run("chmod +x deploy.sh")
                run_command(conn, "./deploy.sh")
            else:
                # Check if Makefile exists
                makefile_check = conn.run(
                    "test -f Makefile && echo 'exists' || echo 'not exists'",
                    hide=True,
                )
                if "exists" in makefile_check.stdout:
                    print(f"======= Running make target: {ENVIRONMENT} =======")
                    run_command(conn, f"make {ENVIRONMENT}")
                else:
                    raise ValueError(
                        "No deploy_command specified and no deploy.sh or Makefile found. "
                        "Please specify deploy_command input."
                    )
    print("======= Baremetal deployment completed =======")


def detect_database_type(conn):
    """
    Detect which database is being used in the deployment
    Returns a list of detected database types (e.g., ['postgres', 'mariadb'])
    """
    databases = []
    with conn.cd(GIT_SUBDIR):
        db_patterns = {
            "postgres": ["postgres", "postgresql", "postgres:"],
            "mariadb": ["mariadb", "mariadb:"],
            "mysql": ["mysql", "mysql:"],
            "mongodb": ["mongo", "mongodb", "mongo:"],
            "redis": ["redis", "redis:"],
        }

        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]
        for compose_file in compose_files:
            check = conn.run(
                f"test -f {compose_file} && echo 'exists' || echo 'not exists'",
                hide=True,
                warn=True,
            )
            if "exists" in check.stdout:
                for db_type, patterns in db_patterns.items():
                    if db_type in databases:
                        continue
                    for pattern in patterns:
                        result = conn.run(
                            f"grep -i '{pattern}' {compose_file} 2>/dev/null | head -1 || true",
                            hide=True,
                            warn=True,
                        )
                        if result.stdout.strip():
                            databases.append(db_type)
                            break

        # Check k8s manifests
        if DEPLOYMENT_TYPE == "k8s":
            manifest_paths = ["k8s", "manifests", "kubernetes"]
            for path in manifest_paths:
                check = conn.run(
                    f"test -d {path} && echo 'exists' || echo 'not exists'",
                    hide=True,
                    warn=True,
                )
                if "exists" in check.stdout:
                    for db_type, patterns in db_patterns.items():
                        if db_type in databases:
                            continue
                        for pattern in patterns:
                            result = conn.run(
                                f"grep -ri '{pattern}' {path}/ 2>/dev/null | head -1 || true",
                                hide=True,
                                warn=True,
                            )
                            if result.stdout.strip():
                                databases.append(db_type)
                                break

    return databases


def get_database_volume_paths(conn, db_type):
    """
    Extract actual volume paths from docker-compose files for a given database type
    Returns a list of paths that need permission fixes
    """
    paths = []
    with conn.cd(GIT_SUBDIR):
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]

        for compose_file in compose_files:
            check = conn.run(
                f"test -f {compose_file} && echo 'exists' || echo 'not exists'",
                hide=True,
                warn=True,
            )
            if "exists" not in check.stdout:
                continue

            # Look for volume mounts that contain the database type in the path
            # Match patterns like: - ./data/postgres:/var/lib/postgresql/data
            # or: - ./postgres_data:/var/lib/postgresql/data
            volume_result = conn.run(
                f"grep -iE '\\s+-\\s+.*{db_type}.*:/' {compose_file} 2>/dev/null || true",
                hide=True,
                warn=True,
            )

            for line in volume_result.stdout.strip().split("\n"):
                line = line.strip()
                if ":/" in line:
                    parts = line.split(":/")
                    if len(parts) > 0:
                        local_path = parts[0].strip().lstrip("-").strip()
                        if local_path and (
                            local_path.startswith("./") or local_path.startswith("/")
                        ):
                            if local_path not in paths:
                                paths.append(local_path)

    return paths


def fix_database_permissions(conn):
    """
    Fix database data directory permissions dynamically based on detected database types
    Supports: PostgreSQL, MariaDB, MySQL, MongoDB, Redis
    Detects actual volume paths from docker-compose files
    """
    databases = detect_database_type(conn)
    if not databases:
        return

    db_configs = {
        "postgres": ("postgres", "999", "999", "700"),
        "mariadb": ("mariadb", "999", "999", "750"),
        "mysql": ("mysql", "999", "999", "750"),
        "mongodb": ("mongodb", "999", "999", "755"),
        "redis": ("redis", "999", "999", "755"),
    }

    with conn.cd(GIT_SUBDIR):
        for db_type in databases:
            if db_type not in db_configs:
                continue

            dir_name, user_id, group_id, perms = db_configs[db_type]

            volume_paths = get_database_volume_paths(conn, db_type)

            # Also check for existing directories that match the pattern
            existing_dirs = conn.run(
                f"find . -type d -name '*{dir_name}*' -path '*/data/*' -o -type d -name '*{dir_name}*' -path '*/volumes/*' 2>/dev/null | head -10 || true",
                hide=True,
                warn=True,
            )
            for existing_dir in existing_dirs.stdout.strip().split("\n"):
                if existing_dir.strip() and existing_dir.strip() not in volume_paths:
                    volume_paths.append(existing_dir.strip())

            # Only fix permissions if paths were found
            if not volume_paths:
                continue

            print(f"======= Fixing {db_type.upper()} data directory permissions =======")

            for path in volume_paths:
                if not path.strip():
                    continue

                normalized_path = path.lstrip("./")
                if not normalized_path.startswith("/"):
                    full_path = f"./{normalized_path}"
                else:
                    full_path = normalized_path

                run_command(
                    conn,
                    f"""
                    bash -c '
                        mkdir -p {full_path} || true &&
                        chown -R {user_id}:{group_id} {full_path} || true &&
                        chmod -R {perms} {full_path} || true
                    '
                    """.strip(),
                )


def deploy_docker(conn):
    """
    Deploy using Docker Compose
    """

    with conn.cd(GIT_SUBDIR):
        docker_login(conn, registry_type=REGISTRY_TYPE)

        if PROFILE:
            print(f"======= Deploying with Docker Compose profile: {PROFILE} =======")
            run_command(
                conn,
                f"docker compose --profile {PROFILE} up --build -d",
            )
        else:
            print("======= Deploying with Docker Compose =======")
            run_command(conn, "docker compose up --build -d")

        # run_command(conn, "docker image prune -f")

    print("======= Docker deployment completed =======")


def deploy_k8s(conn):
    """
    Deploy using Kubernetes
    """

    with conn.cd(GIT_SUBDIR):
        docker_login(conn, registry_type=REGISTRY_TYPE)

        # Find manifest path
        manifest_path = K8S_MANIFEST_PATH
        if not manifest_path:
            # Try common paths
            for path in ["k8s", "manifests", "kubernetes"]:
                check = conn.run(
                    f"test -d {path} && echo 'exists' || echo 'not exists'",
                    hide=True,
                )
                if "exists" in check.stdout:
                    manifest_path = path
                    break

            if not manifest_path:
                # Check for single manifest file
                for file in [
                    "k8s.yaml",
                    "k8s.yml",
                    "deployment.yaml",
                    "deployment.yml",
                ]:
                    check = conn.run(
                        f"test -f {file} && echo 'exists' || echo 'not exists'",
                        hide=True,
                    )
                    if "exists" in check.stdout:
                        manifest_path = file
                        break

        if not manifest_path:
            raise ValueError(
                "No k8s_manifest_path specified and no k8s manifests found. "
                "Please specify k8s_manifest_path input or create k8s/, manifests/, or kubernetes/ directory."
            )

        print(f"======= Deploying to Kubernetes using: {manifest_path} =======")

        # Set KUBECONFIG
        kubeconfig_cmd = "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"

        # Create namespace if it doesn't exist
        conn.run(
            f"{kubeconfig_cmd} && kubectl create namespace {K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -"
        )

        # Apply manifests
        if conn.run(f"test -d {manifest_path}", warn=True, hide=True).ok:
            conn.run(f"{kubeconfig_cmd} && kubectl apply -f {manifest_path}/ -n {K8S_NAMESPACE}")
        else:
            conn.run(f"{kubeconfig_cmd} && kubectl apply -f {manifest_path} -n {K8S_NAMESPACE}")

    print("======= Kubernetes deployment completed =======")


def deploy(conn):
    """
    Main deploy function that routes to the appropriate deployment method
    """

    fix_database_permissions(conn)

    if DEPLOYMENT_TYPE == "baremetal":
        deploy_baremetal(conn)
    elif DEPLOYMENT_TYPE == "docker":
        deploy_docker(conn)
    elif DEPLOYMENT_TYPE == "k8s":
        deploy_k8s(conn)
    else:
        raise ValueError(
            f"Invalid deployment_type: {DEPLOYMENT_TYPE}. Must be 'baremetal', 'docker', or 'k8s'"
        )


def handle_connection():
    """
    Handle the SSH connection and orchestrate the deployment
    """

    # Setup SSH key and Git authentication first
    setup_ssh_key()
    setup_git_auth()

    conn_kwargs = {
        "host": REMOTE_HOST,
        "user": REMOTE_USER,
    }

    if REMOTE_PASSWORD:
        conn_kwargs["connect_kwargs"] = {
            "password": REMOTE_PASSWORD,
            "look_for_keys": False,
            "allow_agent": False,
        }
    elif SSH_KEY_PATH:
        conn_kwargs["connect_kwargs"] = {"key_filename": SSH_KEY_PATH}

    conn = Connection(**conn_kwargs)

    result = conn.run("hostname", hide=True)
    hostname = result.stdout.strip()
    print(f"======= Connected to {conn_kwargs.get('host')}, " f"hostname: {hostname} =======")

    # Set output for GitHub Actions
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.getenv("GITHUB_OUTPUT"), "a") as f:
            f.write(f"remote_hostname={hostname}\n")

    install_dependencies(conn)

    if DEPLOYMENT_TYPE in ["docker", "k8s"]:
        install_docker(conn)

    if DEPLOYMENT_TYPE == "k8s":
        install_kubectl(conn)
        install_helm(conn)
        install_k3s(conn)

    clone_repo(conn)
    deploy(conn)

    # Set deployment status
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.getenv("GITHUB_OUTPUT"), "a") as f:
            f.write("deployment_status=success\n")

    # Cleanup SSH key files
    if SSH_KEY_PATH and os.path.exists(SSH_KEY_PATH):
        try:
            os.unlink(SSH_KEY_PATH)
        except OSError:
            pass  # Ignore errors during cleanup
    if GIT_SSH_KEY_PATH and os.path.exists(GIT_SSH_KEY_PATH):
        try:
            os.unlink(GIT_SSH_KEY_PATH)
        except OSError:
            pass  # Ignore errors during cleanup


if __name__ == "__main__":
    try:
        handle_connection()
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        if os.getenv("GITHUB_OUTPUT"):
            with open(os.getenv("GITHUB_OUTPUT"), "a") as f:
                f.write("deployment_status=failed\n")
        raise
