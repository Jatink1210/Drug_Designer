"""
Integration tests for authentication endpoints
"""

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.db import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Test database setup
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/drug_designer_test"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client():
    """Test client fixture"""
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_register_user(client):
    """Test user registration"""
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test User"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert "id" in data
    assert "password" not in data  # Password should not be returned


def test_register_duplicate_email(client):
    """Test registration with duplicate email"""
    # First registration
    client.post("/api/v1/auth/register", json={
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
        "full_name": "User One"
    })
    
    # Second registration with same email
    response = client.post("/api/v1/auth/register", json={
        "email": "duplicate@example.com",
        "password": "DifferentPassword456!",
        "full_name": "User Two"
    })
    
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_success(client):
    """Test successful login"""
    # Register user first
    client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "SecurePassword123!",
        "full_name": "Login User"
    })
    
    # Login
    response = client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "SecurePassword123!"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "WrongPassword123!"
    })
    
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_wrong_password(client):
    """Test login with wrong password"""
    # Register user
    client.post("/api/v1/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "CorrectPassword123!",
        "full_name": "Test User"
    })
    
    # Login with wrong password
    response = client.post("/api/v1/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "WrongPassword123!"
    })
    
    assert response.status_code == 401


def test_refresh_token(client):
    """Test token refresh"""
    # Register and login
    client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com",
        "password": "SecurePassword123!",
        "full_name": "Refresh User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "refresh@example.com",
        "password": "SecurePassword123!"
    })
    
    refresh_token = login_response.json()["refresh_token"]
    
    # Refresh token
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_get_current_user(client):
    """Test getting current user info"""
    # Register and login
    client.post("/api/v1/auth/register", json={
        "email": "current@example.com",
        "password": "SecurePassword123!",
        "full_name": "Current User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "current@example.com",
        "password": "SecurePassword123!"
    })
    
    access_token = login_response.json()["access_token"]
    
    # Get current user
    response = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {access_token}"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "current@example.com"
    assert data["full_name"] == "Current User"


def test_unauthorized_access(client):
    """Test accessing protected endpoint without token"""
    response = client.get("/api/v1/auth/me")
    
    assert response.status_code == 401


def test_invalid_token(client):
    """Test accessing protected endpoint with invalid token"""
    response = client.get("/api/v1/auth/me", headers={
        "Authorization": "Bearer invalid_token_here"
    })
    
    assert response.status_code == 401


def test_logout(client):
    """Test user logout"""
    # Register and login
    client.post("/api/v1/auth/register", json={
        "email": "logout@example.com",
        "password": "SecurePassword123!",
        "full_name": "Logout User"
    })
    
    login_response = client.post("/api/v1/auth/login", json={
        "email": "logout@example.com",
        "password": "SecurePassword123!"
    })
    
    access_token = login_response.json()["access_token"]
    
    # Logout
    response = client.post("/api/v1/auth/logout", headers={
        "Authorization": f"Bearer {access_token}"
    })
    
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


def test_password_reset_request(client):
    """Test password reset request"""
    # Register user
    client.post("/api/v1/auth/register", json={
        "email": "reset@example.com",
        "password": "SecurePassword123!",
        "full_name": "Reset User"
    })
    
    # Request password reset
    response = client.post("/api/v1/auth/password-reset-request", json={
        "email": "reset@example.com"
    })
    
    assert response.status_code == 200
    assert "reset link" in response.json()["message"].lower()


def test_rate_limiting(client):
    """Test rate limiting on login endpoint"""
    # Attempt multiple failed logins
    for _ in range(10):
        client.post("/api/v1/auth/login", json={
            "email": "ratelimit@example.com",
            "password": "WrongPassword123!"
        })
    
    # Next attempt should be rate limited
    response = client.post("/api/v1/auth/login", json={
        "email": "ratelimit@example.com",
        "password": "WrongPassword123!"
    })
    
    assert response.status_code == 429  # Too Many Requests
