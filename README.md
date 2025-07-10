# Capacity Planning System

An intelligent local system for generating point-in-time capacity recommendations for WordPress hosting configurations. The system uses a hybrid orchestrator-worker architecture to process heterogeneous data sources and provide tiered recommendations.

## Features

- **Multi-source data processing**: Handles CSV, logs, PDFs, and API data
- **Intelligent recommendation engine**: Matches usage patterns to optimal configurations
- **Continuous learning**: Incorporates feedback to improve recommendations
- **Dual interface**: Both CLI and GUI for different use cases
- **Local execution**: Runs entirely on your machine, no cloud dependencies

## Quick Start

### Prerequisites

- Python 3.9+
- Git
- 8GB RAM minimum (16GB recommended for GUI)

### Installation

```bash
# Clone the repository
git clone https://github.com/robertliwpe/capacity-planning-system.git
cd capacity-planning-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration
```

### Usage

#### CLI Mode

```bash
# Basic analysis
python -m capacity_planner analyze --data-dir /path/to/data

# With specific configuration options
python -m capacity_planner analyze \
  --data-dir /path/to/data \
  --output report.md \
  --confidence-threshold 0.8

# Interactive mode
python -m capacity_planner interactive
```

#### GUI Mode

```bash
# Launch the GUI
python -m capacity_planner gui
```

The GUI provides:
- Drag-and-drop data file upload
- Real-time analysis progress
- Interactive configuration selection
- Export options for reports

## Architecture

### Core Components

1. **Orchestrator**: Coordinates analysis tasks and manages worker agents
2. **Data Processing Workers**: Handle different data formats (CSV, logs, PDFs)
3. **Analysis Engine**: Pattern matching and recommendation generation
4. **Learning System**: Feedback incorporation and model updates
5. **Report Generator**: Creates formatted recommendations

### Data Flow

```
Input Data → Data Workers → Analysis Engine → Recommendations → Report
     ↓                            ↓
Learning System ← Feedback ← User Review
```

## Configuration

The system uses predefined hosting configurations from `matrix_cleaned.csv`. Each configuration includes:
- Resource allocations (CPU, memory)
- Component specifications (PHP, MySQL, Nginx, etc.)
- Performance characteristics

## Project Structure

```
capacity-planning-system/
├── capacity_planner/
│   ├── __init__.py
│   ├── orchestrator/
│   ├── workers/
│   ├── analysis/
│   ├── learning/
│   ├── cli/
│   └── gui/
├── data/
│   └── configurations/
├── tests/
├── docs/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .env.example
└── .gitignore
```

## Development

See [CLAUDE.md](CLAUDE.md) for detailed implementation instructions and architecture documentation.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=capacity_planner

# Run specific test suite
pytest tests/test_analysis.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details