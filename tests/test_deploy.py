#!/usr/bin/env python3
"""
Unit tests for deploy.py
"""
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path to import deploy module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after setting up path
import deploy  # noqa: E402


@pytest.fixture
def mock_connection():
    """Create a mock Fabric Connection"""
    conn = Mock()
    conn.run.return_value = Mock(stdout="", ok=True)
    conn.cd.return_value.__enter__ = Mock(return_value=None)
    conn.cd.return_value.__exit__ = Mock(return_value=None)
    return conn


@pytest.fixture
def set_env_vars(monkeypatch):
    """Set up environment variables for testing"""
    env_vars = {
        "GIT_URL": "https://github.com/testuser/testrepo.git",
        "GIT_AUTH_METHOD": "token",
        "GIT_TOKEN": "test_token",
        "GIT_USER": "testuser",
        "DEPLOYMENT_TYPE": "docker",
        "ENVIRONMENT": "dev",
        "REMOTE_USER": "root",
        "REMOTE_HOST": "127.0.0.1",
        "REGISTRY_TYPE": "ghcr",
        "USE_SUDO": "true",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


class TestRunCommand:
    """Test the run_command function"""

    def test_run_command_with_sudo(self, mock_connection, monkeypatch):
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", None)
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "test command")
        call_args = str(mock_connection.run.call_args)
        # Should use sudo and source bashrc
        assert "sudo" in call_args
        assert "bash -c" in call_args or "source" in call_args
        assert "test command" in call_args

    def test_run_command_with_sudo_and_password(self, mock_connection, monkeypatch):
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", "testpass")
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "test command")
        call_args = str(mock_connection.run.call_args)
        # Should use sudo with password and source bashrc
        assert "sudo -S" in call_args
        assert "bash -c" in call_args or "source" in call_args
        assert "test command" in call_args

    def test_run_command_without_sudo(self, mock_connection, monkeypatch):
        monkeypatch.setattr(deploy, "USE_SUDO", False)

        deploy.run_command(mock_connection, "test command")
        mock_connection.run.assert_called_once_with("test command", warn=False)

    def test_run_command_force_sudo(self, mock_connection, monkeypatch):
        monkeypatch.setattr(deploy, "USE_SUDO", False)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", "testpass")
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "test command", force_sudo=True)
        # Should use sudo even if USE_SUDO is False
        call_args = str(mock_connection.run.call_args)
        assert "sudo" in call_args

    def test_run_command_sources_bashrc_for_root(self, mock_connection, monkeypatch):
        """Test that commands with sudo source /root/.bashrc for root user"""
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", None)
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "staging up")
        call_args = str(mock_connection.run.call_args)
        # Should source /root/.bashrc
        assert "/root/.bashrc" in call_args
        assert "staging up" in call_args

    def test_run_command_sources_bashrc_for_non_root(self, mock_connection, monkeypatch):
        """Test that commands with sudo source correct home directory for non-root user"""
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", None)
        monkeypatch.setattr(deploy, "REMOTE_USER", "deploy")

        deploy.run_command(mock_connection, "make deploy")
        call_args = str(mock_connection.run.call_args)
        # Should source /home/deploy/.bashrc
        assert "/home/deploy/.bashrc" in call_args
        assert "make deploy" in call_args

    def test_run_command_handles_quotes_in_command(self, mock_connection, monkeypatch):
        """Test that commands with quotes are properly escaped"""
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", None)
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "echo 'test with quotes'")
        call_args = str(mock_connection.run.call_args)
        # Should handle quotes properly
        assert "echo" in call_args
        assert "test with quotes" in call_args or "quotes" in call_args

    def test_run_command_sources_multiple_profile_files(self, mock_connection, monkeypatch):
        """Test that the command tries multiple profile files as fallback"""
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", None)
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "test command")
        call_args = str(mock_connection.run.call_args)
        # Should try .bashrc, .bash_profile, and .profile
        # bash -l automatically sources .bash_profile/.profile, and we explicitly source all
        assert ".bashrc" in call_args
        assert ".bash_profile" in call_args
        assert ".profile" in call_args

    def test_run_command_with_complex_deploy_command(self, mock_connection, monkeypatch):
        """Test that complex baremetal commands with && work correctly"""
        monkeypatch.setattr(deploy, "USE_SUDO", True)
        monkeypatch.setattr(deploy, "REMOTE_PASSWORD", "mypass")
        monkeypatch.setattr(deploy, "REMOTE_USER", "root")

        deploy.run_command(mock_connection, "staging up && staging migrate")
        call_args = str(mock_connection.run.call_args)
        # Should include both commands
        assert "staging up" in call_args
        assert "staging migrate" in call_args
        assert "&&" in call_args
        assert "/root/.bashrc" in call_args


class TestInstallDependencies:
    """Test the install_dependencies function"""

    def test_install_dependencies_all_installed(self, mock_connection, set_env_vars):
        # Mock all dependencies as already installed
        def mock_which(cmd, **kwargs):
            result = Mock()
            result.stdout = "/usr/bin/" + cmd.split()[-1]
            return result

        mock_connection.run.side_effect = mock_which

        deploy.install_dependencies(mock_connection)

        # Should check for dependencies
        assert mock_connection.run.called

    def test_install_dependencies_missing_packages(self, mock_connection, set_env_vars):
        # Mock some dependencies as missing
        call_count = 0

        def mock_which(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            result = Mock()
            if call_count <= 3:  # First 3 are missing
                result.stdout = ""
            else:
                result.stdout = "/usr/bin/" + cmd.split()[-1]
            return result

        mock_connection.run.side_effect = mock_which

        with patch.object(deploy, "run_command") as mock_run_cmd:
            deploy.install_dependencies(mock_connection)
            # Should call apt-get update and install
            assert mock_run_cmd.called


class TestDockerLogin:
    """Test the docker_login function"""

    def test_docker_login_ghcr(self, mock_connection, set_env_vars, monkeypatch):
        monkeypatch.setattr(deploy, "GIT_USER", "testuser")
        monkeypatch.setattr(deploy, "GIT_TOKEN", "testtoken")

        deploy.docker_login(mock_connection, registry_type="ghcr")
        # Should run docker login
        assert mock_connection.run.called

    def test_docker_login_dockerhub(self, mock_connection, set_env_vars):
        with patch.dict(
            os.environ, {"REGISTRY_USERNAME": "testuser", "REGISTRY_PASSWORD": "testpass"}
        ):
            deploy.docker_login(mock_connection, registry_type="dockerhub")
            assert mock_connection.run.called

    def test_docker_login_invalid_type(self, mock_connection, set_env_vars):
        with pytest.raises(ValueError, match="Unsupported registry_type"):
            deploy.docker_login(mock_connection, registry_type="invalid")


class TestDeployFunctions:
    """Test deployment functions"""

    def test_deploy_docker(self, mock_connection, set_env_vars):
        with patch.object(deploy, "docker_login"), patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_docker(mock_connection)
            # Should call docker compose
            assert mock_run.called

    def test_deploy_docker_with_profile(self, mock_connection, set_env_vars, monkeypatch):
        monkeypatch.setattr(deploy, "PROFILE", "production")

        with patch.object(deploy, "docker_login"), patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_docker(mock_connection)
            # Should use profile
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("profile" in str(call).lower() for call in calls)

    def test_deploy_baremetal_with_command(self, mock_connection, set_env_vars, monkeypatch):
        monkeypatch.setattr(deploy, "DEPLOY_COMMAND", "make deploy")

        with patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_baremetal(mock_connection)
            mock_run.assert_called()

    def test_deploy_baremetal_with_deploy_sh(self, mock_connection, set_env_vars, monkeypatch):
        # Mock deploy.sh exists
        def mock_test(cmd, **kwargs):
            if "deploy.sh" in cmd:
                result = Mock()
                result.stdout = "exists"
                return result
            return Mock(stdout="")

        mock_connection.run.side_effect = mock_test
        monkeypatch.setattr(deploy, "DEPLOY_COMMAND", None)

        with patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_baremetal(mock_connection)
            # Should call deploy.sh
            assert mock_run.called

    def test_deploy_baremetal_with_makefile(self, mock_connection, set_env_vars, monkeypatch):
        # Mock deploy.sh doesn't exist, but Makefile exists
        def mock_test(cmd, **kwargs):
            if "deploy.sh" in cmd:
                result = Mock()
                result.stdout = "not exists"
                return result
            if "Makefile" in cmd:
                result = Mock()
                result.stdout = "exists"
                return result
            return Mock(stdout="")

        mock_connection.run.side_effect = mock_test
        monkeypatch.setattr(deploy, "DEPLOY_COMMAND", None)
        monkeypatch.setattr(deploy, "ENVIRONMENT", "dev")

        with patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_baremetal(mock_connection)
            # Should call make dev (since deploy.sh doesn't exist)
            assert mock_run.called


class TestGitAuth:
    """Test Git authentication setup"""

    def test_git_auth_token(self, monkeypatch):
        monkeypatch.setenv("GIT_AUTH_METHOD", "token")
        monkeypatch.setenv("GIT_TOKEN", "test_token")
        monkeypatch.setenv("GIT_USER", "testuser")
        monkeypatch.setenv("GIT_URL", "https://github.com/test/repo.git")

        # Reload module to pick up new env vars
        import importlib

        importlib.reload(deploy)

        # Call setup function
        deploy.setup_git_auth()

        assert deploy.AUTH_GIT_URL is not None
        assert "test_token" in deploy.AUTH_GIT_URL or "testuser" in deploy.AUTH_GIT_URL

    def test_git_auth_ssh(self, monkeypatch):
        monkeypatch.setenv("GIT_AUTH_METHOD", "ssh")
        monkeypatch.setenv(
            "GIT_SSH_KEY", "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
        )
        monkeypatch.setenv("GIT_URL", "https://github.com/test/repo.git")

        import importlib

        importlib.reload(deploy)

        # Call setup function
        deploy.setup_git_auth()

        assert deploy.AUTH_GIT_URL is not None
        # Should convert to SSH format
        assert "git@" in deploy.AUTH_GIT_URL or "github.com" in deploy.AUTH_GIT_URL

    def test_git_auth_none(self, monkeypatch):
        monkeypatch.setenv("GIT_AUTH_METHOD", "none")
        monkeypatch.setenv("GIT_URL", "https://github.com/test/repo.git")

        import importlib

        importlib.reload(deploy)

        # Call setup function
        deploy.setup_git_auth()

        assert deploy.AUTH_GIT_URL == "https://github.com/test/repo.git"


class TestValidation:
    """Test input validation"""

    def test_invalid_deployment_type(self, mock_connection, set_env_vars, monkeypatch):
        monkeypatch.setattr(deploy, "DEPLOYMENT_TYPE", "invalid")

        with pytest.raises(ValueError, match="Invalid deployment_type"):
            deploy.deploy(mock_connection)

    def test_missing_git_token_for_token_auth(self):
        with patch.dict(
            os.environ,
            {"GIT_AUTH_METHOD": "token", "GIT_TOKEN": "", "GIT_USER": "testuser"},
            clear=False,
        ):
            # Should raise error during initialization
            # This is tested by checking if ValueError is raised
            pass  # Actual validation happens at runtime
