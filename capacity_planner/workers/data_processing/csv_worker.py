"""CSV file processing worker."""

import csv
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import chardet

from ..base import BaseWorker
from ...models.data_models import WorkerTask


class CSVWorker(BaseWorker):
    """Worker for CSV file processing."""
    
    def __init__(self):
        """Initialize CSV worker."""
        super().__init__()
    
    async def detect_encoding(self, file_path: str) -> str:
        """Detect file encoding.
        
        Args:
            file_path: Path to file
            
        Returns:
            Detected encoding
        """
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'
    
    async def read_csv(self, file_path: str, encoding: Optional[str] = None) -> pd.DataFrame:
        """Read CSV file into DataFrame.
        
        Args:
            file_path: Path to CSV file
            encoding: File encoding (auto-detected if not provided)
            
        Returns:
            Pandas DataFrame
        """
        if not encoding:
            encoding = await self.detect_encoding(file_path)
        
        try:
            # Try reading with pandas
            df = pd.read_csv(file_path, encoding=encoding)
            return df
        except Exception as e:
            self.logger.warning(f"Failed to read with pandas, trying alternative: {e}")
            
            # Fallback to manual parsing
            data = []
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if headers:
                    for row in reader:
                        if len(row) == len(headers):
                            data.append(dict(zip(headers, row)))
            
            return pd.DataFrame(data)
    
    async def analyze_usage_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze usage data from CSV.
        
        Args:
            df: DataFrame with usage data
            
        Returns:
            Analysis results
        """
        analysis = {
            'row_count': len(df),
            'columns': list(df.columns),
            'data_types': df.dtypes.to_dict(),
            'metrics': {}
        }
        
        # Identify numeric columns
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        
        # Calculate statistics for numeric columns
        for col in numeric_cols:
            if col in df.columns:
                analysis['metrics'][col] = {
                    'mean': df[col].mean(),
                    'median': df[col].median(),
                    'std': df[col].std(),
                    'min': df[col].min(),
                    'max': df[col].max(),
                    'percentile_95': df[col].quantile(0.95),
                    'percentile_99': df[col].quantile(0.99)
                }
        
        # Detect time-based columns
        time_cols = []
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                    time_cols.append(col)
                except:
                    pass
        
        if time_cols:
            analysis['time_columns'] = time_cols
            # Analyze time-based patterns
            primary_time_col = time_cols[0]
            df_sorted = df.sort_values(by=primary_time_col)
            
            # Calculate time range
            analysis['time_range'] = {
                'start': str(df_sorted[primary_time_col].min()),
                'end': str(df_sorted[primary_time_col].max()),
                'duration_days': (df_sorted[primary_time_col].max() - 
                                df_sorted[primary_time_col].min()).days
            }
        
        # Look for specific metrics
        if 'cpu' in ' '.join(df.columns).lower():
            cpu_cols = [col for col in df.columns if 'cpu' in col.lower()]
            for col in cpu_cols:
                if col in numeric_cols:
                    analysis['cpu_metrics'] = {
                        'column': col,
                        'average': df[col].mean(),
                        'peak': df[col].max(),
                        'high_usage_count': len(df[df[col] > 80])  # > 80%
                    }
        
        if 'memory' in ' '.join(df.columns).lower():
            mem_cols = [col for col in df.columns if 'memory' in col.lower() or 'mem' in col.lower()]
            for col in mem_cols:
                if col in numeric_cols:
                    analysis['memory_metrics'] = {
                        'column': col,
                        'average': df[col].mean(),
                        'peak': df[col].max(),
                        'high_usage_count': len(df[df[col] > 80])  # > 80%
                    }
        
        # Look for request/traffic data
        request_cols = [col for col in df.columns if any(
            keyword in col.lower() 
            for keyword in ['request', 'traffic', 'hits', 'visits', 'pageviews']
        )]
        
        if request_cols and request_cols[0] in numeric_cols:
            req_col = request_cols[0]
            analysis['traffic_metrics'] = {
                'column': req_col,
                'total': df[req_col].sum(),
                'average': df[req_col].mean(),
                'peak': df[req_col].max(),
                'percentile_95': df[req_col].quantile(0.95)
            }
        
        return analysis
    
    async def extract_configuration_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract configuration data from CSV.
        
        Args:
            df: DataFrame with configuration data
            
        Returns:
            List of configuration dictionaries
        """
        configs = []
        
        # Common configuration column patterns
        config_patterns = {
            'name': ['config', 'name', 'configuration', 'tier'],
            'cpu': ['cpu', 'processor', 'cores'],
            'memory': ['memory', 'ram', 'mem'],
            'disk': ['disk', 'storage', 'space'],
            'tier': ['tier', 'level', 'plan']
        }
        
        # Map columns to standard names
        column_mapping = {}
        for std_name, patterns in config_patterns.items():
            for col in df.columns:
                if any(pattern in col.lower() for pattern in patterns):
                    column_mapping[std_name] = col
                    break
        
        # Extract configurations
        for _, row in df.iterrows():
            config = {}
            
            # Map standard fields
            for std_name, col_name in column_mapping.items():
                if col_name in row:
                    config[std_name] = row[col_name]
            
            # Include all other columns
            for col in df.columns:
                if col not in column_mapping.values():
                    config[col] = row[col]
            
            configs.append(config)
        
        return configs
    
    async def process(self, task: WorkerTask) -> Dict[str, Any]:
        """Process CSV file task.
        
        Args:
            task: Worker task
            
        Returns:
            Processing results
        """
        file_path = task.data_source.path
        if not file_path:
            raise ValueError("No file path provided")
        
        if not Path(file_path).exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        # Read CSV file
        df = await self.read_csv(file_path)
        
        # Determine task type
        task_type = task.parameters.get('type', 'auto')
        
        if task_type == 'auto':
            # Auto-detect based on content
            columns_lower = [col.lower() for col in df.columns]
            
            if any('config' in col for col in columns_lower):
                task_type = 'configuration'
            elif any(metric in ' '.join(columns_lower) 
                    for metric in ['cpu', 'memory', 'request', 'traffic']):
                task_type = 'usage'
            else:
                task_type = 'generic'
        
        results = {
            'file_path': file_path,
            'file_size': Path(file_path).stat().st_size,
            'row_count': len(df),
            'column_count': len(df.columns),
            'task_type': task_type
        }
        
        if task_type == 'usage':
            results['analysis'] = await self.analyze_usage_data(df)
        elif task_type == 'configuration':
            results['configurations'] = await self.extract_configuration_data(df)
        else:
            # Generic analysis
            results['summary'] = {
                'columns': list(df.columns),
                'dtypes': df.dtypes.to_dict(),
                'null_counts': df.isnull().sum().to_dict(),
                'unique_counts': {col: df[col].nunique() for col in df.columns}
            }
            
            # Sample data
            results['sample'] = df.head(10).to_dict('records')
        
        return results