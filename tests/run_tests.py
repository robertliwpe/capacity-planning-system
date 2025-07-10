#!/usr/bin/env python3
"""Test runner script to run all tests and generate coverage report."""

import sys
import subprocess
import os
from pathlib import Path


def run_tests():
    """Run all tests with coverage reporting."""
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
    
    print("🧪 Running Capacity Planning System Test Suite")
    print("=" * 60)
    
    # Change to project directory
    os.chdir(project_root)
    
    # Install package in development mode if not already installed
    print("📦 Installing package in development mode...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-e", "."
        ], check=True, capture_output=True)
        print("✅ Package installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install package: {e}")
        return False
    
    # Run tests with pytest and coverage
    test_commands = [
        # Basic test run
        [
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v", 
            "--tb=short",
            "--durations=10"
        ],
        
        # Coverage report
        [
            sys.executable, "-m", "pytest", 
            "tests/", 
            "--cov=capacity_planner",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=70"
        ]
    ]
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n🔍 Test Run {i}/{len(test_commands)}")
        print("-" * 40)
        
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                print(f"⚠️  Test run {i} completed with warnings/failures")
            else:
                print(f"✅ Test run {i} completed successfully")
        except Exception as e:
            print(f"❌ Test run {i} failed: {e}")
            return False
    
    # Generate test summary
    print("\n📊 Test Summary")
    print("-" * 40)
    
    # Check if coverage report was generated
    coverage_file = project_root / "htmlcov" / "index.html"
    if coverage_file.exists():
        print(f"📈 Coverage report generated: {coverage_file}")
    
    # List test files
    test_files = list(Path("tests").glob("test_*.py"))
    print(f"📁 Test files executed: {len(test_files)}")
    for test_file in sorted(test_files):
        print(f"   • {test_file}")
    
    print("\n🎯 Quick Test Commands:")
    print("   Run all tests:           pytest tests/")
    print("   Run specific test:       pytest tests/test_models.py")
    print("   Run with coverage:       pytest tests/ --cov=capacity_planner")
    print("   Run integration tests:   pytest tests/test_integration.py")
    print("   Run worker tests:        pytest tests/test_workers.py -v")
    
    print("\n🐛 Debugging Commands:")
    print("   Run with verbose output: pytest tests/ -v -s")
    print("   Run specific test method: pytest tests/test_models.py::TestSSHConfig::test_valid_ssh_config")
    print("   Drop into debugger on failure: pytest tests/ --pdb")
    
    return True


def run_specific_test_category():
    """Run tests by category."""
    
    categories = {
        "models": "tests/test_models.py",
        "workers": "tests/test_workers.py", 
        "orchestrator": "tests/test_orchestrator.py",
        "analysis": "tests/test_analysis.py",
        "utils": "tests/test_utils.py",
        "integration": "tests/test_integration.py"
    }
    
    print("\n🏷️  Available test categories:")
    for name, path in categories.items():
        print(f"   {name:12} - {path}")
    
    print("\nTo run a specific category:")
    print("   python tests/run_tests.py models")
    print("   python tests/run_tests.py workers")
    print("   python tests/run_tests.py integration")
    
    # If category specified as argument
    if len(sys.argv) > 1:
        category = sys.argv[1].lower()
        if category in categories:
            print(f"\n🎯 Running {category} tests...")
            subprocess.run([
                sys.executable, "-m", "pytest", 
                categories[category], 
                "-v"
            ])
        else:
            print(f"❌ Unknown category: {category}")
            return False
    
    return True


def check_test_dependencies():
    """Check if test dependencies are installed."""
    
    required_packages = [
        "pytest",
        "pytest-cov", 
        "pytest-asyncio",
        "pytest-mock"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing test dependencies:")
        for package in missing_packages:
            print(f"   • {package}")
        print("\nInstall with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All test dependencies are installed")
    return True


def main():
    """Main test runner function."""
    
    print("🔧 Checking test environment...")
    
    # Check dependencies
    if not check_test_dependencies():
        sys.exit(1)
    
    # Run tests based on arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("\nUsage:")
            print("   python tests/run_tests.py           # Run all tests")
            print("   python tests/run_tests.py models    # Run model tests")
            print("   python tests/run_tests.py workers   # Run worker tests")
            print("   python tests/run_tests.py --help    # Show this help")
            return
        else:
            run_specific_test_category()
    else:
        # Run all tests
        success = run_tests()
        if not success:
            sys.exit(1)
    
    print("\n🎉 Test execution completed!")


if __name__ == "__main__":
    main()