"""PDF file processing worker."""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import PyPDF2

from ..base import BaseWorker
from ...models.data_models import WorkerTask


class PDFWorker(BaseWorker):
    """Worker for PDF file processing."""
    
    def __init__(self):
        """Initialize PDF worker."""
        super().__init__()
    
    async def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        text = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()
                    text += "\n"
        
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF: {e}")
            raise
        
        return text
    
    async def extract_metrics_from_text(self, text: str) -> Dict[str, Any]:
        """Extract performance metrics from text.
        
        Args:
            text: Extracted text
            
        Returns:
            Extracted metrics
        """
        metrics = {}
        
        # CPU usage patterns
        cpu_patterns = [
            r'cpu\s*usage?\s*:?\s*(\d+(?:\.\d+)?)%?',
            r'cpu\s*:?\s*(\d+(?:\.\d+)?)%',
            r'processor\s*usage?\s*:?\s*(\d+(?:\.\d+)?)%?'
        ]
        
        for pattern in cpu_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    cpu_values = [float(m) for m in matches]
                    metrics['cpu'] = {
                        'values': cpu_values,
                        'average': sum(cpu_values) / len(cpu_values),
                        'max': max(cpu_values),
                        'min': min(cpu_values)
                    }
                    break
                except:
                    pass
        
        # Memory usage patterns
        memory_patterns = [
            r'memory\s*usage?\s*:?\s*(\d+(?:\.\d+)?)%?',
            r'ram\s*usage?\s*:?\s*(\d+(?:\.\d+)?)%?',
            r'memory\s*:?\s*(\d+(?:\.\d+)?)\s*(?:gb|mb|%)',
            r'(\d+(?:\.\d+)?)\s*(?:gb|mb)\s*(?:of\s*memory|ram)'
        ]
        
        for pattern in memory_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    memory_values = [float(m) for m in matches]
                    metrics['memory'] = {
                        'values': memory_values,
                        'average': sum(memory_values) / len(memory_values),
                        'max': max(memory_values),
                        'min': min(memory_values)
                    }
                    break
                except:
                    pass
        
        # Request/traffic patterns
        request_patterns = [
            r'(\d+(?:,\d{3})*)\s*requests?',
            r'(\d+(?:,\d{3})*)\s*hits?',
            r'(\d+(?:,\d{3})*)\s*visits?',
            r'traffic\s*:?\s*(\d+(?:,\d{3})*)',
            r'(\d+(?:\.\d+)?)\s*(?:req/s|requests?\s*per\s*second)',
            r'requests?\s*:?\s*(\d+(?:,\d{3})*)',  # Handle "Total Requests: 10,000" format
            r'hits?\s*:?\s*(\d+(?:,\d{3})*)',
            r'visits?\s*:?\s*(\d+(?:,\d{3})*)'
        ]
        
        for pattern in request_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Clean up numbers (remove commas)
                    request_values = [float(m.replace(',', '')) for m in matches if m]
                    metrics['requests'] = {
                        'values': request_values,
                        'total': sum(request_values),
                        'average': sum(request_values) / len(request_values),
                        'max': max(request_values)
                    }
                    break
                except:
                    pass
        
        # Response time patterns
        response_patterns = [
            r'response\s*time\s*:?\s*(\d+(?:\.\d+)?)\s*(?:ms|seconds?)',
            r'latency\s*:?\s*(\d+(?:\.\d+)?)\s*(?:ms|seconds?)',
            r'(\d+(?:\.\d+)?)\s*ms\s*(?:response|latency)',
            r'avg\s*:?\s*(\d+(?:\.\d+)?)\s*(?:ms|seconds?)'
        ]
        
        for pattern in response_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    response_values = [float(m) for m in matches]
                    metrics['response_time'] = {
                        'values': response_values,
                        'average': sum(response_values) / len(response_values),
                        'max': max(response_values),
                        'min': min(response_values)
                    }
                    break
                except:
                    pass
        
        # Error rate patterns
        error_patterns = [
            r'error\s*rate\s*:?\s*(\d+(?:\.\d+)?)%?',
            r'(\d+(?:\.\d+)?)%?\s*errors?',
            r'error\s*:?\s*(\d+(?:\.\d+)?)%',
            r'failed\s*:?\s*(\d+(?:\.\d+)?)%?'
        ]
        
        for pattern in error_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    error_values = [float(m) for m in matches]
                    metrics['error_rate'] = {
                        'values': error_values,
                        'average': sum(error_values) / len(error_values),
                        'max': max(error_values),
                        'min': min(error_values)
                    }
                    break
                except:
                    pass
        
        return metrics
    
    async def extract_configuration_info(self, text: str) -> Dict[str, Any]:
        """Extract configuration information from text.
        
        Args:
            text: Extracted text
            
        Returns:
            Configuration information
        """
        config = {}
        
        # Server specifications
        server_patterns = {
            'cores': r'(\d+)\s*(?:cpu\s*)?cores?',
            'ram': r'(\d+(?:\.\d+)?)\s*(?:gb|mb)\s*(?:ram|memory)',
            'storage': r'(\d+(?:\.\d+)?)\s*(?:gb|tb)\s*(?:storage|disk|ssd)',
            'bandwidth': r'(\d+(?:\.\d+)?)\s*(?:gbps|mbps|gb/s|mb/s)\s*bandwidth'
        }
        
        for key, pattern in server_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    config[key] = [float(m) for m in matches]
                except:
                    config[key] = matches
        
        # Software versions
        software_patterns = {
            'php': r'php\s*(?:version\s*)?(\d+\.\d+(?:\.\d+)?)',
            'mysql': r'mysql\s*(?:version\s*)?(\d+\.\d+(?:\.\d+)?)',
            'nginx': r'nginx\s*(?:version\s*)?(\d+\.\d+(?:\.\d+)?)',
            'apache': r'apache\s*(?:version\s*)?(\d+\.\d+(?:\.\d+)?)',
            'wordpress': r'wordpress\s*(?:version\s*)?(\d+\.\d+(?:\.\d+)?)'
        }
        
        for software, pattern in software_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                config[f'{software}_version'] = matches[0]
        
        # Configuration names/tiers
        tier_patterns = [
            r'(?:tier\s*|plan\s*|config\s*)([A-Za-z]\d+)',
            r'(p\d+(?:-[a-z]+)?)',
            r'(?:configuration\s*|plan\s*)([A-Z]+\d*)'
        ]
        
        for pattern in tier_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                config['tiers'] = list(set(matches))
                break
        
        return config
    
    async def search_keywords(self, text: str, keywords: List[str]) -> Dict[str, int]:
        """Search for specific keywords in text.
        
        Args:
            text: Text to search
            keywords: Keywords to find
            
        Returns:
            Keyword counts
        """
        keyword_counts = {}
        text_lower = text.lower()
        
        for keyword in keywords:
            count = text_lower.count(keyword.lower())
            if count > 0:
                keyword_counts[keyword] = count
        
        return keyword_counts
    
    async def process(self, task: WorkerTask) -> Dict[str, Any]:
        """Process PDF file task.
        
        Args:
            task: Worker task
            
        Returns:
            Processing results
        """
        file_path = task.data_source.path
        if not file_path:
            raise ValueError("No file path provided")
        
        if not Path(file_path).exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        # Extract text from PDF
        text = await self.extract_text_from_pdf(file_path)
        
        if not text.strip():
            return {'error': 'No text extracted from PDF'}
        
        results = {
            'file_path': file_path,
            'file_size': Path(file_path).stat().st_size,
            'text_length': len(text),
            'word_count': len(text.split())
        }
        
        # Extract metrics
        metrics = await self.extract_metrics_from_text(text)
        if metrics:
            results['metrics'] = metrics
        
        # Extract configuration info
        config = await self.extract_configuration_info(text)
        if config:
            results['configuration'] = config
        
        # Search for performance-related keywords
        performance_keywords = [
            'cpu', 'memory', 'ram', 'disk', 'bandwidth', 'latency',
            'response time', 'throughput', 'requests', 'traffic',
            'load', 'performance', 'optimization', 'bottleneck',
            'cache', 'database', 'mysql', 'php', 'nginx', 'apache'
        ]
        
        keyword_counts = await self.search_keywords(text, performance_keywords)
        if keyword_counts:
            results['keyword_analysis'] = keyword_counts
        
        # Include sample text for manual review
        results['text_sample'] = text[:1000] + "..." if len(text) > 1000 else text
        
        return results