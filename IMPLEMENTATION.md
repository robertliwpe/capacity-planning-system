# Capacity Planning System - Implementation Guide

## Overview

This system provides automated, point-in-time capacity planning recommendations for WordPress hosting configurations. It uses a hybrid orchestrator-worker pattern to process local data sources and SSH-based server metrics, matching them to optimal configurations from a predefined matrix.

## Architecture

### System Design Principles

1. **Local-first**: Runs entirely on local machine, no external API dependencies
2. **SSH-based data collection**: Uses user's SSH credentials to collect server metrics
3. **Terminal-accessible**: Leverages existing terminal/SSH access for data gathering
4. **Point-in-time analysis**: Provides recommendations based on current data snapshot
5. **Flexible data ingestion**: Handles multiple data formats and sources
6. **Continuous learning**: Improves recommendations based on feedback
7. **Dual interface**: CLI for automation, GUI for interactive use

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              User Interface Layer                                  │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │          CLI Interface            │  │         GUI (Streamlit)         │  │
│  └─────────────────────────────────────┘  └─────────────────────────────────┘  │
├─────────────────────────────────────┴─────────────────────────────────────┤
│                             Orchestrator Layer                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Main Orchestrator                              │  │
│  │  - Task complexity analysis                                            │  │
│  │  - Worker coordination                                                 │  │
│  │  - Result synthesis                                                    │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────┴─────────────────────────────────────┤
│                               Worker Layer                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │ Data Workers │  │   Analysis    │  │   Learning    │  │    Report     │  │
│  │              │  │    Workers    │  │    Workers    │  │   Generator   │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘  │
├─────────────────────────────────────┴─────────────────────────────────────┤
│                             Storage Layer                                          │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐  │
│  │      Vector Database (ChromaDB)    │  │         SQLite Database         │  │
│  └─────────────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Collection Strategy

### 1. Local File Sources
- **CSV Files**: Usage statistics, performance metrics
- **Log Files**: Apache/Nginx access logs, error logs
- **PDF Reports**: Dashboard exports, performance reports
- **JSON Files**: Configuration dumps, API responses

### 2. SSH-Based Data Collection
- **System Metrics**: CPU, memory, disk usage via SSH commands
- **Log Analysis**: Direct access to server logs via SSH
- **Database Queries**: MySQL performance metrics via SSH tunneling
- **Process Monitoring**: Real-time process information

### 3. Terminal Commands
- **Local System Info**: Host system metrics for baseline comparisons
- **Network Diagnostics**: Latency, bandwidth testing
- **Docker Stats**: Container resource usage (if applicable)

## Implementation Details

### Configuration Matrix

The system uses configurations from `/Users/robert.li/Desktop/technical-solutions/wpod-config-python/matrix_cleaned.csv`:

- **68 predefined configurations** (p0 to p10 with variants)
- **Resource specifications** for each component:
  - PHP, MySQL, Nginx, Memcached, Varnish, etc.
  - CPU limits/requests and memory limits/requests
- **Configuration naming**: `p{tier}[-{specialization}][-{size}][-v{version}]`
  - Tiers: 0-10 (increasing capacity)
  - Specializations: php, db, dense
  - Sizes: standard, xl

### Project Structure

```bash
capacity-planning-system/
├── capacity_planner/
│   ├── __init__.py
│   ├── __main__.py              # Entry point
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── main.py              # Main orchestrator
│   │   ├── task_analyzer.py     # Complexity analysis
│   │   └── coordinator.py       # Worker coordination
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── base.py              # Base worker class
│   │   ├── data_processing/
│   │   │   ├── csv_worker.py
│   │   │   ├── log_worker.py
│   │   │   ├── pdf_worker.py
│   │   │   ├── ssh_worker.py
│   │   │   └── terminal_worker.py
│   │   ├── analysis/
│   │   │   ├── pattern_matcher.py
│   │   │   ├── anomaly_detector.py
│   │   │   └── recommendation_engine.py
│   │   └── learning/
│   │       ├── feedback_processor.py
│   │       ├── model_trainer.py
│   │       └── knowledge_manager.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── metrics.py           # Metric calculations
│   │   ├── patterns.py          # Pattern definitions
│   │   └── scoring.py           # Configuration scoring
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── embeddings.py        # Vector embeddings
│   │   ├── memory.py            # Long-term memory
│   │   └── models.py            # ML models
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── commands.py          # CLI commands
│   │   ├── interactive.py       # Interactive mode
│   │   └── utils.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py               # Streamlit app
│   │   ├── pages/
│   │   │   ├── upload.py
│   │   │   ├── analysis.py
│   │   │   └── results.py
│   │   └── components/
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management
│   │   ├── logging.py           # Logging setup
│   │   ├── ssh_utils.py         # SSH connection utilities
│   │   └── validation.py        # Data validation
│   └── models/
│       ├── __init__.py
│       ├── data_models.py       # Pydantic models
│       └── db_models.py         # Database models
├── data/
│   ├── configurations/
│   │   └── matrix_cleaned.csv   # Copy of config matrix
│   ├── templates/
│   │   └── report_template.md
│   ├── ssh_configs/
│   │   └── known_hosts
│   └── examples/
├── tests/
│   ├── __init__.py
│   ├── test_orchestrator.py
│   ├── test_workers.py
│   ├── test_analysis.py
│   └── fixtures/
├── docs/
│   ├── api.md
│   ├── architecture.md
│   └── user_guide.md
└── scripts/
    ├── setup.sh
    └── demo.py
```

## Key Implementation Components

### 1. SSH Data Collection Worker (`workers/data_processing/ssh_worker.py`)

```python
import paramiko
import asyncio
from typing import Dict, List, Optional
from ..base import BaseWorker
from ...utils.ssh_utils import SSHConnection
from ...models.data_models import SSHConfig, MetricData

class SSHWorker(BaseWorker):
    def __init__(self, ssh_config: SSHConfig):
        self.ssh_config = ssh_config
        self.connection = None
    
    async def connect(self) -> bool:
        """Establish SSH connection using user's credentials"""
        try:
            self.connection = SSHConnection(
                hostname=self.ssh_config.hostname,
                username=self.ssh_config.username,
                key_filename=self.ssh_config.key_path,
                port=self.ssh_config.port
            )
            await self.connection.connect()
            return True
        except Exception as e:
            self.logger.error(f"SSH connection failed: {e}")
            return False
    
    async def collect_system_metrics(self) -> Dict:
        """Collect system metrics via SSH commands"""
        commands = {
            'cpu_usage': "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
            'memory_usage': "free -m | grep '^Mem:' | awk '{print ($3/$2)*100}'",
            'disk_usage': "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1",
            'load_average': "uptime | awk -F'load average:' '{print $2}'",
            'process_count': "ps aux | wc -l",
            'mysql_processes': "ps aux | grep mysql | wc -l",
            'php_processes': "ps aux | grep php | wc -l",
            'nginx_processes': "ps aux | grep nginx | wc -l"
        }
        
        results = {}
        for metric, command in commands.items():
            try:
                result = await self.connection.execute_command(command)
                results[metric] = self.parse_metric_output(metric, result)
            except Exception as e:
                self.logger.warning(f"Failed to collect {metric}: {e}")
                results[metric] = None
        
        return results
    
    async def collect_log_data(self, log_paths: List[str]) -> Dict:
        """Collect and analyze log files via SSH"""
        log_data = {}
        
        for log_path in log_paths:
            try:
                # Get recent log entries (last 10000 lines)
                command = f"tail -n 10000 {log_path}"
                log_content = await self.connection.execute_command(command)
                
                # Parse log based on type
                if 'access' in log_path:
                    log_data[f'{log_path}_access'] = self.parse_access_log(log_content)
                elif 'error' in log_path:
                    log_data[f'{log_path}_error'] = self.parse_error_log(log_content)
                else:
                    log_data[log_path] = self.parse_generic_log(log_content)
                    
            except Exception as e:
                self.logger.warning(f"Failed to collect log {log_path}: {e}")
        
        return log_data
    
    async def collect_database_metrics(self) -> Dict:
        """Collect MySQL performance metrics"""
        mysql_commands = {
            'connections': "mysql -e 'SHOW STATUS LIKE \"Threads_connected\"'",
            'queries_per_sec': "mysql -e 'SHOW STATUS LIKE \"Questions\"'",
            'slow_queries': "mysql -e 'SHOW STATUS LIKE \"Slow_queries\"'",
            'table_locks': "mysql -e 'SHOW STATUS LIKE \"Table_locks_waited\"'",
            'innodb_buffer_pool': "mysql -e 'SHOW STATUS LIKE \"Innodb_buffer_pool_pages_free\"'"
        }
        
        db_metrics = {}
        for metric, command in mysql_commands.items():
            try:
                result = await self.connection.execute_command(command)
                db_metrics[metric] = self.parse_mysql_output(result)
            except Exception as e:
                self.logger.warning(f"Failed to collect MySQL {metric}: {e}")
        
        return db_metrics
    
    async def disconnect(self):
        """Close SSH connection"""
        if self.connection:
            await self.connection.close()
```

### 2. SSH Connection Utility (`utils/ssh_utils.py`)

```python
import paramiko
import asyncio
import os
from typing import Optional
from pathlib import Path

class SSHConnection:
    def __init__(self, hostname: str, username: str, key_filename: Optional[str] = None, 
                 password: Optional[str] = None, port: int = 22):
        self.hostname = hostname
        self.username = username
        self.key_filename = key_filename
        self.password = password
        self.port = port
        self.client = None
    
    async def connect(self):
        """Establish SSH connection"""
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if self.key_filename and os.path.exists(self.key_filename):
                # Use SSH key authentication
                self.client.connect(
                    hostname=self.hostname,
                    username=self.username,
                    key_filename=self.key_filename,
                    port=self.port,
                    timeout=30
                )
            elif self.password:
                # Use password authentication
                self.client.connect(
                    hostname=self.hostname,
                    username=self.username,
                    password=self.password,
                    port=self.port,
                    timeout=30
                )
            else:
                # Try default SSH keys
                self.client.connect(
                    hostname=self.hostname,
                    username=self.username,
                    port=self.port,
                    timeout=30
                )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.hostname}: {e}")
    
    async def execute_command(self, command: str) -> str:
        """Execute command on remote server"""
        if not self.client:
            raise RuntimeError("SSH connection not established")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            
            # Wait for command to complete
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                error_output = stderr.read().decode()
                raise RuntimeError(f"Command failed with exit code {exit_status}: {error_output}")
            
            return stdout.read().decode().strip()
        
        except Exception as e:
            raise RuntimeError(f"Failed to execute command '{command}': {e}")
    
    async def download_file(self, remote_path: str, local_path: str):
        """Download file from remote server"""
        if not self.client:
            raise RuntimeError("SSH connection not established")
        
        try:
            sftp = self.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
        except Exception as e:
            raise RuntimeError(f"Failed to download {remote_path}: {e}")
    
    async def close(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
```

### 3. Terminal Worker (`workers/data_processing/terminal_worker.py`)

```python
import subprocess
import asyncio
import psutil
import shutil
from typing import Dict, List
from ..base import BaseWorker

class TerminalWorker(BaseWorker):
    def __init__(self):
        super().__init__()
    
    async def collect_local_system_info(self) -> Dict:
        """Collect local system information"""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': {
                'total': psutil.disk_usage('/').total,
                'used': psutil.disk_usage('/').used,
                'free': psutil.disk_usage('/').free
            },
            'network_io': psutil.net_io_counters()._asdict(),
            'boot_time': psutil.boot_time()
        }
    
    async def execute_command(self, command: str) -> str:
        """Execute local terminal command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")
            
            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out: {command}")
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}")
    
    async def check_docker_containers(self) -> Dict:
        """Check Docker container status if Docker is available"""
        if not shutil.which('docker'):
            return {'docker_available': False}
        
        try:
            # Get container stats
            stats_output = await self.execute_command('docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"')
            
            # Get container list
            ps_output = await self.execute_command('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"')
            
            return {
                'docker_available': True,
                'container_stats': self.parse_docker_stats(stats_output),
                'container_list': self.parse_docker_ps(ps_output)
            }
        
        except Exception as e:
            return {
                'docker_available': True,
                'error': str(e)
            }
    
    async def network_diagnostics(self, target_hosts: List[str]) -> Dict:
        """Perform network diagnostics"""
        diagnostics = {}
        
        for host in target_hosts:
            try:
                # Ping test
                ping_result = await self.execute_command(f'ping -c 4 {host}')
                diagnostics[f'{host}_ping'] = self.parse_ping_output(ping_result)
                
                # Traceroute (if available)
                if shutil.which('traceroute'):
                    trace_result = await self.execute_command(f'traceroute -m 10 {host}')
                    diagnostics[f'{host}_traceroute'] = self.parse_traceroute_output(trace_result)
                
            except Exception as e:
                diagnostics[f'{host}_error'] = str(e)
        
        return diagnostics
```

### 4. Enhanced CLI Interface

```python
# cli/commands.py
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from pathlib import Path
import asyncio

console = Console()

@click.group()
def cli():
    pass

@cli.command()
@click.option('--data-dir', type=click.Path(exists=True), help='Directory containing data files')
@click.option('--ssh-config', type=click.Path(exists=True), help='SSH configuration file')
@click.option('--servers', multiple=True, help='Server hostnames to analyze')
@click.option('--output', default='report.md', help='Output report file')
@click.option('--confidence-threshold', default=0.75, help='Minimum confidence score')
def analyze(data_dir, ssh_config, servers, output, confidence_threshold):
    """Analyze capacity requirements using local files and SSH data collection."""
    
    with Progress() as progress:
        task = progress.add_task("Analyzing capacity...", total=100)
        
        # Initialize orchestrator
        orchestrator = CapacityPlanningOrchestrator()
        
        # Prepare data sources
        data_sources = []
        
        if data_dir:
            data_sources.extend(find_local_data_files(data_dir))
            progress.update(task, advance=20)
        
        if ssh_config and servers:
            ssh_sources = prepare_ssh_data_sources(ssh_config, servers)
            data_sources.extend(ssh_sources)
            progress.update(task, advance=30)
        
        # Process data
        request = AnalysisRequest(
            data_sources=data_sources,
            confidence_threshold=confidence_threshold
        )
        
        result = asyncio.run(orchestrator.analyze(request))
        progress.update(task, advance=100)
        
        # Generate report
        with open(output, 'w') as f:
            f.write(result.report)
        
        # Display results
        display_recommendations(result.recommendations)
        console.print(f"[green]Analysis complete! Report saved to {output}[/green]")

@cli.command()
@click.option('--host', required=True, help='Target hostname')
@click.option('--username', help='SSH username')
@click.option('--key-path', type=click.Path(exists=True), help='SSH private key path')
def test_ssh(host, username, key_path):
    """Test SSH connection and collect sample metrics."""
    
    async def test_connection():
        ssh_config = SSHConfig(
            hostname=host,
            username=username,
            key_path=key_path
        )
        
        worker = SSHWorker(ssh_config)
        
        try:
            console.print(f"[yellow]Connecting to {host}...[/yellow]")
            if await worker.connect():
                console.print("[green]Connection successful![/green]")
                
                # Collect sample metrics
                console.print("[yellow]Collecting system metrics...[/yellow]")
                metrics = await worker.collect_system_metrics()
                
                # Display metrics table
                table = Table(title="System Metrics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                for metric, value in metrics.items():
                    table.add_row(metric, str(value))
                
                console.print(table)
                
            else:
                console.print("[red]Connection failed![/red]")
                
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            await worker.disconnect()
    
    asyncio.run(test_connection())

@cli.command()
def interactive():
    """Launch interactive analysis mode."""
    console.print("[bold blue]Capacity Planning Interactive Mode[/bold blue]")
    
    # Interactive prompts for configuration
    data_dir = click.prompt("Data directory path (optional)", default="", show_default=False)
    
    if click.confirm("Do you want to collect data from remote servers via SSH?"):
        servers = []
        while True:
            server = click.prompt("Enter server hostname (or press Enter to finish)", default="")
            if not server:
                break
            servers.append(server)
        
        if servers:
            username = click.prompt("SSH username", default=os.getenv('USER'))
            key_path = click.prompt("SSH key path", default=f"{os.path.expanduser('~')}/.ssh/id_rsa")
    
    # Run analysis
    console.print("[yellow]Starting analysis...[/yellow]")
    # Implementation continues...
```

### 5. Data Models for SSH

```python
# models/data_models.py
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path

class SSHConfig(BaseModel):
    hostname: str
    username: str
    key_path: Optional[str] = None
    password: Optional[str] = None
    port: int = 22

class ServerMetrics(BaseModel):
    hostname: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    load_average: str
    processes: Dict[str, int]
    timestamp: str

class LogAnalysis(BaseModel):
    log_path: str
    total_requests: int
    error_rate: float
    avg_response_time: float
    peak_requests_per_minute: int
    top_ips: List[str]
    status_codes: Dict[str, int]
```

## Security Considerations

1. **SSH Key Management**: Use existing SSH keys, never store passwords
2. **Connection Security**: All connections use standard SSH protocols
3. **Data Privacy**: All processing happens locally
4. **Access Control**: Respects existing SSH permissions
5. **Audit Trail**: Log all SSH connections and commands

## Usage Examples

### CLI Usage

```bash
# Analyze using local files only
python -m capacity_planner analyze --data-dir ./data

# Analyze with SSH data collection
python -m capacity_planner analyze \
  --data-dir ./data \
  --servers server1.example.com server2.example.com

# Test SSH connection
python -m capacity_planner test-ssh \
  --host server.example.com \
  --username admin \
  --key-path ~/.ssh/id_rsa

# Interactive mode
python -m capacity_planner interactive
```

### Configuration File

```yaml
# config.yaml
ssh_servers:
  - hostname: "web01.example.com"
    username: "admin"
    key_path: "~/.ssh/web_servers"
  - hostname: "db01.example.com"
    username: "admin"
    key_path: "~/.ssh/db_servers"

data_collection:
  log_paths:
    - "/var/log/nginx/access.log"
    - "/var/log/mysql/slow.log"
  
  metrics_interval: 300  # seconds
  
analysis:
  confidence_threshold: 0.75
  historical_lookback: 30  # days
```

## Implementation Timeline

### Phase 1: SSH Infrastructure (Week 1-2)
1. Implement SSH connection utilities
2. Create SSH worker with basic metrics collection
3. Add terminal worker for local commands
4. Test SSH connectivity and data collection

### Phase 2: Data Processing (Week 3-4)
1. Enhance log parsing for SSH-collected logs
2. Implement system metrics analysis
3. Add database metrics collection
4. Create data validation and normalization

### Phase 3: Analysis Engine (Week 5-6)
1. Adapt pattern matching for SSH-collected data
2. Enhance scoring model with system metrics
3. Implement recommendation engine
4. Add report generation

### Phase 4: Learning System (Week 7-8)
1. Integrate feedback from SSH-based analyses
2. Implement similarity matching
3. Add continuous learning capabilities
4. Create knowledge base management

### Phase 5: User Interface (Week 9-10)
1. Complete CLI with SSH options
2. Add interactive SSH configuration
3. Build GUI with SSH connection management
4. Create visualization for server metrics

### Phase 6: Testing & Documentation (Week 11-12)
1. Comprehensive testing with various SSH scenarios
2. Security testing and validation
3. Performance optimization
4. Documentation and user guides

This approach ensures the system works within existing SSH infrastructure while providing comprehensive capacity planning capabilities.

## SSH Pod Access Patterns

### Pod Connection Format

When SSHing into a pod, the correct format is:
```bash
ssh pod-${podnumber}.wpengine.com
```

The user will be prompted to enter one or more pod numbers. The system uses the existing user's permissions and keys, accepting any new keys implicitly if required.

### Log File Locations

Install access logs can be accessed via the following pathnames:

- `/var/log/nginx/${install}.apachestyle.log*` - Apache log format
- `/var/log/nginx/${install}.access.log*` - Nginx log format  
- `/var/log/apache2/${install}.access.log*` - Apache2 access logs

**Log Compression:**
- Web server access logs are uncompressed for the first 2 files:
  - `/var/log/nginx/${install}.apachestyle.log`
  - `/var/log/nginx/${install}.apachestyle.log.1`
- Subsequent logs are gzipped, requiring `zcat -f` command to read them

**MySQL Slow Logs:**
- Located at: `/var/log/mysql/mysql-slow.log*`
- Require sudo permission to read
- First 2 files are uncompressed, rest are gzipped
- If sudo password is required, use a sudo password stored in the `.env` file

### Server Functions Available on Pods

When SSH'd into a pod, there are additional functions that can be accessed:

#### Performance Analysis Functions

**Log Analysis:**
- `alog` - Parse Apache access log (--help for options)
- `nlog` - Parse NGINX access log (--help for options)
- `myslow` - MySQL Slow Log analysis ([hours ago])
- `mysqloff` - MySQL Offender analysis (See --help)
- `apacheoff` - Apache Offender analysis (<install_name>)
- `ipoffender` - IP Offenders analysis (<install_name>)
- `uaoffender` - UserAgent Offender (<a|n> <install_name> [search])

**Real-time Monitoring:**
- `apachewatch` - Watch Apache Process Length
- `loadwatch` - Watch Apache log growth
- `logwatch` - Watch Apache log growth
- `concurrent` - Show nginx concurrent users (run from doc root)
- `concurrenta` - Show apache concurrent users (run from doc root)
- `event-monitor` - Live server performance monitoring to Slack channels

**Historical Analysis:**
- `factfind` - Gather server usage facts ([install_name])
- `healthcheck` - Perform many checks to train on diagnosing server load
- `recapit` - Historical or real time resource usage ([-d previous day] [-h help])
- `sarqh` - Check for high load during the last 5 days
- `bandwidth-check` - Check bandwidth of an install (<install-name> [-d])

#### System Information Functions

**Navigation:**
- `wpe` - Go to wpe sites directory ([install_name])
- `wpes` - Go to wpe staging directory ([install_name])
- `wpep` - Go to the _wpeprivate directory (live) ([install_name])
- `wpesp` - Go to the _wpeprivate directory (staging) ([install_name])

**Platform Commands:**
- `deploys` - Info on recent deploys/updates of WPE packages
- `purge-all` - kitt site:purge-caches
- `l1-purge-varnish` - kitt site:purge-caches ([install_name] [--varnish-only=true])
- `regen` - kitt install:regen
- `apply` - kitt install:apply
- `impersonate` - Create a shell session as the install's unix user (EVLV only) ([install])

**WordPress Management:**
- `check` - Get general WordPress settings
- `check2` - Same as check, but with extended info (slower)
- `ver` - Gets current WP version ([install_name])
- `wpeuser` - Set 'wpengine' user and pass (<install_name> [staging])
- `theme` - Change theme ([theme_name] [-h or --help])
- `plugin` - Various plugin related tasks (plugin [-h,--help])
- `ptoggle` - Activate/Deactivate plugins without losing auth keys (run from doc root)

**Database Functions:**
- `dbcheck` - Check for crashed tables (<install_name> [staging])
- `dbrepair` - Repair crashed tables (<install_name> [staging])
- `dbrows` - Get row count of tables (<install_name> [staging] [-p])
- `dbsearch` - Search database for term (<search_term> [table_name])
- `dbdump` - Dump database without wpcli (run from doc root)
- `dbautoload` - Check autoloaded data ([install_name] [alltables] [-s] [-h])
- `dbsummary` - Analyze key database optimization values ([-s. --size])

**Error Analysis:**
- `aperr` - Apache errors ([install_name])
- `errorcount` - Show counts of Apache errors ([install])
- `phpfatal` - PHP Fatal errors ([install_name])
- `codes` - Count HTTP Codes (see codes --help for options)
- `get50x` - Count 50x errors
- `evict` - Displays information about 504s over the last 2 days for a pod

**Disk Management:**
- `disk-junk-finder` - Check disk space of known directories
- `sds` - Show Disk Space - colorized summary of disk usage
- `diskaudit` - Display diskspace (files and DB) a site is taking

**Cache Management:**
- `cache-check` - Count cache exception hits (--install [install_name])
- `banlist` - Show most recent items purged in Varnish ([number_of_lines])
- `cacheable` - Show cacheability for sites (See --help)

#### Advanced Functions (L2 Access)

If L1a/L2 access is available:
- `admin` - sudo /opt/nas/admin
- `cluster` - sudo /opt/nas/ec2/cluster  
- `wpephp` - sudo php /opt/nas/www/tools/wpe.php
- `adminl` - Show admin commands ([search])
- `clul` - Show cluster commands ([search])
- `wpel` - Show wpe.php commands ([search])

### Implementation Updates for SSH Worker

The SSH worker should be updated to support these pod-specific patterns:

```python
class SSHWorker(BaseWorker):
    def __init__(self, ssh_config: SSHConfig):
        super().__init__()
        self.ssh_config = ssh_config
        self.connection = None
        self.sudo_password = os.getenv('SUDO_PASSWORD')
        
    async def connect_to_pod(self, pod_number: int) -> bool:
        """Connect to a specific pod"""
        hostname = f"pod-{pod_number}.wpengine.com"
        self.ssh_config.hostname = hostname
        return await self.connect()
    
    async def collect_install_logs(self, install_name: str) -> Dict:
        """Collect logs for a specific install"""
        log_paths = [
            f"/var/log/nginx/{install_name}.apachestyle.log",
            f"/var/log/nginx/{install_name}.access.log",
            f"/var/log/apache2/{install_name}.access.log"
        ]
        
        log_data = {}
        for log_path in log_paths:
            # Check if file exists
            check_cmd = f"test -f {log_path} && echo exists"
            if await self.execute_command(check_cmd):
                # Read uncompressed logs
                log_content = await self.execute_command(f"tail -n 10000 {log_path}")
                log_data[log_path] = log_content
                
                # Check for compressed versions
                for i in range(2, 10):
                    compressed_path = f"{log_path}.{i}.gz"
                    check_cmd = f"test -f {compressed_path} && echo exists"
                    if await self.execute_command(check_cmd):
                        # Read compressed logs
                        log_content = await self.execute_command(f"zcat -f {compressed_path} | tail -n 10000")
                        log_data[compressed_path] = log_content
                    else:
                        break
        
        return log_data
    
    async def execute_server_function(self, function_name: str, args: List[str] = None) -> str:
        """Execute a server function on the pod"""
        command = function_name
        if args:
            command += " " + " ".join(args)
        
        return await self.execute_command(command)
    
    async def collect_mysql_slow_logs(self) -> Dict:
        """Collect MySQL slow logs with sudo"""
        if not self.sudo_password:
            self.logger.warning("No sudo password provided in .env file")
            return {}
        
        logs = {}
        base_path = "/var/log/mysql/mysql-slow.log"
        
        # Read uncompressed logs
        for i in ["", ".1"]:
            log_path = f"{base_path}{i}"
            cmd = f"echo '{self.sudo_password}' | sudo -S tail -n 1000 {log_path}"
            try:
                content = await self.execute_command(cmd)
                logs[log_path] = content
            except Exception as e:
                self.logger.warning(f"Failed to read {log_path}: {e}")
        
        # Read compressed logs
        for i in range(2, 10):
            log_path = f"{base_path}.{i}.gz"
            cmd = f"echo '{self.sudo_password}' | sudo -S zcat -f {log_path} | tail -n 1000"
            try:
                content = await self.execute_command(cmd)
                logs[log_path] = content
            except Exception as e:
                # No more compressed files
                break
        
        return logs
```

### CLI Updates for Pod Access

The CLI should be updated to prompt for pod numbers:

```python
@cli.command()
@click.option('--pods', multiple=True, type=int, help='Pod numbers to analyze')
@click.option('--installs', multiple=True, help='Install names to analyze')
def analyze_pods(pods, installs):
    """Analyze capacity for specific pods and installs."""
    
    if not pods:
        # Interactive prompt for pod numbers
        pod_list = []
        console.print("[bold blue]Enter pod numbers (press Enter when done):[/bold blue]")
        while True:
            pod = click.prompt("Pod number", default="", show_default=False)
            if not pod:
                break
            try:
                pod_list.append(int(pod))
            except ValueError:
                console.print("[red]Invalid pod number[/red]")
        pods = pod_list
    
    if not installs:
        # Prompt for install names
        install_list = []
        console.print("[bold blue]Enter install names (press Enter when done):[/bold blue]")
        while True:
            install = click.prompt("Install name", default="", show_default=False)
            if not install:
                break
            install_list.append(install)
        installs = install_list
    
    # Connect to pods and analyze
    for pod_number in pods:
        console.print(f"[yellow]Connecting to pod-{pod_number}.wpengine.com...[/yellow]")
        # Analysis implementation
```
# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.