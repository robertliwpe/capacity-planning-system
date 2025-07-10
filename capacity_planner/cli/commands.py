"""CLI commands for capacity planner."""

import click
import asyncio
import os
from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.panel import Panel

from ..orchestrator.main import CapacityPlanningOrchestrator
from ..models.data_models import (
    AnalysisRequest, DataSource, DataSourceType, SSHConfig
)
from ..utils.config import Config
from ..utils.logging import setup_logging
from ..workers.data_processing.ssh_worker import SSHWorker

console = Console()


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--config-file', type=click.Path(), help='Configuration file path')
@click.pass_context
def cli(ctx, debug, config_file):
    """Capacity Planning System CLI."""
    ctx.ensure_object(dict)
    
    # Setup logging
    log_level = "DEBUG" if debug else "INFO"
    setup_logging(log_level=log_level, console_output=True)
    
    # Load configuration
    config = Config(config_file)
    ctx.obj['config'] = config
    
    console.print(Panel.fit(
        "[bold blue]Capacity Planning System[/bold blue]\n"
        "Automated WordPress hosting capacity analysis",
        border_style="blue"
    ))


@cli.command()
@click.option('--data-dir', type=click.Path(exists=True), help='Directory containing data files')
@click.option('--ssh-config', type=click.Path(exists=True), help='SSH configuration file')
@click.option('--pods', multiple=True, type=int, help='Pod numbers to analyze')
@click.option('--installs', multiple=True, help='Install names to analyze')
@click.option('--output', default='report.md', help='Output report file')
@click.option('--confidence-threshold', default=0.75, help='Minimum confidence score')
@click.option('--format', 'output_format', default='markdown', 
              type=click.Choice(['markdown', 'json', 'text']), help='Output format')
@click.pass_context
def analyze(ctx, data_dir, ssh_config, pods, installs, output, confidence_threshold, output_format):
    """Analyze capacity requirements using local files and SSH data collection."""
    
    config = ctx.obj['config']
    
    async def run_analysis():
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            with Progress() as progress:
                task = progress.add_task("Analyzing capacity...", total=100)
                
                # Prepare data sources
                data_sources = []
                
                # Add local file sources
                if data_dir:
                    data_sources.extend(find_local_data_files(data_dir))
                    progress.update(task, advance=20)
                
                # Add SSH sources
                if pods and installs:
                    ssh_sources = prepare_ssh_data_sources(pods, installs, config)
                    data_sources.extend(ssh_sources)
                    progress.update(task, advance=30)
                
                if not data_sources:
                    console.print("[red]No data sources specified. Use --data-dir or --pods/--installs[/red]")
                    return
                
                # Create analysis request
                request = AnalysisRequest(
                    data_sources=data_sources,
                    confidence_threshold=confidence_threshold,
                    output_format=output_format
                )
                
                progress.update(task, advance=10)
                
                # Run analysis
                result = await orchestrator.analyze(request)
                progress.update(task, advance=40)
                
                # Save report
                if result.report:
                    with open(output, 'w') as f:
                        f.write(result.report)
                    console.print(f"[green]Report saved to {output}[/green]")
                
                # Display results
                display_analysis_results(result)
                
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
        finally:
            await orchestrator.stop()
    
    asyncio.run(run_analysis())


@cli.command()
@click.option('--pod', type=int, help='Pod number to connect to')
@click.option('--host', help='Hostname to connect to')
@click.option('--username', help='SSH username')
@click.option('--key-path', type=click.Path(exists=True), help='SSH private key path')
@click.pass_context
def test_ssh(ctx, pod, host, username, key_path):
    """Test SSH connection and collect sample metrics."""
    
    config = ctx.obj['config']
    
    # Determine connection details
    if pod:
        hostname = f"pod-{pod}.wpengine.com"
    elif host:
        hostname = host
    else:
        console.print("[red]Must specify either --pod or --host[/red]")
        return
    
    ssh_username = username or config.default_ssh_user or click.prompt("SSH username")
    ssh_key_path = key_path or config.ssh_key_path
    
    async def test_connection():
        ssh_config = SSHConfig(
            hostname=hostname,
            username=ssh_username,
            key_path=ssh_key_path,
            pod_number=pod
        )
        
        worker = SSHWorker(ssh_config)
        
        try:
            console.print(f"[yellow]Connecting to {hostname}...[/yellow]")
            
            if await worker.connect():
                console.print("[green]✓ Connection successful![/green]")
                
                # Collect sample metrics
                console.print("[yellow]Collecting system metrics...[/yellow]")
                metrics = await worker.collect_system_metrics()
                
                # Display metrics table
                table = Table(title="System Metrics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Hostname", metrics.hostname)
                table.add_row("CPU Usage", f"{metrics.cpu_usage:.1f}%")
                table.add_row("Memory Usage", f"{metrics.memory_usage:.1f}%")
                table.add_row("Disk Usage", f"{metrics.disk_usage:.1f}%")
                table.add_row("Load Average", metrics.load_average)
                
                for proc_type, count in metrics.processes.items():
                    table.add_row(f"{proc_type.title()} Processes", str(count))
                
                console.print(table)
                
                # Test server functions if on a pod
                if pod:
                    console.print("\n[yellow]Testing server functions...[/yellow]")
                    
                    functions_to_test = ['whereami', 'ver', 'healthcheck -q']
                    
                    for func in functions_to_test:
                        try:
                            result = await worker.execute_server_function(func.split()[0], func.split()[1:])
                            if result:
                                console.print(f"[green]✓ {func}:[/green] {result[:100]}...")
                        except Exception as e:
                            console.print(f"[yellow]⚠ {func}:[/yellow] {str(e)[:50]}...")
                
            else:
                console.print("[red]✗ Connection failed![/red]")
                
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            await worker.disconnect()
    
    asyncio.run(test_connection())


@cli.command()
@click.option('--pods', multiple=True, type=int, help='Pod numbers to analyze')
@click.option('--installs', multiple=True, help='Install names to analyze')
@click.option('--output', default='pod_analysis.md', help='Output report file')
@click.pass_context
def analyze_pods(ctx, pods, installs, output):
    """Analyze capacity for specific pods and installs."""
    
    config = ctx.obj['config']
    
    if not pods:
        # Interactive prompt for pod numbers
        console.print("[bold blue]Enter pod numbers (press Enter when done):[/bold blue]")
        pod_list = []
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
        console.print("[bold blue]Enter install names (press Enter when done):[/bold blue]")
        install_list = []
        while True:
            install = click.prompt("Install name", default="", show_default=False)
            if not install:
                break
            install_list.append(install)
        installs = install_list
    
    if not pods or not installs:
        console.print("[red]Both pods and installs are required[/red]")
        return
    
    async def analyze_pod_data():
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Analyze each pod
            all_results = []
            
            for pod_number in pods:
                console.print(f"[yellow]Analyzing pod-{pod_number}.wpengine.com...[/yellow]")
                
                ssh_config = SSHConfig(
                    hostname=f"pod-{pod_number}.wpengine.com",
                    username=config.default_ssh_user or "admin",
                    key_path=config.ssh_key_path,
                    pod_number=pod_number
                )
                
                result = await orchestrator.analyze_single_pod(
                    pod_number, list(installs), ssh_config
                )
                
                all_results.append(result)
                
                if result.recommendations:
                    console.print(f"[green]✓ Pod {pod_number}: {result.recommendations[0].config_name} "
                                f"({result.recommendations[0].confidence_score:.1%} confidence)[/green]")
                else:
                    console.print(f"[yellow]⚠ Pod {pod_number}: No recommendations generated[/yellow]")
            
            # Generate combined report
            combined_report = generate_combined_pod_report(all_results, pods, installs)
            
            with open(output, 'w') as f:
                f.write(combined_report)
            
            console.print(f"\n[green]Combined analysis saved to {output}[/green]")
            
        except Exception as e:
            console.print(f"[red]Pod analysis failed: {e}[/red]")
        finally:
            await orchestrator.stop()
    
    asyncio.run(analyze_pod_data())


@cli.command()
@click.pass_context
def interactive(ctx):
    """Launch interactive analysis mode."""
    
    config = ctx.obj['config']
    
    console.print(Panel(
        "[bold blue]Interactive Capacity Planning Mode[/bold blue]\n"
        "Follow the prompts to configure your analysis",
        border_style="blue"
    ))
    
    # Interactive configuration
    analysis_type = click.prompt(
        "Analysis type",
        type=click.Choice(['local-files', 'ssh-pods', 'mixed']),
        default='ssh-pods'
    )
    
    data_sources = []
    
    if analysis_type in ['local-files', 'mixed']:
        data_dir = click.prompt("Data directory path", default="", show_default=False)
        if data_dir and Path(data_dir).exists():
            data_sources.extend(find_local_data_files(data_dir))
    
    if analysis_type in ['ssh-pods', 'mixed']:
        console.print("\n[bold]SSH Pod Configuration[/bold]")
        
        pods = []
        while True:
            pod = click.prompt("Pod number (or press Enter to finish)", default="", show_default=False)
            if not pod:
                break
            try:
                pods.append(int(pod))
            except ValueError:
                console.print("[red]Invalid pod number[/red]")
        
        installs = []
        if pods:
            console.print("\n[bold]Install Names[/bold]")
            while True:
                install = click.prompt("Install name (or press Enter to finish)", default="", show_default=False)
                if not install:
                    break
                installs.append(install)
        
        if pods and installs:
            ssh_sources = prepare_ssh_data_sources(pods, installs, config)
            data_sources.extend(ssh_sources)
    
    if not data_sources:
        console.print("[red]No data sources configured[/red]")
        return
    
    # Analysis options
    confidence_threshold = click.prompt("Confidence threshold", default=0.75, type=float)
    output_format = click.prompt(
        "Output format",
        type=click.Choice(['markdown', 'json', 'text']),
        default='markdown'
    )
    output_file = click.prompt("Output file", default="interactive_analysis.md")
    
    # Run analysis
    async def run_interactive_analysis():
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            request = AnalysisRequest(
                data_sources=data_sources,
                confidence_threshold=confidence_threshold,
                output_format=output_format,
                interactive=True
            )
            
            console.print("\n[yellow]Running analysis...[/yellow]")
            result = await orchestrator.analyze(request)
            
            if result.report:
                with open(output_file, 'w') as f:
                    f.write(result.report)
                console.print(f"[green]Analysis saved to {output_file}[/green]")
            
            display_analysis_results(result)
            
        except Exception as e:
            console.print(f"[red]Interactive analysis failed: {e}[/red]")
        finally:
            await orchestrator.stop()
    
    asyncio.run(run_interactive_analysis())


def find_local_data_files(data_dir: str) -> List[DataSource]:
    """Find local data files in directory."""
    data_sources = []
    data_path = Path(data_dir)
    
    # Find CSV files
    for csv_file in data_path.glob("*.csv"):
        data_sources.append(DataSource(
            type=DataSourceType.CSV,
            path=str(csv_file)
        ))
    
    # Find PDF files
    for pdf_file in data_path.glob("*.pdf"):
        data_sources.append(DataSource(
            type=DataSourceType.PDF,
            path=str(pdf_file)
        ))
    
    # Find log files
    for log_file in data_path.glob("*.log*"):
        data_sources.append(DataSource(
            type=DataSourceType.LOG,
            path=str(log_file)
        ))
    
    return data_sources


def prepare_ssh_data_sources(pods: List[int], installs: List[str], config: Config) -> List[DataSource]:
    """Prepare SSH data sources."""
    data_sources = []
    
    for pod_number in pods:
        ssh_config = SSHConfig(
            hostname=f"pod-{pod_number}.wpengine.com",
            username=config.default_ssh_user or "admin",
            key_path=config.ssh_key_path,
            pod_number=pod_number
        )
        
        data_source = DataSource(
            type=DataSourceType.SSH,
            ssh_config=ssh_config,
            install_names=list(installs),
            metadata={'pod_number': pod_number}
        )
        data_sources.append(data_source)
    
    return data_sources


def display_analysis_results(result):
    """Display analysis results in console."""
    if result.status == "failed":
        console.print(f"[red]Analysis failed: {', '.join(result.errors)}[/red]")
        return
    
    if result.recommendations:
        console.print("\n[bold green]Top Recommendations[/bold green]")
        
        table = Table()
        table.add_column("Rank", style="cyan")
        table.add_column("Configuration", style="green")
        table.add_column("Tier", style="blue")
        table.add_column("Confidence", style="magenta")
        table.add_column("Specialization", style="yellow")
        
        for i, rec in enumerate(result.recommendations[:5], 1):
            table.add_row(
                str(i),
                rec.config_name,
                str(rec.tier),
                f"{rec.confidence_score:.1%}",
                rec.specialization or "General"
            )
        
        console.print(table)
        
        # Show top recommendation details
        top_rec = result.recommendations[0]
        console.print(f"\n[bold]Top Recommendation: {top_rec.config_name}[/bold]")
        console.print("Reasoning:")
        for reason in top_rec.reasoning:
            console.print(f"  • {reason}")
        
        if top_rec.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in top_rec.warnings:
                console.print(f"  ⚠ {warning}")
    
    # Show execution summary
    console.print(f"\n[dim]Analysis completed in {result.execution_time:.1f}s[/dim]")
    
    if result.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  ⚠ {warning}")


def generate_combined_pod_report(results, pods, installs):
    """Generate combined report for multiple pods."""
    report = []
    
    report.append("# Multi-Pod Capacity Analysis Report")
    report.append(f"Pods analyzed: {', '.join(map(str, pods))}")
    report.append(f"Installs analyzed: {', '.join(installs)}")
    report.append("")
    
    for i, result in enumerate(results):
        pod_num = pods[i]
        report.append(f"## Pod {pod_num} Analysis")
        
        if result.recommendations:
            rec = result.recommendations[0]
            report.append(f"**Recommended Configuration:** {rec.config_name}")
            report.append(f"**Confidence:** {rec.confidence_score:.1%}")
            report.append(f"**Tier:** {rec.tier}")
        else:
            report.append("No recommendations generated")
        
        report.append("")
    
    return "\n".join(report)


if __name__ == '__main__':
    cli()