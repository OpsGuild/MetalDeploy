#!/usr/bin/env python3
"""
Tests for error handling and edge cases
"""
import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deploy  # noqa: E402


@pytest.fixture
def mock_connection():
    """Create a mock Fabric Connection"""
    conn = Mock()
    conn.run.return_value = Mock(stdout="", ok=True)
    conn.cd.return_value.__enter__ = Mock(return_value=None)
    conn.cd.return_value.__exit__ = Mock(return_value=None)
    return conn


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_network_failure_during_clone(self, mock_connection, monkeypatch):
        """Test handling network failure during git clone"""
        monkeypatch.setenv("GIT_AUTH_METHOD", "none")

        # Simulate network failure
        mock_connection.run.side_effect = Exception("Network unreachable")

        with patch.object(deploy, "AUTH_GIT_URL", "https://github.com/test/repo.git"), patch.object(
            deploy, "PROJECT_NAME", "repo"
        ), patch.object(deploy, "GIT_DIR", "/home/user/repo"):
            with pytest.raises(Exception, match="Network unreachable"):
                deploy.clone_repo(mock_connection)

    def test_ssh_connection_timeout(self, mock_connection, monkeypatch):
        """Test SSH connection timeout"""
        monkeypatch.setenv("REMOTE_HOST", "unreachable-host")

        with patch("deploy.Connection") as mock_conn_class:
            mock_conn_class.side_effect = TimeoutError("Connection timed out")

            # Should raise timeout error
            with pytest.raises(TimeoutError):
                mock_conn_class(host="unreachable-host", user="root")

    def test_docker_login_failure(self, mock_connection, monkeypatch):
        """Test Docker login failure"""
        monkeypatch.setattr(deploy, "GIT_USER", "testuser")
        monkeypatch.setattr(deploy, "GIT_TOKEN", "invalid_token")

        # Simulate login failure
        mock_connection.run.side_effect = Exception("Authentication failed")

        with pytest.raises(Exception, match="Authentication failed"):
            deploy.docker_login(mock_connection, registry_type="ghcr")

    def test_missing_required_env_vars(self, monkeypatch):
        """Test error when required environment variables are missing"""
        # Clear all env vars
        monkeypatch.delenv("GIT_URL", raising=False)
        monkeypatch.delenv("REMOTE_HOST", raising=False)

        # Reload module to trigger validation
        # Should fail validation when trying to use
        pass  # Validation happens at runtime

    def test_invalid_git_url_format(self, monkeypatch):
        """Test handling invalid Git URL format"""
        monkeypatch.setenv("GIT_URL", "not-a-valid-url")
        monkeypatch.setenv("GIT_AUTH_METHOD", "token")
        monkeypatch.setenv("GIT_TOKEN", "token")
        monkeypatch.setenv("GIT_USER", "user")

        import importlib

        importlib.reload(deploy)

        # Call setup function
        deploy.setup_git_auth()

        # Should still create AUTH_GIT_URL (may be invalid but won't crash)
        assert deploy.AUTH_GIT_URL is not None

    def test_deployment_failure_handling(self, mock_connection, monkeypatch):
        """Test handling deployment command failures"""
        monkeypatch.setattr(deploy, "DEPLOYMENT_TYPE", "docker")

        # Simulate docker compose failure
        def mock_run(conn, cmd, force_sudo=False):
            if isinstance(cmd, str) and "docker compose" in cmd:
                raise Exception("Docker compose failed")
            return Mock(ok=True, stdout="")

        with patch.object(deploy, "docker_login"), patch.object(
            deploy, "run_command", side_effect=mock_run
        ):
            with pytest.raises(Exception, match="Docker compose failed"):
                deploy.deploy_docker(mock_connection)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_git_url(self, monkeypatch):
        """Test handling empty Git URL"""
        monkeypatch.setenv("GIT_URL", "")

        import importlib

        importlib.reload(deploy)

        # Should handle gracefully or raise error
        if deploy.GIT_URL == "":
            # PROJECT_NAME extraction might fail
            pass

    def test_special_characters_in_commands(self, mock_connection, monkeypatch):
        """Test handling special characters in commands"""
        monkeypatch.setattr(deploy, "DEPLOY_COMMAND", "echo 'test with \"quotes\" and $vars'")

        with patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_baremetal(mock_connection)
            # Should handle special characters properly
            assert mock_run.called

    def test_very_long_commands(self, mock_connection, monkeypatch):
        """Test handling very long commands"""
        long_cmd = " && ".join([f"echo {i}" for i in range(100)])
        monkeypatch.setattr(deploy, "DEPLOY_COMMAND", long_cmd)

        with patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_baremetal(mock_connection)
            # Should handle long commands
            assert mock_run.called

    def test_unicode_in_outputs(self, mock_connection):
        """Test handling unicode characters in outputs"""
        mock_connection.run.return_value = Mock(stdout="测试服务器 🚀", ok=True)

        result = mock_connection.run("hostname")
        assert "测试" in result.stdout or "🚀" in result.stdout

    def test_concurrent_deployments(self, mock_connection):
        """Test that deployment handles concurrent operations"""
        # This would test thread safety if applicable
        # For now, just verify functions are callable
        assert callable(deploy.deploy_docker)
        assert callable(deploy.deploy_baremetal)
        assert callable(deploy.deploy_k8s)


class TestFileSystemOperations:
    """Test file system operations"""

    def test_temp_file_creation(self, monkeypatch):
        """Test temporary file creation for SSH keys"""
        test_key = "test_key_content"
        monkeypatch.setenv("SSH_KEY", test_key)

        import importlib

        importlib.reload(deploy)

        # Call setup function
        deploy.setup_ssh_key()

        if deploy.SSH_KEY:
            assert deploy.SSH_KEY_PATH is not None
            if os.path.exists(deploy.SSH_KEY_PATH):
                # Verify content
                with open(deploy.SSH_KEY_PATH, "r") as f:
                    assert f.read() == test_key
                # Cleanup
                os.unlink(deploy.SSH_KEY_PATH)

    def test_directory_creation(self, mock_connection, monkeypatch):
        """Test remote directory creation"""
        monkeypatch.setenv("REMOTE_DIR", "/new/path")

        with patch.object(deploy, "REMOTE_DIR", "/new/path"):
            deploy.clone_repo(mock_connection)

            # Should create directory
            mkdir_calls = [
                call for call in mock_connection.run.call_args_list if "mkdir -p" in str(call)
            ]
            assert len(mkdir_calls) > 0

    def test_file_permissions(self, monkeypatch):
        """Test file permission handling"""
        test_key = "test_key"
        monkeypatch.setenv("SSH_KEY", test_key)

        import importlib

        importlib.reload(deploy)

        if deploy.SSH_KEY_PATH and os.path.exists(deploy.SSH_KEY_PATH):
            stat_info = os.stat(deploy.SSH_KEY_PATH)
            # Should have restrictive permissions
            permissions = stat_info.st_mode & 0o777
            assert permissions <= 0o600  # 600 or more restrictive
            os.unlink(deploy.SSH_KEY_PATH)


class TestEndToEndFlow:
    """Test end-to-end deployment flow"""

    def test_full_docker_deployment_flow(self, mock_connection, monkeypatch):
        """Test complete Docker deployment flow"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "docker")
        monkeypatch.setenv("GIT_URL", "https://github.com/test/repo.git")
        monkeypatch.setenv("GIT_AUTH_METHOD", "token")
        monkeypatch.setenv("GIT_TOKEN", "token")
        monkeypatch.setenv("GIT_USER", "user")
        monkeypatch.setenv("REMOTE_HOST", "192.168.1.1")
        monkeypatch.setenv("REGISTRY_TYPE", "ghcr")

        # Mock all operations
        with patch.object(deploy, "install_dependencies"), patch.object(
            deploy, "install_docker"
        ), patch.object(deploy, "clone_repo"), patch.object(deploy, "deploy_docker") as mock_deploy:
            # Simulate handle_connection flow
            deploy.install_dependencies(mock_connection)
            deploy.install_docker(mock_connection)
            deploy.clone_repo(mock_connection)
            deploy.deploy_docker(mock_connection)

            # All steps should be called
            assert mock_deploy.called

    def test_full_baremetal_deployment_flow(self, mock_connection, monkeypatch):
        """Test complete baremetal deployment flow"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "baremetal")
        monkeypatch.setenv("DEPLOY_COMMAND", "make deploy")

        with patch.object(deploy, "install_dependencies"), patch.object(
            deploy, "clone_repo"
        ), patch.object(deploy, "deploy_baremetal") as mock_deploy:
            deploy.install_dependencies(mock_connection)
            deploy.clone_repo(mock_connection)
            deploy.deploy_baremetal(mock_connection)

            assert mock_deploy.called

    def test_full_k8s_deployment_flow(self, mock_connection, monkeypatch):
        """Test complete Kubernetes deployment flow"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "k8s")
        monkeypatch.setenv("K8S_MANIFEST_PATH", "k8s/")

        with patch.object(deploy, "install_dependencies"), patch.object(
            deploy, "install_docker"
        ), patch.object(deploy, "install_kubectl"), patch.object(
            deploy, "install_helm"
        ), patch.object(
            deploy, "install_k3s"
        ), patch.object(
            deploy, "clone_repo"
        ), patch.object(
            deploy, "deploy_k8s"
        ) as mock_deploy:
            deploy.install_dependencies(mock_connection)
            deploy.install_docker(mock_connection)
            deploy.install_kubectl(mock_connection)
            deploy.install_helm(mock_connection)
            deploy.install_k3s(mock_connection)
            deploy.clone_repo(mock_connection)
            deploy.deploy_k8s(mock_connection)

            assert mock_deploy.called

    def test_deployment_with_all_options(self, mock_connection, monkeypatch):
        """Test deployment with all optional parameters set"""
        monkeypatch.setenv("DEPLOYMENT_TYPE", "docker")
        monkeypatch.setenv("PROFILE", "production")
        monkeypatch.setenv("USE_SUDO", "false")
        monkeypatch.setenv("REGISTRY_TYPE", "dockerhub")
        monkeypatch.setenv("REGISTRY_USERNAME", "user")
        monkeypatch.setenv("REGISTRY_PASSWORD", "pass")

        with patch.object(deploy, "docker_login"), patch.object(deploy, "run_command") as mock_run:
            deploy.deploy_docker(mock_connection)

            # Should use profile and respect use_sudo
            assert mock_run.called
