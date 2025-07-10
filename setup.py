from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="capacity-planner",
    version="0.1.0",
    author="Capacity Planning Team",
    author_email="team@example.com",
    description="Automated capacity planning system for WordPress hosting configurations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/robertliwpe/capacity-planning-system",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "capacity-planner=capacity_planner.__main__:main",
            "cp-cli=capacity_planner.cli.commands:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "capacity_planner": ["data/**/*"],
    },
)