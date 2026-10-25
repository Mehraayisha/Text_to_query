# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MongoDB Agent AI - Setup Configuration
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="mongodb-nl-query-ai-agent",
    version="1.0.0",
    author="MongoDB Agent Contributors",
    author_email="mongodb-agent@example.com",
    description="AI-powered agent for querying MongoDB databases using natural language",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cisco-open/mongodb-nl-query-ai-agent",
    project_urls={
        "Bug Tracker": "https://github.com/cisco-open/mongodb-nl-query-ai-agent/issues",
        "Documentation": "https://github.com/cisco-open/mongodb-nl-query-ai-agent/tree/main/docs",
        "Source Code": "https://github.com/cisco-open/mongodb-nl-query-ai-agent",
    },
    packages=find_packages(where="src", exclude=["tests", "examples", "docs"]),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pymongo>=4.0.0",
        "langchain>=0.1.0",
        "langchain-core>=0.1.0",
        "langgraph>=0.0.1",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
        "requests>=2.28.0",
    ],
    extras_require={
        "openai": ["langchain-openai>=0.0.1"],
        "anthropic": ["langchain-anthropic>=0.0.1"],
        "bedrock": ["langchain-aws>=0.0.1", "boto3>=1.28.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "mongodb-agent=mongodb_agent.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "mongodb_agent": ["semantic_models/*.yaml"],
    },
    keywords="mongodb ai agent natural-language llm langchain database query",
    license="MIT",
)
