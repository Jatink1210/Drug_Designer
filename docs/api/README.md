# Drug Designer API Documentation

## Overview

The Drug Designer API is a RESTful API that provides access to the Drug Designer platform's features and data. This documentation covers all available endpoints, authentication, request/response formats, and error handling.

**Task**: 17.1 Write API documentation  
**Priority**: P2  
**Requirements**: Documentation

**Base URL**: `http://localhost:8000/api` (development)  
**Production URL**: `https://api.drugdesigner.com/api`  
**API Version**: v1  
**Protocol**: HTTPS (production), HTTP (development)

## Table of Contents

1. [Authentication](#authentication)
2. [Request/Response Format](#requestresponse-format)
3. [Error Handling](#error-handling)
4. [Rate Limiting](#rate-limiting)
5. [Endpoints](#endpoints)
   - [Authentication](#authentication-endpoints)
   - [Projects](#projects-endpoints)
   - [Disease Intelligence](#disease-intelligence-endpoints)
   - [Target Prioritization](#target-prioritization-endpoints)
   - [Evidence](#evidence-endpoints)
   - [Knowledge Graph](#knowledge-graph-endpoints)
   - [Pathways](#pathways-endpoints)
   - [Clinical Workflow](#clinical-workflow-endpoints)
   - [Dossiers](#dossiers-endpoints)
   - [Runtime](#runtime-endpoints)
6. [WebSocket API](#websocket-api)
7. [Examples](#examples)

## Authentication

### JWT Authentication

The API uses JWT (JSON Web Token) for authentication. Include the token in the `Authorization` header:

```http
Authorization: Bearer <your-jwt-token>
```

### Obtaining a Token

**POST** `/api/auth/login`

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "user": {
      "id": "user-123",
      "email": "user@example.com",
      "display_name": "John Doe",
      "role": "collaborator"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### Token Expiration

- **Access Token**: 15 minutes
- **Refresh Token**: 7 days

### Refreshing Tokens

**POST** `/api/auth/refresh`

```json
{
  "refresh_token": "your-refresh-token"
}
```

## Request/Response Format

### Universal Envelope

All API responses use a universal envelope format:

```json
{
  "status": "success" | "error" | "degraded",
  "data": { ... },
  "errors": [ ... ],
  "degraded": { ... },
  "provenance": { ... },
  "timing": { ... }
}
```

### Success Response

```json
{
  "status": "success",
  "data": {
    "id": "123",
    "name": "My Project"
  },
  "provenance": {
    "sources": ["pubmed", "uniprot"],
    "generated_at": "2024-01-15T10:30:00Z",
    "runtime_mode": "hosted"
  },
  "timing": {
    "started_at": "2024-01-15T10:30:00Z",
    "elapsed_ms": 1234
  }
}
```

### Error Response

```json
{
  "status": "error",
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Invalid email format",
      "field": "email"
    }
  ]
}
```

### Degraded Response

When some data sources fail but the request partially succeeds:

```json
{
  "status": "degraded",
  "data": { ... },
  "degraded": {
    "failed_sources": ["source1", "source2"],
    "partial_results": true,
    "message": "Some data sources unavailable"
  }
}
```

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Request validation failed |
| `AUTHENTICATION_ERROR` | Authentication failed |
| `AUTHORIZATION_ERROR` | Insufficient permissions |
| `NOT_FOUND` | Resource not found |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INTERNAL_ERROR` | Internal server error |
| `SERVICE_UNAVAILABLE` | Service temporarily unavailable |
| `CIRCUIT_BREAKER_OPEN` | External service unavailable |

## Rate Limiting

### Limits

- **Authenticated Users**: 100 requests/minute
- **Unauthenticated**: 20 requests/minute

### Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

### Rate Limit Exceeded

**Response** (429):
```json
{
  "status": "error",
  "errors": [
    {
      "code": "RATE_LIMIT_EXCEEDED",
      "message": "Rate limit exceeded. Try again in 60 seconds.",
      "retry_after": 60
    }
  ]
}
```

## Endpoints

### Authentication Endpoints

#### POST /api/auth/login

Authenticate user and obtain JWT tokens.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "user": {
      "id": "user-123",
      "email": "user@example.com",
      "display_name": "John Doe",
      "role": "collaborator"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### POST /api/auth/register

Register a new user account.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "display_name": "John Doe"
}
```

**Response** (201):
```json
{
  "status": "success",
  "data": {
    "user": {
      "id": "user-123",
      "email": "user@example.com",
      "display_name": "John Doe",
      "role": "collaborator"
    }
  }
}
```

#### POST /api/auth/refresh

Refresh access token using refresh token.

**Request**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### Projects Endpoints

#### GET /api/projects

List all projects for the authenticated user.

**Query Parameters**:
- `limit` (optional): Number of results (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "projects": [
      {
        "id": "proj-123",
        "title": "IPEX Syndrome Research",
        "description": "Investigating IPEX syndrome targets",
        "owner_id": "user-123",
        "created_at": "2024-01-15T10:30:00Z",
        "last_active": "2024-01-20T15:45:00Z"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

#### POST /api/projects

Create a new project.

**Request**:
```json
{
  "title": "IPEX Syndrome Research",
  "description": "Investigating IPEX syndrome targets"
}
```

**Response** (201):
```json
{
  "status": "success",
  "data": {
    "id": "proj-123",
    "title": "IPEX Syndrome Research",
    "description": "Investigating IPEX syndrome targets",
    "owner_id": "user-123",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### GET /api/projects/{project_id}

Get project details.

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "id": "proj-123",
    "title": "IPEX Syndrome Research",
    "description": "Investigating IPEX syndrome targets",
    "owner_id": "user-123",
    "members": [
      {
        "user_id": "user-456",
        "role": "collaborator",
        "joined_at": "2024-01-16T09:00:00Z"
      }
    ],
    "created_at": "2024-01-15T10:30:00Z",
    "last_active": "2024-01-20T15:45:00Z"
  }
}
```

### Disease Intelligence Endpoints

#### POST /api/disease/intelligence

Run disease intelligence pipeline.

**Request**:
```json
{
  "query": "IPEX syndrome",
  "sources": ["pubmed", "uniprot", "disgenet"],
  "include_indian_context": true
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "run_id": "run-123",
    "normalized_label": "IPEX",
    "identifiers": {
      "mondo": "MONDO:0007915",
      "omim": ["304790"],
      "mesh": "D007153"
    },
    "synonyms": ["IPEX", "Immune dysregulation, polyendocrinopathy, enteropathy, X-linked"],
    "candidate_genes": [
      {
        "gene_symbol": "FOXP3",
        "uniprot_id": "Q9BZS1",
        "score": 0.95,
        "source_count": 12,
        "sources": ["pubmed", "uniprot", "disgenet"],
        "evidence_ids": ["ev-1", "ev-2"]
      }
    ],
    "contradiction_count": 0,
    "confidence": 0.92
  },
  "provenance": {
    "sources": ["pubmed", "uniprot", "disgenet"],
    "generated_at": "2024-01-15T10:30:00Z",
    "runtime_mode": "hosted"
  },
  "timing": {
    "started_at": "2024-01-15T10:30:00Z",
    "elapsed_ms": 15234
  }
}
```

### Clinical Workflow Endpoints

#### POST /api/clinical/ingest

Ingest EHR data (Stage 1).

**Request**:
```json
{
  "record_type": "ehr",
  "raw_text": "Patient presents with chronic diarrhea...",
  "patient_id": "patient-123"
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "record_id": "rec-123",
    "structured_data": {
      "phenotypes": [
        {"term": "Chronic diarrhea", "hpo_id": "HP:0002028", "severity": "moderate"}
      ],
      "medications": ["Prednisone"],
      "diagnoses": ["IPEX syndrome"]
    },
    "phi_redacted": true
  }
}
```

#### POST /api/clinical/phenotype-cluster

Cluster phenotypes (Stage 2).

**Request**:
```json
{
  "ehr_record_ids": ["rec-123", "rec-456"],
  "min_cluster_size": 3
}
```

**Response** (200):
```json
{
  "status": "success",
  "data": {
    "run_id": "run-456",
    "clusters": [
      {
        "cluster_id": 1,
        "phenotypes": [
          {"term": "Chronic diarrhea", "hpo_id": "HP:0002028"},
          {"term": "Eczema", "hpo_id": "HP:0000964"}
        ],
        "size": 5,
        "rarity_score": 0.85,
        "representative_terms": ["Chronic diarrhea", "Eczema"]
      }
    ]
  }
}
```

## WebSocket API

### Connection

Connect to WebSocket for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/runs/{run_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress update:', data);
};
```

### Message Format

```json
{
  "type": "progress",
  "run_id": "run-123",
  "stage": "ehr_ingestion",
  "progress": 45,
  "message": "Processing EHR records...",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Message Types

- `progress`: Progress update
- `complete`: Stage completed
- `error`: Error occurred
- `status`: Status update

## Examples

### Complete Disease Intelligence Workflow

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'

# 2. Create Project
curl -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"IPEX Research","description":"IPEX syndrome investigation"}'

# 3. Run Disease Intelligence
curl -X POST http://localhost:8000/api/disease/intelligence \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"IPEX syndrome"}'

# 4. Get Results
curl -X GET http://localhost:8000/api/runs/{run_id} \
  -H "Authorization: Bearer <token>"
```

### Python Example

```python
import requests

# Login
response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={'email': 'user@example.com', 'password': 'password123'}
)
token = response.json()['data']['access_token']

# Create Project
headers = {'Authorization': f'Bearer {token}'}
response = requests.post(
    'http://localhost:8000/api/projects',
    headers=headers,
    json={'title': 'IPEX Research', 'description': 'IPEX syndrome investigation'}
)
project_id = response.json()['data']['id']

# Run Disease Intelligence
response = requests.post(
    'http://localhost:8000/api/disease/intelligence',
    headers=headers,
    json={'query': 'IPEX syndrome'}
)
run_id = response.json()['data']['run_id']

# Get Results
response = requests.get(
    f'http://localhost:8000/api/runs/{run_id}',
    headers=headers
)
results = response.json()['data']
```

## Support

For questions or issues:
- API Status: http://status.drugdesigner.com
- Documentation: https://docs.drugdesigner.com
- Support: support@drugdesigner.com

---

**Last Updated**: Task 17.1 Implementation  
**Version**: 1.0  
**Status**: Complete
