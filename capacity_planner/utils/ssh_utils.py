"""SSH connection utilities."""

try:
    import paramiko
except ImportError:
    paramiko = None

import asyncio
import os
from typing import Optional, Tuple
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


class SSHConnection:
    """SSH connection handler."""
    
    def __init__(
        self,
        hostname: str,
        username: str,
        key_filename: Optional[str] = None,
        password: Optional[str] = None,
        port: int = 22,
        timeout: int = 30
    ):
        """Initialize SSH connection.
        
        Args:
            hostname: Remote hostname
            username: SSH username
            key_filename: Path to SSH private key
            password: SSH password (if not using key)
            port: SSH port
            timeout: Connection timeout in seconds
        """
        self.hostname = hostname
        self.username = username
        self.key_filename = key_filename
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Establish SSH connection.
        
        Returns:
            True if connection successful
        """
        if paramiko is None:
            raise ImportError("paramiko is required for SSH connections. Install with: pip install paramiko")
            
        async with self._lock:
            if self.client and self.client.get_transport() and self.client.get_transport().is_active():
                return True
            
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._connect_sync
                )
                
                logger.info(f"Connected to {self.hostname}:{self.port}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to {self.hostname}: {e}")
                self.client = None
                raise ConnectionError(f"SSH connection failed: {e}")
    
    def _connect_sync(self):
        """Synchronous connection method."""
        connect_kwargs = {
            "hostname": self.hostname,
            "username": self.username,
            "port": self.port,
            "timeout": self.timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }
        
        if self.key_filename and os.path.exists(os.path.expanduser(self.key_filename)):
            connect_kwargs["key_filename"] = os.path.expanduser(self.key_filename)
        elif self.password:
            connect_kwargs["password"] = self.password
            connect_kwargs["look_for_keys"] = False
        
        self.client.connect(**connect_kwargs)
    
    async def execute_command(self, command: str, timeout: Optional[int] = None) -> str:
        """Execute command on remote server.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Command output
        """
        if not self.client:
            await self.connect()
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            stdout, stderr = await loop.run_in_executor(
                None,
                self._execute_sync,
                command,
                timeout or self.timeout
            )
            
            if stderr and not stdout:
                raise RuntimeError(f"Command error: {stderr}")
            
            return stdout
            
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")
            raise RuntimeError(f"Command execution failed: {e}")
    
    def _execute_sync(self, command: str, timeout: int) -> Tuple[str, str]:
        """Synchronous command execution."""
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        
        # Wait for command to complete
        exit_status = stdout.channel.recv_exit_status()
        
        stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
        stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
        
        if exit_status != 0 and stderr_data:
            logger.warning(f"Command exited with status {exit_status}: {stderr_data}")
        
        return stdout_data, stderr_data
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote server.
        
        Args:
            remote_path: Remote file path
            local_path: Local file path
            
        Returns:
            True if download successful
        """
        if not self.client:
            await self.connect()
        
        try:
            # Ensure local directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._download_sync,
                remote_path,
                local_path
            )
            
            logger.info(f"Downloaded {remote_path} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            return False
    
    def _download_sync(self, remote_path: str, local_path: str):
        """Synchronous file download."""
        sftp = self.client.open_sftp()
        try:
            sftp.get(remote_path, local_path)
        finally:
            sftp.close()
    
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to remote server.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
            
        Returns:
            True if upload successful
        """
        if not self.client:
            await self.connect()
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._upload_sync,
                local_path,
                remote_path
            )
            
            logger.info(f"Uploaded {local_path} to {remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def _upload_sync(self, local_path: str, remote_path: str):
        """Synchronous file upload."""
        sftp = self.client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()
    
    async def close(self):
        """Close SSH connection."""
        async with self._lock:
            if self.client:
                try:
                    self.client.close()
                    logger.info(f"Closed connection to {self.hostname}")
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
                finally:
                    self.client = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()