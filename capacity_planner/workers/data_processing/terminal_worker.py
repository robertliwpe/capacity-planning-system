"""Terminal command execution worker."""

import subprocess
import asyncio
import shutil
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    psutil = None

from ..base import BaseWorker
from ...models.data_models import WorkerTask, ServerMetrics


class TerminalWorker(BaseWorker):
    """Worker for local terminal command execution."""
    
    def __init__(self):
        """Initialize terminal worker."""
        super().__init__()
    
    async def collect_local_system_info(self) -> ServerMetrics:
        """Collect local system information."""
        # Get hostname
        hostname_result = await self.execute_command("hostname")
        hostname = hostname_result.strip() if hostname_result else "localhost"
        
        if psutil is None:
            # Fallback when psutil is not available
            cpu_percent = 0.0
            memory = type('Memory', (), {'total': 0, 'available': 0, 'percent': 0.0})()
            disk = type('Disk', (), {'total': 0, 'used': 0, 'percent': 0.0})()
            load_avg_str = "0.0, 0.0, 0.0"
            processes = {'total': 0, 'python': 0, 'node': 0, 'docker': 0}
            network_io = {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0}
        else:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory info
            memory = psutil.virtual_memory()
            
            # Disk info
            disk = psutil.disk_usage('/')
            
            # Load average
            load_avg = psutil.getloadavg()
            load_avg_str = f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
            
            # Process counts
            processes = {
                'total': len(psutil.pids()),
                'python': 0,
                'node': 0,
                'docker': 0
            }
            
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name'].lower()
                    if 'python' in name:
                        processes['python'] += 1
                    elif 'node' in name:
                        processes['node'] += 1
                    elif 'docker' in name:
                        processes['docker'] += 1
                except:
                    pass
            
            # Network I/O
            net_io = psutil.net_io_counters()
            network_io = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        
        return ServerMetrics(
            hostname=hostname,
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            memory_total=memory.total,
            memory_available=memory.available,
            disk_usage=disk.percent,
            disk_total=disk.total,
            disk_used=disk.used,
            load_average=load_avg_str,
            processes=processes,
            network_io=network_io
        )
    
    async def execute_command(self, command: str, timeout: int = 30) -> str:
        """Execute local terminal command.
        
        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Command output
        """
        try:
            # Run command asynchronously
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for command with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuntimeError(f"Command timed out after {timeout}s: {command}")
            
            # Check return code
            if proc.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                if error_msg:
                    raise RuntimeError(f"Command failed: {error_msg}")
            
            return stdout.decode('utf-8', errors='ignore').strip()
            
        except Exception as e:
            self.logger.error(f"Failed to execute command '{command}': {e}")
            raise
    
    async def check_docker_containers(self) -> Dict[str, Any]:
        """Check Docker container status if Docker is available."""
        if not shutil.which('docker'):
            return {'docker_available': False}
        
        result = {'docker_available': True}
        
        try:
            # Get container list
            ps_output = await self.execute_command(
                'docker ps --format "json"'
            )
            
            containers = []
            for line in ps_output.strip().split('\n'):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except:
                        pass
            
            result['containers'] = containers
            result['container_count'] = len(containers)
            
            # Get container stats
            if containers:
                stats_output = await self.execute_command(
                    'docker stats --no-stream --format "json"'
                )
                
                stats = []
                for line in stats_output.strip().split('\n'):
                    if line:
                        try:
                            stats.append(json.loads(line))
                        except:
                            pass
                
                result['container_stats'] = stats
            
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def network_diagnostics(self, target_hosts: List[str]) -> Dict[str, Any]:
        """Perform network diagnostics.
        
        Args:
            target_hosts: List of hosts to test
            
        Returns:
            Diagnostic results
        """
        diagnostics = {}
        
        for host in target_hosts:
            host_diag = {}
            
            # Ping test
            try:
                ping_cmd = f"ping -c 4 -W 2 {host}"
                ping_result = await self.execute_command(ping_cmd)
                
                # Parse ping output
                lines = ping_result.split('\n')
                for line in lines:
                    if 'min/avg/max' in line:
                        # Extract RTT values
                        match = re.search(r'(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)', line)
                        if match:
                            host_diag['ping'] = {
                                'min_rtt': float(match.group(1)),
                                'avg_rtt': float(match.group(2)),
                                'max_rtt': float(match.group(3)),
                                'status': 'success'
                            }
                    elif '% packet loss' in line:
                        match = re.search(r'(\d+)% packet loss', line)
                        if match:
                            host_diag['packet_loss'] = int(match.group(1))
                
            except Exception as e:
                host_diag['ping'] = {'status': 'failed', 'error': str(e)}
            
            # DNS lookup
            try:
                nslookup_cmd = f"nslookup {host}"
                nslookup_result = await self.execute_command(nslookup_cmd, timeout=5)
                host_diag['dns'] = {'status': 'success', 'resolved': True}
            except Exception as e:
                host_diag['dns'] = {'status': 'failed', 'error': str(e)}
            
            # Traceroute (if available)
            if shutil.which('traceroute'):
                try:
                    trace_cmd = f"traceroute -m 10 -w 2 {host}"
                    trace_result = await self.execute_command(trace_cmd, timeout=20)
                    
                    hops = []
                    for line in trace_result.split('\n')[1:]:  # Skip header
                        if line.strip():
                            hops.append(line.strip())
                    
                    host_diag['traceroute'] = {
                        'status': 'success',
                        'hops': hops[:10]  # Limit to 10 hops
                    }
                except Exception as e:
                    host_diag['traceroute'] = {'status': 'failed', 'error': str(e)}
            
            diagnostics[host] = host_diag
        
        return diagnostics
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        resources = {}
        
        if psutil is None:
            # Fallback when psutil is not available
            resources['cpu'] = {
                'count': 1,
                'count_physical': 1,
                'percent': 0.0,
                'freq': None
            }
            resources['memory'] = {
                'total': 0,
                'available': 0,
                'percent': 0.0,
                'used': 0,
                'free': 0
            }
            resources['swap'] = {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0.0
            }
            resources['disk_partitions'] = []
            resources['network_interfaces'] = []
        else:
            # CPU info
            resources['cpu'] = {
                'count': psutil.cpu_count(),
                'count_physical': psutil.cpu_count(logical=False),
                'percent': psutil.cpu_percent(interval=1),
                'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
            }
            
            # Memory info
            mem = psutil.virtual_memory()
            resources['memory'] = {
                'total': mem.total,
                'available': mem.available,
                'percent': mem.percent,
                'used': mem.used,
                'free': mem.free
            }
            
            # Swap info
            swap = psutil.swap_memory()
            resources['swap'] = {
                'total': swap.total,
                'used': swap.used,
                'free': swap.free,
                'percent': swap.percent
            }
            
            # Disk partitions
            partitions = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    })
                except:
                    pass
            resources['disk_partitions'] = partitions
            
            # Network interfaces
            net_if = psutil.net_if_addrs()
            resources['network_interfaces'] = list(net_if.keys())
        
        return resources
    
    async def run_performance_test(self, test_type: str = "basic") -> Dict[str, Any]:
        """Run performance tests.
        
        Args:
            test_type: Type of test to run
            
        Returns:
            Test results
        """
        results = {}
        
        if test_type == "basic":
            # CPU benchmark (simple calculation)
            start_time = datetime.now(timezone.utc)
            count = 0
            while (datetime.now(timezone.utc) - start_time).total_seconds() < 1:
                count += 1
                _ = sum(i**2 for i in range(1000))
            results['cpu_operations_per_second'] = count
            
            # Memory speed test
            start_time = datetime.now(timezone.utc)
            data = bytearray(10 * 1024 * 1024)  # 10MB
            iterations = 0
            while (datetime.now(timezone.utc) - start_time).total_seconds() < 1:
                data[iterations % len(data)] = iterations % 256
                iterations += 1
            results['memory_operations_per_second'] = iterations
            
            # Disk speed test (if possible)
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=True) as f:
                    data = b'x' * (1024 * 1024)  # 1MB
                    start_time = datetime.now(timezone.utc)
                    writes = 0
                    while (datetime.now(timezone.utc) - start_time).total_seconds() < 1:
                        f.write(data)
                        f.flush()
                        writes += 1
                    results['disk_mb_per_second'] = writes
            except:
                results['disk_mb_per_second'] = 0
        
        return results
    
    async def process(self, task: WorkerTask) -> Dict[str, Any]:
        """Process terminal worker task.
        
        Args:
            task: Worker task
            
        Returns:
            Task results
        """
        task_type = task.parameters.get('type', 'system_info')
        
        if task_type == 'system_info':
            return {
                'metrics': await self.collect_local_system_info(),
                'resources': await self.check_system_resources(),
                'docker': await self.check_docker_containers()
            }
        
        elif task_type == 'network_diagnostics':
            hosts = task.parameters.get('hosts', ['google.com', '8.8.8.8'])
            return await self.network_diagnostics(hosts)
        
        elif task_type == 'performance_test':
            test_type = task.parameters.get('test_type', 'basic')
            return await self.run_performance_test(test_type)
        
        elif task_type == 'execute_command':
            command = task.parameters.get('command')
            if not command:
                raise ValueError("No command specified")
            timeout = task.parameters.get('timeout', 30)
            return {
                'command': command,
                'output': await self.execute_command(command, timeout),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        else:
            raise ValueError(f"Unknown task type: {task_type}")