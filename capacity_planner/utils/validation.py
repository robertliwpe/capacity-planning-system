"""Validation utilities."""

from pathlib import Path
from typing import Optional
import paramiko
import os

from ..models.data_models import SSHConfig, DataSource


def validate_ssh_config(ssh_config: SSHConfig) -> tuple[bool, Optional[str]]:
    """Validate SSH configuration.
    
    Args:
        ssh_config: SSH configuration to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ssh_config.hostname:
        return False, "Hostname is required"
    
    if not ssh_config.username:
        return False, "Username is required"
    
    if ssh_config.key_path:
        key_path = Path(ssh_config.key_path).expanduser()
        if not key_path.exists():
            return False, f"SSH key file not found: {ssh_config.key_path}"
        
        # Check if key file is readable
        try:
            with open(key_path, 'r') as f:
                content = f.read()
                if not any(header in content for header in ['BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY', 'BEGIN OPENSSH PRIVATE KEY']):
                    return False, "SSH key file does not appear to be a valid private key"
        except Exception as e:
            return False, f"Cannot read SSH key file: {e}"
    
    if ssh_config.port <= 0 or ssh_config.port > 65535:
        return False, "Port must be between 1 and 65535"
    
    return True, None


def validate_data_source(data_source: DataSource) -> tuple[bool, Optional[str]]:
    """Validate data source.
    
    Args:
        data_source: Data source to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if data_source.path:
        path = Path(data_source.path)
        if not path.exists():
            return False, f"File not found: {data_source.path}"
        
        if not path.is_file():
            return False, f"Path is not a file: {data_source.path}"
        
        # Check file extension matches type
        if data_source.type.value == "csv" and not path.suffix.lower() == ".csv":
            return False, "CSV data source must have .csv extension"
        
        if data_source.type.value == "pdf" and not path.suffix.lower() == ".pdf":
            return False, "PDF data source must have .pdf extension"
    
    if data_source.ssh_config:
        is_valid, error = validate_ssh_config(data_source.ssh_config)
        if not is_valid:
            return False, f"SSH configuration invalid: {error}"
    
    return True, None