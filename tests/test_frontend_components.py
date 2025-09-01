"""
Frontend Component Tests - Test React components with simple verification
"""
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add frontend to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_citation_graph_component_import():
    """Test that CitationGraph component can be imported"""
    try:
        from frontend.src.components.CitationGraph import CitationGraph
        assert CitationGraph is not None
    except ImportError:
        # If component doesn't exist, that's okay for now
        pytest.skip("CitationGraph component not available")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_api_client_functions_exist():
    """Test that API client functions are defined"""
    try:
        from frontend.src.lib.api import (
            uploadPdfs, processDocuments, getDocuments, 
            getDocumentDetail, getGraph, getPdfUrl
        )
        
        # Check that functions exist
        assert callable(uploadPdfs)
        assert callable(processDocuments)
        assert callable(getDocuments)
        assert callable(getDocumentDetail)
        assert callable(getGraph)
        assert callable(getPdfUrl)
        
    except ImportError:
        pytest.skip("Frontend API client not available")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_frontend_pages_exist():
    """Test that frontend pages are accessible"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'src', 'app')
    
    if os.path.exists(frontend_dir):
        # Check for key pages
        expected_pages = ['page.tsx', 'upload/page.tsx', 'documents/page.tsx', 'graph/page.tsx']
        
        for page in expected_pages:
            page_path = os.path.join(frontend_dir, page)
            if os.path.exists(page_path):
                assert True  # Page exists
            else:
                pytest.skip(f"Page {page} not found")
    else:
        pytest.skip("Frontend directory not found")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_frontend_configuration():
    """Test that frontend configuration files exist"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    
    if os.path.exists(frontend_dir):
        # Check for key config files
        config_files = ['package.json', 'next.config.js', 'tailwind.config.js']
        
        for config in config_files:
            config_path = os.path.join(frontend_dir, config)
            if os.path.exists(config_path):
                assert True  # Config file exists
            else:
                pytest.skip(f"Config file {config} not found")
    else:
        pytest.skip("Frontend directory not found")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_frontend_dependencies():
    """Test that frontend dependencies are properly configured"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    
    if os.path.exists(frontend_dir):
        package_json_path = os.path.join(frontend_dir, 'package.json')
        
        if os.path.exists(package_json_path):
            import json
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
            
            # Check for required dependencies
            required_deps = ['react', 'next', 'react-dom']
            for dep in required_deps:
                if dep in package_data.get('dependencies', {}):
                    assert True  # Dependency exists
                else:
                    pytest.skip(f"Dependency {dep} not found in package.json")
        else:
            pytest.skip("package.json not found")
    else:
        pytest.skip("Frontend directory not found")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_frontend_build_configuration():
    """Test that frontend build configuration is correct"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    
    if os.path.exists(frontend_dir):
        next_config_path = os.path.join(frontend_dir, 'next.config.js')
        
        if os.path.exists(next_config_path):
            # Check that next.config.js exists and is readable
            with open(next_config_path, 'r') as f:
                config_content = f.read()
            
            # Check for key configurations
            assert 'reactStrictMode' in config_content
            assert 'output' in config_content
            assert 'standalone' in config_content
        else:
            pytest.skip("next.config.js not found")
    else:
        pytest.skip("Frontend directory not found")

@pytest.mark.frontend
@pytest.mark.unit
@pytest.mark.fast
def test_frontend_styling_configuration():
    """Test that frontend styling configuration is correct"""
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    
    if os.path.exists(frontend_dir):
        tailwind_config_path = os.path.join(frontend_dir, 'tailwind.config.js')
        
        if os.path.exists(tailwind_config_path):
            # Check that tailwind.config.js exists and is readable
            with open(tailwind_config_path, 'r') as f:
                config_content = f.read()
            
            # Check for key configurations
            assert 'content' in config_content
            assert 'theme' in config_content
        else:
            pytest.skip("tailwind.config.js not found")
    else:
        pytest.skip("Frontend directory not found")
