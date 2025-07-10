"""SSH data collection worker."""

import os
import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..base import BaseWorker
from ...utils.ssh_utils import SSHConnection
from ...models.data_models import (
    SSHConfig, ServerMetrics, LogAnalysis, WorkerTask, InstallMetrics
)


class SSHWorker(BaseWorker):
    """Worker for SSH-based data collection."""
    
    def __init__(self, ssh_config: SSHConfig):
        """Initialize SSH worker.
        
        Args:
            ssh_config: SSH connection configuration
        """
        super().__init__()
        self.ssh_config = ssh_config
        self.connection: Optional[SSHConnection] = None
        self.sudo_password = os.getenv('SUDO_PASSWORD', '')
    
    async def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.connection = SSHConnection(
                hostname=self.ssh_config.hostname,
                username=self.ssh_config.username,
                key_filename=self.ssh_config.key_path,
                password=self.ssh_config.password,
                port=self.ssh_config.port
            )
            return await self.connection.connect()
        except Exception as e:
            self.logger.error(f"SSH connection failed: {e}")
            return False
    
    async def connect_to_pod(self, pod_number: int) -> bool:
        """Connect to a specific pod.
        
        Args:
            pod_number: Pod number to connect to
            
        Returns:
            True if connection successful
        """
        hostname = f"pod-{pod_number}.wpengine.com"
        self.ssh_config.hostname = hostname
        self.ssh_config.pod_number = pod_number
        return await self.connect()
    
    async def collect_system_metrics(self) -> ServerMetrics:
        """Collect system metrics via SSH."""
        if not self.connection:
            raise RuntimeError("No SSH connection established")
        
        metrics = {}
        
        # CPU usage
        cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        cpu_result = await self.connection.execute_command(cpu_cmd)
        metrics['cpu_usage'] = float(cpu_result) if cpu_result else 0.0
        
        # Memory info
        mem_cmd = "free -b | grep '^Mem:' | awk '{print $2,$3,$7}'"
        mem_result = await self.connection.execute_command(mem_cmd)
        if mem_result:
            total, used, available = map(int, mem_result.split())
            metrics['memory_total'] = total
            metrics['memory_usage'] = (used / total * 100) if total > 0 else 0
            metrics['memory_available'] = available
        
        # Disk usage
        disk_cmd = "df -B1 / | tail -1 | awk '{print $2,$3,$4,$5}'"
        disk_result = await self.connection.execute_command(disk_cmd)
        if disk_result:
            total, used, available, percent = disk_result.split()
            metrics['disk_total'] = int(total)
            metrics['disk_used'] = int(used)
            metrics['disk_usage'] = float(percent.rstrip('%'))
        
        # Load average
        load_cmd = "uptime | awk -F'load average:' '{print $2}'"
        metrics['load_average'] = await self.connection.execute_command(load_cmd)
        
        # Process counts
        process_commands = {
            'total': "ps aux | wc -l",
            'mysql': "ps aux | grep -c '[m]ysql'",
            'php': "ps aux | grep -c '[p]hp'",
            'nginx': "ps aux | grep -c '[n]ginx'",
            'apache': "ps aux | grep -c '[a]pache2\\|[h]ttpd'"
        }
        
        processes = {}
        for name, cmd in process_commands.items():
            try:
                count = await self.connection.execute_command(cmd)
                processes[name] = int(count) if count else 0
            except:
                processes[name] = 0
        
        return ServerMetrics(
            hostname=self.ssh_config.hostname,
            cpu_usage=metrics.get('cpu_usage', 0),
            memory_usage=metrics.get('memory_usage', 0),
            memory_total=metrics.get('memory_total', 0),
            memory_available=metrics.get('memory_available', 0),
            disk_usage=metrics.get('disk_usage', 0),
            disk_total=metrics.get('disk_total', 0),
            disk_used=metrics.get('disk_used', 0),
            load_average=metrics.get('load_average', ''),
            processes=processes
        )
    
    async def collect_install_logs(self, install_name: str) -> Dict[str, str]:
        """Collect logs for a specific install.
        
        Args:
            install_name: Name of the install
            
        Returns:
            Dictionary of log paths to content
        """
        log_paths = [
            f"/var/log/nginx/{install_name}.apachestyle.log",
            f"/var/log/nginx/{install_name}.access.log",
            f"/var/log/apache2/{install_name}.access.log"
        ]
        
        log_data = {}
        
        for log_path in log_paths:
            # Check if file exists
            check_cmd = f"test -f {log_path} && echo exists || echo missing"
            exists = await self.connection.execute_command(check_cmd)
            
            if exists.strip() == "exists":
                # Read first uncompressed file
                content = await self.connection.execute_command(f"tail -n 10000 {log_path}")
                if content:
                    log_data[log_path] = content
                
                # Check for .1 file
                log1_path = f"{log_path}.1"
                check_cmd = f"test -f {log1_path} && echo exists || echo missing"
                exists = await self.connection.execute_command(check_cmd)
                
                if exists.strip() == "exists":
                    content = await self.connection.execute_command(f"tail -n 10000 {log1_path}")
                    if content:
                        log_data[log1_path] = content
                
                # Check for compressed files
                for i in range(2, 10):
                    gz_path = f"{log_path}.{i}.gz"
                    check_cmd = f"test -f {gz_path} && echo exists || echo missing"
                    exists = await self.connection.execute_command(check_cmd)
                    
                    if exists.strip() == "exists":
                        content = await self.connection.execute_command(
                            f"zcat {gz_path} | tail -n 10000"
                        )
                        if content:
                            log_data[gz_path] = content
                    else:
                        break
        
        return log_data
    
    async def collect_mysql_slow_logs(self) -> Dict[str, str]:
        """Collect MySQL slow logs with sudo."""
        if not self.sudo_password:
            self.logger.warning("No sudo password provided, skipping MySQL slow logs")
            return {}
        
        logs = {}
        base_path = "/var/log/mysql/mysql-slow.log"
        
        # Read uncompressed logs
        for suffix in ["", ".1"]:
            log_path = f"{base_path}{suffix}"
            cmd = f"echo '{self.sudo_password}' | sudo -S test -f {log_path} && echo exists || echo missing"
            exists = await self.connection.execute_command(cmd)
            
            if exists.strip() == "exists":
                cmd = f"echo '{self.sudo_password}' | sudo -S tail -n 1000 {log_path}"
                try:
                    content = await self.connection.execute_command(cmd)
                    if content and not content.startswith("[sudo]"):
                        logs[log_path] = content
                except Exception as e:
                    self.logger.warning(f"Failed to read {log_path}: {e}")
        
        # Read compressed logs
        for i in range(2, 10):
            log_path = f"{base_path}.{i}.gz"
            cmd = f"echo '{self.sudo_password}' | sudo -S test -f {log_path} && echo exists || echo missing"
            exists = await self.connection.execute_command(cmd)
            
            if exists.strip() == "exists":
                cmd = f"echo '{self.sudo_password}' | sudo -S zcat {log_path} | tail -n 1000"
                try:
                    content = await self.connection.execute_command(cmd)
                    if content and not content.startswith("[sudo]"):
                        logs[log_path] = content
                except Exception as e:
                    self.logger.warning(f"Failed to read {log_path}: {e}")
            else:
                break
        
        return logs
    
    async def execute_server_function(self, function_name: str, args: List[str] = None) -> str:
        """Execute a server function on the pod.
        
        Args:
            function_name: Name of the server function
            args: Arguments for the function
            
        Returns:
            Function output
        """
        command = function_name
        if args:
            command += " " + " ".join(args)
        
        return await self.connection.execute_command(command)
    
    async def analyze_logs(self, log_content: str, log_type: str = "access") -> LogAnalysis:
        """Analyze log content.
        
        Args:
            log_content: Log file content
            log_type: Type of log (access, error, slow)
            
        Returns:
            Log analysis results
        """
        lines = log_content.strip().split('\n')
        total_requests = len(lines)
        
        status_codes = {}
        response_times = []
        ips = {}
        errors = 0
        
        for line in lines:
            if log_type == "access":
                # Parse access log line (Apache/Nginx format)
                # Example: 127.0.0.1 - - [01/Jan/2024:00:00:00 +0000] "GET / HTTP/1.1" 200 1234 0.123
                match = re.search(r'(\d+\.\d+\.\d+\.\d+).*?".*?" (\d{3}) \d+ ([\d.]+)?', line)
                if match:
                    ip = match.group(1)
                    status = match.group(2)
                    response_time = match.group(3)
                    
                    ips[ip] = ips.get(ip, 0) + 1
                    status_codes[status] = status_codes.get(status, 0) + 1
                    
                    if response_time:
                        try:
                            response_times.append(float(response_time))
                        except:
                            pass
                    
                    if status.startswith('5'):
                        errors += 1
        
        # Calculate metrics
        error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Get top IPs
        top_ips = sorted(ips.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate peak requests per minute (rough estimate)
        # Assuming logs cover last 10000 lines over some time period
        peak_rpm = int(total_requests / 100) if total_requests > 0 else 0  # Rough estimate
        
        return LogAnalysis(
            log_path="",
            total_requests=total_requests,
            error_rate=error_rate,
            avg_response_time=avg_response_time,
            peak_requests_per_minute=peak_rpm,
            top_ips=[ip for ip, _ in top_ips],
            status_codes=status_codes
        )
    
    async def collect_wordpress_info(self, install_name: str) -> Dict[str, Any]:
        """Collect WordPress information for an install.
        
        Args:
            install_name: Install name
            
        Returns:
            WordPress information
        """
        info = {}
        
        # Change to install directory
        cd_cmd = f"cd /nas/content/live/{install_name} 2>/dev/null || cd /nas/content/staging/{install_name} 2>/dev/null"
        
        # Get WordPress version
        wp_ver_cmd = f"{cd_cmd} && wp core version 2>/dev/null"
        wp_version = await self.connection.execute_command(wp_ver_cmd)
        if wp_version:
            info['version'] = wp_version.strip()
        
        # Get active plugins
        wp_plugins_cmd = f"{cd_cmd} && wp plugin list --status=active --format=json 2>/dev/null"
        plugins_json = await self.connection.execute_command(wp_plugins_cmd)
        if plugins_json:
            try:
                info['active_plugins'] = json.loads(plugins_json)
            except:
                info['active_plugins'] = []
        
        # Get active theme
        wp_theme_cmd = f"{cd_cmd} && wp theme list --status=active --format=json 2>/dev/null"
        theme_json = await self.connection.execute_command(wp_theme_cmd)
        if theme_json:
            try:
                themes = json.loads(theme_json)
                info['active_theme'] = themes[0] if themes else None
            except:
                info['active_theme'] = None
        
        return info
    
    async def process(self, task: WorkerTask) -> InstallMetrics:
        """Process SSH data collection task.
        
        Args:
            task: Worker task
            
        Returns:
            Install metrics
        """
        # Connect if not connected
        if not self.connection:
            if task.parameters.get('pod_number'):
                await self.connect_to_pod(task.parameters['pod_number'])
            else:
                await self.connect()
        
        install_name = task.parameters.get('install_name', '')
        
        # Collect system metrics
        metrics = await self.collect_system_metrics()
        
        # Collect logs
        log_data = {}
        if install_name:
            raw_logs = await self.collect_install_logs(install_name)
            for log_path, content in raw_logs.items():
                log_type = 'access' if 'access' in log_path else 'error'
                analysis = await self.analyze_logs(content, log_type)
                analysis.log_path = log_path
                log_data[log_path] = analysis
        
        # Collect MySQL slow logs
        mysql_logs = await self.collect_mysql_slow_logs()
        for log_path, content in mysql_logs.items():
            analysis = await self.analyze_logs(content, 'slow')
            analysis.log_path = log_path
            log_data[log_path] = analysis
        
        # Collect WordPress info
        wp_info = None
        if install_name:
            wp_info = await self.collect_wordpress_info(install_name)
        
        return InstallMetrics(
            install_name=install_name,
            pod_number=self.ssh_config.pod_number or 0,
            metrics=metrics,
            logs=log_data,
            wordpress_info=wp_info
        )
    
    async def disconnect(self):
        """Close SSH connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None