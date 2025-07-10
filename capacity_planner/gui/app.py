"""Streamlit GUI application."""

import streamlit as st
import asyncio
import pandas as pd
from pathlib import Path
import tempfile
import os

from ..orchestrator.main import CapacityPlanningOrchestrator
from ..models.data_models import (
    AnalysisRequest, DataSource, DataSourceType, SSHConfig
)
from ..utils.config import Config
from ..utils.logging import setup_logging


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Capacity Planning System",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📊 Capacity Planning System")
    st.markdown("Automated WordPress hosting capacity analysis")
    
    # Initialize session state
    if 'config' not in st.session_state:
        st.session_state.config = Config()
        setup_logging(log_level="INFO", console_output=False)
    
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Analysis type selection
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Local Files", "SSH Pods", "Mixed"],
            help="Choose your data source type"
        )
        
        # SSH Configuration
        if analysis_type in ["SSH Pods", "Mixed"]:
            st.subheader("SSH Configuration")
            
            ssh_username = st.text_input(
                "SSH Username",
                value=st.session_state.config.default_ssh_user,
                help="Username for SSH connections"
            )
            
            ssh_key_path = st.text_input(
                "SSH Key Path",
                value=st.session_state.config.ssh_key_path,
                help="Path to SSH private key"
            )
            
            sudo_password = st.text_input(
                "Sudo Password",
                type="password",
                help="Password for sudo commands (optional)"
            )
        
        # Analysis settings
        st.subheader("Analysis Settings")
        
        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.75,
            step=0.05,
            help="Minimum confidence score for recommendations"
        )
        
        output_format = st.selectbox(
            "Output Format",
            ["markdown", "json", "text"],
            help="Format for generated reports"
        )
    
    # Main content area
    if analysis_type == "Local Files":
        show_local_files_interface()
    elif analysis_type == "SSH Pods":
        show_ssh_pods_interface(ssh_username, ssh_key_path, sudo_password)
    else:  # Mixed
        show_mixed_interface(ssh_username, ssh_key_path, sudo_password)
    
    # Analysis controls
    st.subheader("Run Analysis")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
            run_analysis(confidence_threshold, output_format)
    
    with col2:
        if st.button("📋 Test SSH Connection", use_container_width=True):
            test_ssh_connection(ssh_username, ssh_key_path)
    
    with col3:
        if st.button("🔄 Clear Results", use_container_width=True):
            st.session_state.analysis_results = None
            st.rerun()
    
    # Display results
    if st.session_state.analysis_results:
        display_analysis_results(st.session_state.analysis_results)


def show_local_files_interface():
    """Show interface for local file analysis."""
    st.subheader("📁 Local File Analysis")
    
    uploaded_files = st.file_uploader(
        "Upload data files",
        accept_multiple_files=True,
        type=['csv', 'pdf', 'log', 'txt'],
        help="Upload CSV, PDF, or log files for analysis"
    )
    
    if uploaded_files:
        st.write(f"📊 {len(uploaded_files)} files uploaded:")
        
        files_df = pd.DataFrame([
            {
                "File Name": file.name,
                "Type": file.type,
                "Size": f"{file.size / 1024:.1f} KB"
            }
            for file in uploaded_files
        ])
        
        st.dataframe(files_df, use_container_width=True)
        
        # Store files for analysis
        if 'uploaded_files' not in st.session_state:
            st.session_state.uploaded_files = {}
        
        for file in uploaded_files:
            st.session_state.uploaded_files[file.name] = file


def show_ssh_pods_interface(ssh_username, ssh_key_path, sudo_password):
    """Show interface for SSH pod analysis."""
    st.subheader("🖥️ SSH Pod Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Pod Configuration**")
        
        # Pod numbers input
        pod_input = st.text_input(
            "Pod Numbers",
            placeholder="1, 2, 3 or 1-5",
            help="Enter pod numbers separated by commas or as ranges"
        )
        
        pods = parse_pod_input(pod_input)
        if pods:
            st.success(f"✅ Configured pods: {', '.join(map(str, pods))}")
    
    with col2:
        st.write("**Install Configuration**")
        
        # Install names
        install_input = st.text_area(
            "Install Names",
            placeholder="install1\ninstall2\ninstall3",
            help="Enter install names, one per line"
        )
        
        installs = [name.strip() for name in install_input.split('\n') if name.strip()]
        if installs:
            st.success(f"✅ Configured {len(installs)} installs")
    
    # Store in session state
    st.session_state.ssh_pods = pods
    st.session_state.ssh_installs = installs
    st.session_state.ssh_config = {
        'username': ssh_username,
        'key_path': ssh_key_path,
        'sudo_password': sudo_password
    }


def show_mixed_interface(ssh_username, ssh_key_path, sudo_password):
    """Show interface for mixed analysis."""
    st.subheader("🔄 Mixed Analysis")
    
    # File upload section
    with st.expander("📁 Local Files", expanded=True):
        show_local_files_interface()
    
    # SSH configuration section
    with st.expander("🖥️ SSH Pods", expanded=True):
        show_ssh_pods_interface(ssh_username, ssh_key_path, sudo_password)


def parse_pod_input(pod_input):
    """Parse pod input string into list of pod numbers."""
    if not pod_input:
        return []
    
    pods = []
    
    try:
        for part in pod_input.split(','):
            part = part.strip()
            
            if '-' in part:
                # Handle ranges like "1-5"
                start, end = map(int, part.split('-'))
                pods.extend(range(start, end + 1))
            else:
                # Handle single numbers
                pods.append(int(part))
        
        return sorted(list(set(pods)))  # Remove duplicates and sort
    
    except ValueError:
        st.error("Invalid pod number format. Use: 1, 2, 3 or 1-5")
        return []


def test_ssh_connection(ssh_username, ssh_key_path):
    """Test SSH connection."""
    pods = getattr(st.session_state, 'ssh_pods', [])
    
    if not pods:
        st.error("No pods configured for testing")
        return
    
    if not ssh_username:
        st.error("SSH username is required")
        return
    
    async def run_ssh_test():
        from ..workers.data_processing.ssh_worker import SSHWorker
        
        test_pod = pods[0]  # Test first pod
        hostname = f"pod-{test_pod}.wpengine.com"
        
        ssh_config = SSHConfig(
            hostname=hostname,
            username=ssh_username,
            key_path=ssh_key_path,
            pod_number=test_pod
        )
        
        worker = SSHWorker(ssh_config)
        
        with st.spinner(f"Testing connection to {hostname}..."):
            try:
                if await worker.connect():
                    st.success(f"✅ Successfully connected to {hostname}")
                    
                    # Collect basic metrics
                    metrics = await worker.collect_system_metrics()
                    
                    st.write("**System Information:**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("CPU Usage", f"{metrics.cpu_usage:.1f}%")
                    with col2:
                        st.metric("Memory Usage", f"{metrics.memory_usage:.1f}%")
                    with col3:
                        st.metric("Disk Usage", f"{metrics.disk_usage:.1f}%")
                    with col4:
                        st.metric("Total Processes", metrics.processes.get('total', 0))
                    
                else:
                    st.error("❌ Connection failed")
                    
            except Exception as e:
                st.error(f"❌ Connection error: {e}")
            finally:
                await worker.disconnect()
    
    # Run async function
    asyncio.run(run_ssh_test())


def run_analysis(confidence_threshold, output_format):
    """Run capacity planning analysis."""
    
    async def run_async_analysis():
        # Prepare data sources
        data_sources = []
        
        # Add uploaded files
        if hasattr(st.session_state, 'uploaded_files'):
            temp_dir = tempfile.mkdtemp()
            
            for filename, file_obj in st.session_state.uploaded_files.items():
                temp_path = os.path.join(temp_dir, filename)
                with open(temp_path, 'wb') as f:
                    f.write(file_obj.read())
                
                # Determine file type
                if filename.endswith('.csv'):
                    file_type = DataSourceType.CSV
                elif filename.endswith('.pdf'):
                    file_type = DataSourceType.PDF
                else:
                    file_type = DataSourceType.LOG
                
                data_sources.append(DataSource(
                    type=file_type,
                    path=temp_path
                ))
        
        # Add SSH sources
        if hasattr(st.session_state, 'ssh_pods') and st.session_state.ssh_pods:
            ssh_config_data = getattr(st.session_state, 'ssh_config', {})
            installs = getattr(st.session_state, 'ssh_installs', [])
            
            for pod_number in st.session_state.ssh_pods:
                ssh_config = SSHConfig(
                    hostname=f"pod-{pod_number}.wpengine.com",
                    username=ssh_config_data.get('username', ''),
                    key_path=ssh_config_data.get('key_path', ''),
                    pod_number=pod_number
                )
                
                data_source = DataSource(
                    type=DataSourceType.SSH,
                    ssh_config=ssh_config,
                    install_names=installs,
                    metadata={'pod_number': pod_number}
                )
                data_sources.append(data_source)
        
        if not data_sources:
            st.error("No data sources configured")
            return
        
        # Create analysis request
        request = AnalysisRequest(
            data_sources=data_sources,
            confidence_threshold=confidence_threshold,
            output_format=output_format
        )
        
        # Run analysis
        orchestrator = CapacityPlanningOrchestrator(st.session_state.config)
        
        try:
            await orchestrator.start()
            
            with st.spinner("Running capacity analysis..."):
                result = await orchestrator.analyze(request)
            
            st.session_state.analysis_results = result
            
            if result.status == "completed":
                st.success("✅ Analysis completed successfully!")
            else:
                st.error("❌ Analysis failed")
                for error in result.errors:
                    st.error(error)
            
        except Exception as e:
            st.error(f"Analysis error: {e}")
        finally:
            await orchestrator.stop()
    
    # Run analysis
    asyncio.run(run_async_analysis())
    st.rerun()


def display_analysis_results(result):
    """Display analysis results."""
    st.subheader("📊 Analysis Results")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Status", result.status.title())
    with col2:
        st.metric("Recommendations", len(result.recommendations))
    with col3:
        st.metric("Execution Time", f"{result.execution_time:.1f}s")
    with col4:
        confidence = result.recommendations[0].confidence_score if result.recommendations else 0
        st.metric("Top Confidence", f"{confidence:.1%}")
    
    if result.recommendations:
        # Recommendations table
        st.subheader("🏆 Configuration Recommendations")
        
        recommendations_data = []
        for i, rec in enumerate(result.recommendations[:10], 1):
            recommendations_data.append({
                "Rank": i,
                "Configuration": rec.config_name,
                "Tier": rec.tier,
                "Confidence": f"{rec.confidence_score:.1%}",
                "Specialization": rec.specialization or "General",
                "Estimated RPS": rec.estimated_capacity.get('requests_per_second', 0)
            })
        
        st.dataframe(
            pd.DataFrame(recommendations_data),
            use_container_width=True,
            hide_index=True
        )
        
        # Top recommendation details
        with st.expander("🔍 Top Recommendation Details", expanded=True):
            top_rec = result.recommendations[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Configuration Details**")
                st.write(f"• **Name:** {top_rec.config_name}")
                st.write(f"• **Tier:** {top_rec.tier}")
                st.write(f"• **Confidence:** {top_rec.confidence_score:.1%}")
                if top_rec.specialization:
                    st.write(f"• **Specialization:** {top_rec.specialization}")
                if top_rec.size:
                    st.write(f"• **Size:** {top_rec.size}")
            
            with col2:
                st.write("**Estimated Capacity**")
                for key, value in top_rec.estimated_capacity.items():
                    if isinstance(value, (int, float)):
                        if key == "requests_per_second":
                            st.write(f"• **RPS:** {value:.0f}")
                        elif key == "concurrent_users":
                            st.write(f"• **Concurrent Users:** {value:,}")
                        elif key == "storage_gb":
                            st.write(f"• **Storage:** {value:.0f} GB")
            
            st.write("**Reasoning**")
            for reason in top_rec.reasoning:
                st.write(f"• {reason}")
            
            if top_rec.warnings:
                st.warning("**Warnings:**")
                for warning in top_rec.warnings:
                    st.write(f"⚠️ {warning}")
    
    # Report download
    if result.report:
        st.subheader("📄 Generated Report")
        
        st.download_button(
            label="📥 Download Report",
            data=result.report,
            file_name=f"capacity_analysis_{result.timestamp.strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
        
        with st.expander("👁️ Preview Report"):
            st.markdown(result.report)
    
    # Errors and warnings
    if result.errors:
        st.error("**Errors:**")
        for error in result.errors:
            st.write(f"❌ {error}")
    
    if result.warnings:
        st.warning("**Warnings:**")
        for warning in result.warnings:
            st.write(f"⚠️ {warning}")


if __name__ == "__main__":
    main()