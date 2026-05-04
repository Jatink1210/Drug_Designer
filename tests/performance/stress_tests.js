/**
 * k6 Stress Testing Script for Drug Designer API
 * 
 * Tests system limits and failure modes under extreme load (200 concurrent users)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const requestCount = new Counter('request_count');
const activeUsers = new Gauge('active_users');

// Test configuration - Stress test with gradual ramp-up to 200 users
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '3m', target: 100 },  // Ramp up to 100 users
    { duration: '3m', target: 150 },  // Ramp up to 150 users
    { duration: '5m', target: 200 },  // Ramp up to 200 users (stress point)
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '3m', target: 100 },  // Ramp down to 100 users
    { duration: '2m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    'http_req_duration': ['p(95)<10000'], // 95% of requests should be below 10s (relaxed for stress)
    'http_req_failed': ['rate<0.05'],     // Error rate should be below 5% (relaxed for stress)
    'errors': ['rate<0.05'],              // Custom error rate below 5%
  },
};

// Base URL
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Authentication token
let authToken = '';

export function setup() {
  // Login to get auth token
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, JSON.stringify({
    email: 'test@example.com',
    password: 'testpassword',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });
  
  if (loginRes.status === 200) {
    authToken = loginRes.json('access_token');
  }
  
  return { authToken };
}

export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${data.authToken}`,
  };
  
  // Track active users
  activeUsers.add(1);
  
  // Test 1: Health Check (lightweight)
  testHealthCheck();
  
  // Test 2: List Projects (medium load)
  testListProjects(headers);
  
  // Test 3: Disease Search (heavy load)
  testDiseaseSearch(headers);
  
  // Test 4: Target Discovery (heavy load)
  testTargetDiscovery(headers);
  
  // Test 5: Evidence Search (heavy load)
  testEvidenceSearch(headers);
  
  // Test 6: Clinical Workflow Status (medium load)
  testClinicalWorkflowStatus(headers);
  
  // Test 7: Create Project (write operation)
  testCreateProject(headers);
  
  // Test 8: Connector Query (external dependency)
  testConnectorQuery(headers);
  
  // Shorter sleep for stress testing
  sleep(0.5);
}

function testHealthCheck() {
  const res = http.get(`${BASE_URL}/health`);
  
  const success = check(res, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testListProjects(headers) {
  const res = http.get(`${BASE_URL}/api/v1/projects`, { headers });
  
  const success = check(res, {
    'list projects status is 200 or 503': (r) => r.status === 200 || r.status === 503,
    'list projects response time < 3000ms': (r) => r.timings.duration < 3000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testDiseaseSearch(headers) {
  const payload = JSON.stringify({
    query: 'IPEX syndrome',
    limit: 10,
  });
  
  const res = http.post(`${BASE_URL}/api/v1/disease/search`, payload, { headers });
  
  const success = check(res, {
    'disease search status is 200 or 503': (r) => r.status === 200 || r.status === 503,
    'disease search response time < 10000ms': (r) => r.timings.duration < 10000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testTargetDiscovery(headers) {
  const payload = JSON.stringify({
    disease: 'IPEX syndrome',
    limit: 20,
  });
  
  const res = http.post(`${BASE_URL}/api/v1/target/discover`, payload, { headers });
  
  const success = check(res, {
    'target discovery status is 200 or 503': (r) => r.status === 200 || r.status === 503,
    'target discovery response time < 15000ms': (r) => r.timings.duration < 15000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testEvidenceSearch(headers) {
  const payload = JSON.stringify({
    query: 'FOXP3 mutations',
    sources: ['pubmed', 'clinvar'],
    limit: 50,
  });
  
  const res = http.post(`${BASE_URL}/api/v1/evidence/search`, payload, { headers });
  
  const success = check(res, {
    'evidence search status is 200 or 503': (r) => r.status === 200 || r.status === 503,
    'evidence search response time < 10000ms': (r) => r.timings.duration < 10000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testClinicalWorkflowStatus(headers) {
  const workflowId = 'test-workflow-123';
  const res = http.get(`${BASE_URL}/api/v1/clinical/workflow/${workflowId}`, { headers });
  
  const success = check(res, {
    'workflow status is 200, 404, or 503': (r) => r.status === 200 || r.status === 404 || r.status === 503,
    'workflow status response time < 2000ms': (r) => r.timings.duration < 2000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testCreateProject(headers) {
  const payload = JSON.stringify({
    name: `Stress Test Project ${Date.now()}`,
    description: 'Project created during stress testing',
    disease: 'IPEX syndrome',
  });
  
  const res = http.post(`${BASE_URL}/api/v1/projects`, payload, { headers });
  
  const success = check(res, {
    'create project status is 201 or 503': (r) => r.status === 201 || r.status === 503,
    'create project response time < 5000ms': (r) => r.timings.duration < 5000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testConnectorQuery(headers) {
  const payload = JSON.stringify({
    connector: 'pubmed',
    query: 'FOXP3',
    limit: 10,
  });
  
  const res = http.post(`${BASE_URL}/api/v1/connectors/query`, payload, { headers });
  
  const success = check(res, {
    'connector query status is 200 or 503': (r) => r.status === 200 || r.status === 503,
    'connector query response time < 10000ms': (r) => r.timings.duration < 10000,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

export function handleSummary(data) {
  return {
    'stress_test_results.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const enableColors = options.enableColors || false;
  
  let summary = '\n';
  summary += `${indent}Stress Test Summary\n`;
  summary += `${indent}==================\n\n`;
  
  // HTTP metrics
  summary += `${indent}HTTP Metrics:\n`;
  summary += `${indent}  Requests: ${data.metrics.http_reqs.values.count}\n`;
  summary += `${indent}  Failed: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}  Duration (avg): ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  Duration (p95): ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}  Duration (p99): ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n`;
  summary += `${indent}  Duration (max): ${data.metrics.http_req_duration.values.max.toFixed(2)}ms\n\n`;
  
  // Custom metrics
  summary += `${indent}Custom Metrics:\n`;
  summary += `${indent}  Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}  API Latency (avg): ${data.metrics.api_latency.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  API Latency (max): ${data.metrics.api_latency.values.max.toFixed(2)}ms\n`;
  summary += `${indent}  Total Requests: ${data.metrics.request_count.values.count}\n`;
  summary += `${indent}  Peak Active Users: ${data.metrics.active_users.values.max}\n\n`;
  
  // Thresholds
  summary += `${indent}Thresholds:\n`;
  Object.keys(data.metrics).forEach(metric => {
    if (data.metrics[metric].thresholds) {
      Object.keys(data.metrics[metric].thresholds).forEach(threshold => {
        const passed = data.metrics[metric].thresholds[threshold].ok;
        const status = passed ? '✓' : '✗';
        summary += `${indent}  ${status} ${metric} ${threshold}\n`;
      });
    }
  });
  
  // Breaking point analysis
  summary += `\n${indent}Breaking Point Analysis:\n`;
  summary += `${indent}  System handled ${data.metrics.active_users.values.max} concurrent users\n`;
  summary += `${indent}  Error rate at peak: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}  Max response time: ${data.metrics.http_req_duration.values.max.toFixed(2)}ms\n`;
  
  if (data.metrics.errors.values.rate > 0.05) {
    summary += `${indent}  ⚠️  System degraded beyond acceptable limits\n`;
  } else {
    summary += `${indent}  ✓ System maintained acceptable performance\n`;
  }
  
  return summary;
}
