/**
 * k6 Load Testing Script for Drug Designer API
 * 
 * Tests system performance under normal load (50 concurrent users)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const requestCount = new Counter('request_count');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },  // Ramp up to 10 users
    { duration: '5m', target: 50 },  // Ramp up to 50 users
    { duration: '10m', target: 50 }, // Stay at 50 users
    { duration: '2m', target: 0 },   // Ramp down to 0 users
  ],
  thresholds: {
    'http_req_duration': ['p(95)<5000'], // 95% of requests should be below 5s
    'http_req_failed': ['rate<0.01'],    // Error rate should be below 1%
    'errors': ['rate<0.01'],             // Custom error rate below 1%
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
  
  // Test 1: Health Check
  testHealthCheck();
  
  // Test 2: List Projects
  testListProjects(headers);
  
  // Test 3: Disease Search
  testDiseaseSearch(headers);
  
  // Test 4: Target Discovery
  testTargetDiscovery(headers);
  
  // Test 5: Evidence Search
  testEvidenceSearch(headers);
  
  // Test 6: Clinical Workflow Status
  testClinicalWorkflowStatus(headers);
  
  // Sleep between iterations
  sleep(1);
}

function testHealthCheck() {
  const res = http.get(`${BASE_URL}/health`);
  
  const success = check(res, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testListProjects(headers) {
  const res = http.get(`${BASE_URL}/api/v1/projects`, { headers });
  
  const success = check(res, {
    'list projects status is 200': (r) => r.status === 200,
    'list projects response time < 1000ms': (r) => r.timings.duration < 1000,
    'list projects returns array': (r) => Array.isArray(r.json()),
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
    'disease search status is 200': (r) => r.status === 200,
    'disease search response time < 3000ms': (r) => r.timings.duration < 3000,
    'disease search returns results': (r) => r.json('results') !== undefined,
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
    'target discovery status is 200': (r) => r.status === 200,
    'target discovery response time < 5000ms': (r) => r.timings.duration < 5000,
    'target discovery returns targets': (r) => r.json('targets') !== undefined,
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
    'evidence search status is 200': (r) => r.status === 200,
    'evidence search response time < 3000ms': (r) => r.timings.duration < 3000,
    'evidence search returns results': (r) => r.json('results') !== undefined,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

function testClinicalWorkflowStatus(headers) {
  const workflowId = 'test-workflow-123';
  const res = http.get(`${BASE_URL}/api/v1/clinical/workflow/${workflowId}`, { headers });
  
  const success = check(res, {
    'workflow status is 200 or 404': (r) => r.status === 200 || r.status === 404,
    'workflow status response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
  apiLatency.add(res.timings.duration);
  requestCount.add(1);
}

export function handleSummary(data) {
  return {
    'load_test_results.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options) {
  const indent = options.indent || '';
  const enableColors = options.enableColors || false;
  
  let summary = '\n';
  summary += `${indent}Load Test Summary\n`;
  summary += `${indent}================\n\n`;
  
  // HTTP metrics
  summary += `${indent}HTTP Metrics:\n`;
  summary += `${indent}  Requests: ${data.metrics.http_reqs.values.count}\n`;
  summary += `${indent}  Failed: ${data.metrics.http_req_failed.values.rate * 100}%\n`;
  summary += `${indent}  Duration (avg): ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  Duration (p95): ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  summary += `${indent}  Duration (p99): ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n\n`;
  
  // Custom metrics
  summary += `${indent}Custom Metrics:\n`;
  summary += `${indent}  Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%\n`;
  summary += `${indent}  API Latency (avg): ${data.metrics.api_latency.values.avg.toFixed(2)}ms\n`;
  summary += `${indent}  Total Requests: ${data.metrics.request_count.values.count}\n\n`;
  
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
  
  return summary;
}
