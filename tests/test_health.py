"""Tests for the /health endpoint"""
import pytest
from main import flask_app

def test_health_endpoint():
    """Test that /health returns HTTP 200 with correct JSON body"""
    with flask_app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json == {"status": "ok"}
