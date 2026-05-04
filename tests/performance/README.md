# Performance Testing - Drug Designer Platform

This directory contains performance testing scripts for the Drug Designer platform using k6.

## Overview

Performance testing validates that the system meets SLA targets under various load conditions:
- **Load Testing**: Normal operating conditions (50 concurrent users)
- **Stress Testing**: System limits and failure modes (200 concurrent users)

## Prerequisites

### Install k6

**macOS**:
```bash
brew install k6
```

**Windows**:
```bash
choco install k6
```

**Linux**:
```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

**Docker**:
```bash
docker pull grafana/k6
```

## Test Scripts

### 1. Load Testing (`load_tests.js`)

Tests system performance under normal load conditions.

**Configuration**:
- Ramp up: 2 minutes to 10 users, 5 minutes to 50 users
- Steady state: 10 minutes at 50 users
- Ramp down: 2 minutes to 0 users
- Total duration: 19 minutes

**Thresholds**:
- 95% of requests < 5 seconds
- Error rate < 1%

**Run**:
```bash
# Local environment
k6 run load_tests.js

# Custom environment
BASE_URL=https://staging.drugdesigner.com k6 run load_tests.js

# With Docker
docker run --rm -i grafana/k6 run - <load_tests.js
```

### 2. Stress Testing (`stress_tests.js`)

Tests system limits and failure modes under extreme load.

**Configuration**:
- Ramp up: 2 min to 50, 3 min to 100, 3 min to 150, 5 min to 200 users
- Steady state: 5 minutes at 200 users
- Ramp down: 3 minutes to 100, 2 minutes to 0 users
- Total duration: 23 minutes

**Thresholds**:
- 95% of requests < 10 seconds (relaxed for stress)
- Error rate < 5% (relaxed for stress)

**Run**:
```bash
# Local environment
k6 run stress_tests.js

# Custom environment
BASE_URL=https://staging.drugdesigner.com k6 run stress_tests.js

# With Docker
docker run --rm -i grafana/k6 run - <stress_tests.js
```

## Test Scenarios

Both test scripts cover the following scenarios:

1. **Health Check** - Lightweight endpoint validation
2. **List Projects** - Medium load database query
3. **Disease Search** - Heavy load with external connectors
4. **Target Discovery** - Heavy load with ML models
5. **Evidence Search** - Heavy load with multiple connectors
6. **Clinical Workflow Status** - Medium load status check
7. **Create Project** - Write operation (stress test only)
8. **Connector Query** - External dependency test (stress test only)

## Metrics

### Standard k6 Metrics
- `http_reqs` - Total HTTP requests
- `http_req_duration` - Request duration (avg, p95, p99, max)
- `http_req_failed` - Failed request rate
- `http_req_waiting` - Time waiting for response
- `http_req_connecting` - Connection time
- `http_req_tls_handshaking` - TLS handshake time

### Custom Metrics
- `errors` - Custom error rate
- `api_latency` - API response latency trend
- `request_count` - Total request counter
- `active_users` - Active user gauge (stress test only)

## Results

Test results are saved to:
- `load_test_results.json` - Load test results
- `stress_test_results.json` - Stress test results

### Interpreting Results

**Load Test Success Criteria**:
- ✅ p95 latency < 5 seconds
- ✅ Error rate < 1%
- ✅ All thresholds passed

**Stress Test Success Criteria**:
- ✅ p95 latency < 10 seconds
- ✅ Error rate < 5%
- ✅ System maintains acceptable performance at 200 users
- ✅ Graceful degradation (no crashes)

### Sample Output

```
Load Test Summary
================

HTTP Metrics:
  Requests: 15234
  Failed: 0.45%
  Duration (avg): 1234.56ms
  Duration (p95): 3456.78ms
  Duration (p99): 4567.89ms

Custom Metrics:
  Error Rate: 0.45%
  API Latency (avg): 1234.56ms
  Total Requests: 15234

Thresholds:
  ✓ http_req_duration p(95)<5000
  ✓ http_req_failed rate<0.01
  ✓ errors rate<0.01
```

## Performance SLA Targets

| Endpoint | p95 Latency | p99 Latency | Error Rate |
|----------|-------------|-------------|------------|
| Health Check | < 200ms | < 500ms | < 0.1% |
| List Projects | < 1s | < 2s | < 1% |
| Disease Search | < 3s | < 5s | < 1% |
| Target Discovery | < 5s | < 10s | < 1% |
| Evidence Search | < 3s | < 5s | < 1% |
| Clinical Workflow | < 500ms | < 1s | < 1% |

## Troubleshooting

### High Error Rates
- Check API server logs for errors
- Verify database connection pool size
- Check external connector availability
- Review rate limiting configuration

### High Latency
- Check database query performance
- Review slow query logs
- Check external connector response times
- Verify caching is working

### Connection Errors
- Verify BASE_URL is correct
- Check network connectivity
- Verify SSL certificates
- Check firewall rules

## CI/CD Integration

### GitHub Actions

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6
      
      - name: Run Load Tests
        run: |
          BASE_URL=${{ secrets.STAGING_URL }} k6 run tests/performance/load_tests.js
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: load_test_results.json
```

## Best Practices

1. **Run tests in staging environment** - Never run performance tests in production
2. **Warm up the system** - Run a small load test before the main test
3. **Monitor system resources** - Watch CPU, memory, disk I/O during tests
4. **Test incrementally** - Start with small loads and increase gradually
5. **Analyze results** - Review metrics and identify bottlenecks
6. **Iterate** - Fix issues and re-test

## Additional Resources

- [k6 Documentation](https://k6.io/docs/)
- [k6 Examples](https://k6.io/docs/examples/)
- [Performance Testing Best Practices](https://k6.io/docs/testing-guides/test-types/)
- [k6 Cloud](https://k6.io/cloud/) - Cloud-based load testing

## Support

For questions or issues with performance testing:
- Create an issue in the repository
- Contact the DevOps team
- Review the k6 documentation
