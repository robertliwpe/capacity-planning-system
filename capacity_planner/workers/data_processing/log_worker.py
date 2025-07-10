"""Log file processing worker."""

import re
import gzip
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from collections import defaultdict

from ..base import BaseWorker
from ...models.data_models import WorkerTask, LogAnalysis


class LogWorker(BaseWorker):
    """Worker for log file processing."""
    
    def __init__(self):
        """Initialize log worker."""
        super().__init__()
    
    async def read_log_file(self, file_path: str, max_lines: int = 10000) -> List[str]:
        """Read log file, handling compression.
        
        Args:
            file_path: Path to log file
            max_lines: Maximum lines to read
            
        Returns:
            List of log lines
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        lines = []
        
        if path.suffix == '.gz':
            with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.strip())
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line.strip())
        
        return lines
    
    async def parse_access_log(self, lines: List[str], log_format: str = 'apache') -> LogAnalysis:
        """Parse access log lines.
        
        Args:
            lines: Log lines
            log_format: Log format (apache, nginx, combined)
            
        Returns:
            Log analysis
        """
        total_requests = 0
        status_codes = defaultdict(int)
        ips = defaultdict(int)
        response_times = []
        error_count = 0
        
        # Common log patterns
        patterns = {
            'apache': r'(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d{3}) (\d+|-) (\d+\.\d+|-)',
            'nginx': r'(\S+) - - \[([^\]]+)\] "([^"]*)" (\d{3}) (\d+|-) "([^"]*)" "([^"]*)" (\d+\.\d+|-)',
            'combined': r'(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d{3}) (\d+|-) "([^"]*)" "([^"]*)"'
        }
        
        pattern = patterns.get(log_format, patterns['apache'])
        compiled_pattern = re.compile(pattern)
        
        for line in lines:
            if not line.strip():
                continue
                
            total_requests += 1
            match = compiled_pattern.match(line)
            
            if match:
                ip = match.group(1)
                status = match.group(4)
                
                ips[ip] += 1
                status_codes[status] += 1
                
                if status.startswith('5') or status.startswith('4'):
                    error_count += 1
                
                # Try to extract response time
                try:
                    if log_format == 'apache' and len(match.groups()) >= 6:
                        response_time = match.group(6)
                        if response_time != '-':
                            response_times.append(float(response_time))
                    elif log_format == 'nginx' and len(match.groups()) >= 8:
                        response_time = match.group(8)
                        if response_time != '-':
                            response_times.append(float(response_time))
                except:
                    pass
        
        # Calculate metrics
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Top IPs
        top_ips = sorted(ips.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Estimate peak RPM (rough calculation)
        peak_rpm = int(total_requests / 10) if total_requests > 0 else 0
        
        return LogAnalysis(
            log_path="",
            total_requests=total_requests,
            error_rate=error_rate,
            avg_response_time=avg_response_time,
            peak_requests_per_minute=peak_rpm,
            top_ips=[ip for ip, _ in top_ips],
            status_codes=dict(status_codes)
        )
    
    async def parse_error_log(self, lines: List[str]) -> Dict[str, Any]:
        """Parse error log lines.
        
        Args:
            lines: Error log lines
            
        Returns:
            Error analysis
        """
        error_types = defaultdict(int)
        error_levels = defaultdict(int)
        php_errors = defaultdict(int)
        
        # Common error patterns
        error_patterns = {
            'php_fatal': r'PHP Fatal error',
            'php_warning': r'PHP Warning',
            'php_notice': r'PHP Notice',
            'segfault': r'segmentation fault',
            'memory_exhausted': r'memory exhausted',
            'max_execution_time': r'Maximum execution time',
            'connection_timeout': r'connection timeout',
            'file_not_found': r'File does not exist',
            'permission_denied': r'Permission denied'
        }
        
        for line in lines:
            line_lower = line.lower()
            
            # Check error levels
            if 'error' in line_lower:
                error_levels['error'] += 1
            elif 'warning' in line_lower:
                error_levels['warning'] += 1
            elif 'notice' in line_lower:
                error_levels['notice'] += 1
            elif 'critical' in line_lower:
                error_levels['critical'] += 1
            
            # Check specific error types
            for error_type, pattern in error_patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    error_types[error_type] += 1
            
            # PHP-specific errors
            if 'php' in line_lower:
                if 'fatal' in line_lower:
                    php_errors['fatal'] += 1
                elif 'warning' in line_lower:
                    php_errors['warning'] += 1
                elif 'notice' in line_lower:
                    php_errors['notice'] += 1
        
        return {
            'total_errors': len(lines),
            'error_levels': dict(error_levels),
            'error_types': dict(error_types),
            'php_errors': dict(php_errors)
        }
    
    async def parse_mysql_slow_log(self, lines: List[str]) -> Dict[str, Any]:
        """Parse MySQL slow query log.
        
        Args:
            lines: Slow log lines
            
        Returns:
            Slow query analysis
        """
        slow_queries = []
        current_query = {}
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('# Time:'):
                if current_query:
                    slow_queries.append(current_query)
                current_query = {'timestamp': line[7:].strip()}
            
            elif line.startswith('# User@Host:'):
                current_query['user_host'] = line[12:].strip()
            
            elif line.startswith('# Query_time:'):
                # Parse: # Query_time: 1.234567  Lock_time: 0.000000 Rows_sent: 1  Rows_examined: 1000
                parts = line[13:].split()
                if len(parts) >= 8:
                    current_query['query_time'] = float(parts[0])
                    current_query['lock_time'] = float(parts[2])
                    current_query['rows_sent'] = int(parts[4])
                    current_query['rows_examined'] = int(parts[6])
            
            elif not line.startswith('#') and line:
                current_query['query'] = current_query.get('query', '') + ' ' + line
        
        # Add last query
        if current_query:
            slow_queries.append(current_query)
        
        # Calculate statistics
        query_times = [q.get('query_time', 0) for q in slow_queries if q.get('query_time')]
        
        analysis = {
            'total_slow_queries': len(slow_queries),
            'queries': slow_queries[:20],  # Limit to first 20
            'statistics': {}
        }
        
        if query_times:
            analysis['statistics'] = {
                'avg_query_time': sum(query_times) / len(query_times),
                'max_query_time': max(query_times),
                'min_query_time': min(query_times),
                'total_query_time': sum(query_times)
            }
        
        return analysis
    
    async def detect_log_type(self, lines: List[str]) -> str:
        """Detect log file type.
        
        Args:
            lines: Sample log lines
            
        Returns:
            Log type (access, error, slow, syslog, etc.)
        """
        if not lines:
            return 'unknown'
        
        sample_lines = ' '.join(lines[:10]).lower()
        
        # Check for access log patterns
        if any(method in sample_lines for method in ['get ', 'post ', 'put ', 'delete ']):
            if any(status in sample_lines for status in [' 200 ', ' 404 ', ' 500 ']):
                return 'access'
        
        # Check for error log patterns
        if any(keyword in sample_lines for keyword in ['error', 'warning', 'fatal', 'exception']):
            return 'error'
        
        # Check for MySQL slow log
        if 'query_time' in sample_lines or 'slow query log' in sample_lines:
            return 'mysql_slow'
        
        # Check for syslog
        if any(keyword in sample_lines for keyword in ['systemd', 'kernel', 'sshd']):
            return 'syslog'
        
        return 'generic'
    
    async def process(self, task: WorkerTask) -> Dict[str, Any]:
        """Process log file task.
        
        Args:
            task: Worker task
            
        Returns:
            Processing results
        """
        file_path = task.data_source.path
        if not file_path:
            raise ValueError("No file path provided")
        
        max_lines = task.parameters.get('max_lines', 10000)
        log_format = task.parameters.get('format', 'auto')
        
        # Read log file
        lines = await self.read_log_file(file_path, max_lines)
        
        if not lines:
            return {'error': 'No log lines found'}
        
        # Detect log type if auto
        if log_format == 'auto':
            log_type = await self.detect_log_type(lines)
        else:
            log_type = log_format
        
        results = {
            'file_path': file_path,
            'file_size': Path(file_path).stat().st_size,
            'lines_processed': len(lines),
            'log_type': log_type,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Process based on log type
        if log_type == 'access':
            format_type = task.parameters.get('access_format', 'apache')
            analysis = await self.parse_access_log(lines, format_type)
            analysis.log_path = file_path
            results['analysis'] = analysis
        
        elif log_type == 'error':
            results['error_analysis'] = await self.parse_error_log(lines)
        
        elif log_type == 'mysql_slow':
            results['slow_query_analysis'] = await self.parse_mysql_slow_log(lines)
        
        else:
            # Generic log analysis
            results['summary'] = {
                'total_lines': len(lines),
                'non_empty_lines': len([l for l in lines if l.strip()]),
                'sample_lines': lines[:10]
            }
        
        return results