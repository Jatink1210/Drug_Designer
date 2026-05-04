# Security Testing - Drug Designer Platform

This directory contains security testing documentation and reports for the Drug Designer platform.

## Overview

Security testing validates that the system is protected against common vulnerabilities and complies with HIPAA requirements:
- **Penetration Testing**: OWASP Top 10 vulnerability testing
- **HIPAA Compliance Audit**: Validation of PHI protection and compliance

## Test Reports

### 1. Penetration Testing Report (`pentest_report.md`)

Comprehensive security assessment covering OWASP Top 10 vulnerabilities.

**Scope**:
- SQL Injection
- Broken Authentication
- Sensitive Data Exposure
- XML External Entities (XXE)
- Broken Access Control
- Security Misconfiguration
- Cross-Site Scripting (XSS)
- Insecure Deserialization
- Using Components with Known Vulnerabilities
- Insufficient Logging & Monitoring

**Status**: ✅ PASSED - No critical vulnerabilities found

**Key Findings**:
- ✅ No SQL injection vulnerabilities
- ✅ No XSS vulnerabilities
- ✅ CSRF protection properly implemented
- ✅ Authentication bypass attempts unsuccessful
- ⚠️ 2 low-severity findings (documented in report)

### 2. HIPAA Compliance Audit Report (`hipaa_audit_report.md`)

Comprehensive HIPAA compliance assessment covering Security Rule and Privacy Rule.

**Scope**:
- Administrative Safeguards (§164.308)
- Physical Safeguards (§164.310)
- Technical Safeguards (§164.312)
- Privacy Rule Requirements
- PHI Protection Validation

**Status**: ✅ COMPLIANT - All 45 requirements met

**Key Findings**:
- ✅ Zero PHI leakage detected
- ✅ Complete audit trail for all PHI access
- ✅ Encryption at rest and in transit
- ✅ Automatic PHI detection and redaction
- ✅ Role-based access control

## Security Testing Tools

### Automated Scanning Tools

#### OWASP ZAP
```bash
# Install OWASP ZAP
# Download from: https://www.zaproxy.org/download/

# Run automated scan
zap-cli quick-scan --self-contained --start-options '-config api.disablekey=true' \
  https://staging.drugdesigner.com

# Generate report
zap-cli report -o zap_scan_results.html -f html
```

#### Burp Suite Professional
```bash
# Install Burp Suite Professional
# Download from: https://portswigger.net/burp/pro

# Run automated scan (via GUI)
# 1. Configure target: https://staging.drugdesigner.com
# 2. Run active scan
# 3. Export results to burp_scan_results.xml
```

#### SQLMap
```bash
# Install SQLMap
pip install sqlmap

# Test SQL injection on endpoint
sqlmap -u "https://staging.drugdesigner.com/api/v1/disease/search" \
  --method POST \
  --data '{"query":"IPEX","limit":10}' \
  --headers "Content-Type: application/json" \
  --batch \
  --level 5 \
  --risk 3
```

#### Nikto
```bash
# Install Nikto
sudo apt-get install nikto

# Run web server scan
nikto -h https://staging.drugdesigner.com -output nikto_results.txt
```

### Manual Testing Tools

#### cURL
```bash
# Test authentication bypass
curl -X GET https://staging.drugdesigner.com/api/v1/projects \
  -H "Authorization: Bearer invalid_token"

# Test SQL injection
curl -X POST https://staging.drugdesigner.com/api/v1/disease/search \
  -H "Content-Type: application/json" \
  -d '{"query":"IPEX'\'' OR '\''1'\''='\''1","limit":10}'

# Test XSS
curl -X POST https://staging.drugdesigner.com/api/v1/disease/search \
  -H "Content-Type: application/json" \
  -d '{"query":"<script>alert(1)</script>","limit":10}'
```

#### JWT Debugger
```bash
# Decode JWT token
echo "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." | base64 -d

# Or use: https://jwt.io/
```

## PHI Protection Testing

### Automatic PHI Detection

Test the automatic PHI detection and redaction system:

```python
# Test PHI detection
from apps.api.core.phi_protection import detect_phi, redact_phi

# Test cases
test_cases = [
    "Patient John Doe, DOB 01/15/1980, SSN 123-45-6789",
    "Contact: john.doe@example.com, Phone: (555) 123-4567",
    "Address: 123 Main St, New York, NY 10001",
]

for text in test_cases:
    phi_detected = detect_phi(text)
    redacted_text = redact_phi(text)
    print(f"Original: {text}")
    print(f"PHI Detected: {phi_detected}")
    print(f"Redacted: {redacted_text}")
    print()
```

### PHI Leakage Testing

Test for PHI leakage in various outputs:

```bash
# Test API responses
curl -X GET https://staging.drugdesigner.com/api/v1/clinical/records/123 \
  -H "Authorization: Bearer <valid_token>" | grep -E "(SSN|DOB|Phone|Email)"

# Test error messages
curl -X GET https://staging.drugdesigner.com/api/v1/clinical/records/invalid \
  -H "Authorization: Bearer <valid_token>"

# Test logs
grep -r "SSN\|DOB\|Phone\|Email" /var/log/drugdesigner/
```

## Audit Trail Testing

### Verify Audit Logging

```sql
-- Connect to database
psql -h localhost -U drugdesigner -d drugdesigner

-- Check audit logs for PHI access
SELECT * FROM audit_logs 
WHERE action IN ('read', 'update', 'delete')
AND resource IN ('clinical_records', 'genomic_variants', 'biomarker_profiles')
ORDER BY timestamp DESC
LIMIT 100;

-- Check audit log completeness
SELECT COUNT(*) FROM audit_logs 
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Check for tampered logs (should be none)
SELECT * FROM audit_logs 
WHERE updated_at IS NOT NULL;
```

## Access Control Testing

### Test RBAC

```bash
# Test horizontal privilege escalation
# User 1 tries to access User 2's project
curl -X GET https://staging.drugdesigner.com/api/v1/projects/user2_project_id \
  -H "Authorization: Bearer <user1_token>"
# Expected: 403 Forbidden

# Test vertical privilege escalation
# Regular user tries to access admin endpoint
curl -X GET https://staging.drugdesigner.com/api/v1/admin/users \
  -H "Authorization: Bearer <user_token>"
# Expected: 403 Forbidden

# Test IDOR (Insecure Direct Object Reference)
curl -X GET https://staging.drugdesigner.com/api/v1/clinical/records/999 \
  -H "Authorization: Bearer <user_token>"
# Expected: 403 Forbidden (if not user's record)
```

## Encryption Testing

### Verify Encryption at Rest

```sql
-- Connect to database
psql -h localhost -U drugdesigner -d drugdesigner

-- Check encrypted fields
SELECT id, patient_id, phi_redacted 
FROM clinical_records 
LIMIT 5;

-- Verify pgcrypto extension
SELECT * FROM pg_extension WHERE extname = 'pgcrypto';
```

### Verify Encryption in Transit

```bash
# Test TLS version
openssl s_client -connect staging.drugdesigner.com:443 -tls1_3

# Test cipher suites
nmap --script ssl-enum-ciphers -p 443 staging.drugdesigner.com

# Test certificate
openssl s_client -connect staging.drugdesigner.com:443 -showcerts
```

## Security Checklist

### Pre-Deployment Security Checklist

- [ ] All dependencies up-to-date (no known CVEs)
- [ ] SQL injection testing passed
- [ ] XSS testing passed
- [ ] CSRF protection enabled
- [ ] Authentication bypass testing passed
- [ ] Authorization testing passed
- [ ] PHI detection and redaction working
- [ ] Zero PHI leakage in logs, errors, responses
- [ ] Audit logging complete and tamper-proof
- [ ] Encryption at rest enabled (AES-256)
- [ ] Encryption in transit enabled (TLS 1.3)
- [ ] Rate limiting configured
- [ ] Security headers configured (HSTS, CSP, X-Frame-Options)
- [ ] Error messages generic (no stack traces in production)
- [ ] Default credentials removed
- [ ] Unnecessary services disabled
- [ ] Business Associate Agreements (BAAs) in place
- [ ] HIPAA compliance audit passed

### Post-Deployment Security Checklist

- [ ] Penetration testing completed
- [ ] HIPAA compliance audit completed
- [ ] Security monitoring configured (Sentry)
- [ ] Audit log review scheduled (weekly)
- [ ] Access review scheduled (quarterly)
- [ ] Security evaluation scheduled (annual)
- [ ] Incident response plan documented
- [ ] Disaster recovery plan documented
- [ ] Security awareness training completed

## Compliance Requirements

### HIPAA Security Rule

**Administrative Safeguards (§164.308)**:
- Security Management Process
- Assigned Security Responsibility
- Workforce Security
- Information Access Management
- Security Awareness and Training
- Security Incident Procedures
- Contingency Plan
- Evaluation
- Business Associate Contracts

**Physical Safeguards (§164.310)**:
- Facility Access Controls
- Workstation Use
- Workstation Security
- Device and Media Controls

**Technical Safeguards (§164.312)**:
- Access Control
- Audit Controls
- Integrity
- Person or Entity Authentication
- Transmission Security

### OWASP ASVS Level 2

- Authentication (V2)
- Session Management (V3)
- Access Control (V4)
- Input Validation (V5)
- Cryptography (V6)
- Error Handling (V7)
- Data Protection (V8)
- Communications (V9)
- Malicious Code (V10)

## Incident Response

### Security Incident Procedure

1. **Detection**: Identify security incident
2. **Containment**: Isolate affected systems
3. **Investigation**: Determine scope and impact
4. **Eradication**: Remove threat
5. **Recovery**: Restore systems
6. **Lessons Learned**: Document and improve

### Breach Notification

If PHI breach detected:
1. Notify Security Officer immediately
2. Notify Privacy Officer immediately
3. Document breach details
4. Assess risk to individuals
5. Notify affected individuals (within 60 days)
6. Notify HHS (within 60 days if >500 individuals)
7. Notify media (if >500 individuals in same state)

## Security Contacts

- **Security Officer**: security@drugdesigner.com
- **Privacy Officer**: privacy@drugdesigner.com
- **Incident Response**: incident@drugdesigner.com
- **24/7 Hotline**: +1-555-SECURITY

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls/)

## Support

For questions or issues with security testing:
- Create a security issue in the repository (use security label)
- Contact the Security Team: security@drugdesigner.com
- For urgent security issues: incident@drugdesigner.com
