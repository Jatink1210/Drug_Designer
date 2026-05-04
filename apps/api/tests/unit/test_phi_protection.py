"""Unit tests for PHI Protection module.

Tests PHI detection, redaction, and HIPAA compliance validation.
"""

import pytest
from core.phi_protection import (
    PHIDetector,
    get_phi_detector,
    redact_phi_from_text,
    redact_phi_from_dict
)


class TestPHIDetector:
    """Test PHI detector functionality."""
    
    def test_detector_initialization(self):
        """Test PHI detector can be initialized."""
        detector = PHIDetector()
        assert detector is not None
        assert len(detector.patterns) > 0
    
    def test_detect_ssn(self):
        """Test SSN detection."""
        detector = PHIDetector()
        text = "Patient SSN is 123-45-6789"
        phi_items = detector.detect_phi(text)
        
        assert len(phi_items) > 0
        ssn_items = [item for item in phi_items if item["type"] == "ssn"]
        assert len(ssn_items) == 1
        assert ssn_items[0]["value"] == "123-45-6789"
    
    def test_detect_phone(self):
        """Test phone number detection."""
        detector = PHIDetector()
        text = "Contact: 555-123-4567"
        phi_items = detector.detect_phi(text)
        
        phone_items = [item for item in phi_items if item["type"] == "phone"]
        assert len(phone_items) == 1
        assert "555-123-4567" in phone_items[0]["value"]
    
    def test_detect_email(self):
        """Test email detection."""
        detector = PHIDetector()
        text = "Email: patient@example.com"
        phi_items = detector.detect_phi(text)
        
        email_items = [item for item in phi_items if item["type"] == "email"]
        assert len(email_items) == 1
        assert email_items[0]["value"] == "patient@example.com"
    
    def test_detect_date(self):
        """Test date detection."""
        detector = PHIDetector()
        text = "DOB: 01/15/1980"
        phi_items = detector.detect_phi(text)
        
        date_items = [item for item in phi_items if item["type"] == "date"]
        assert len(date_items) == 1
    
    def test_detect_mrn(self):
        """Test medical record number detection."""
        detector = PHIDetector()
        text = "MRN: ABC-12345"
        phi_items = detector.detect_phi(text)
        
        mrn_items = [item for item in phi_items if item["type"] == "mrn"]
        assert len(mrn_items) == 1
    
    def test_detect_ip_address(self):
        """Test IP address detection."""
        detector = PHIDetector()
        text = "IP: 192.168.1.1"
        phi_items = detector.detect_phi(text)
        
        ip_items = [item for item in phi_items if item["type"] == "ip_address"]
        assert len(ip_items) == 1
        assert ip_items[0]["value"] == "192.168.1.1"
    
    def test_detect_multiple_phi(self):
        """Test detection of multiple PHI types."""
        detector = PHIDetector()
        text = "Patient John Doe, SSN 123-45-6789, phone 555-123-4567, email john@example.com"
        phi_items = detector.detect_phi(text)
        
        assert len(phi_items) >= 3  # SSN, phone, email
    
    def test_redact_phi_basic(self):
        """Test basic PHI redaction."""
        detector = PHIDetector()
        text = "SSN: 123-45-6789"
        redacted, phi_found = detector.redact_phi(text)
        
        assert phi_found is True
        assert "123-45-6789" not in redacted
        assert "[SSN_REDACTED]" in redacted
    
    def test_redact_phi_no_phi(self):
        """Test redaction when no PHI present."""
        detector = PHIDetector()
        text = "This is a normal sentence with no PHI."
        redacted, phi_found = detector.redact_phi(text)
        
        assert phi_found is False
        assert redacted == text
    
    def test_redact_phi_multiple(self):
        """Test redaction of multiple PHI items."""
        detector = PHIDetector()
        text = "SSN: 123-45-6789, Phone: 555-123-4567"
        redacted, phi_found = detector.redact_phi(text)
        
        assert phi_found is True
        assert "123-45-6789" not in redacted
        assert "555-123-4567" not in redacted
        assert "[SSN_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted
    
    def test_scan_dict_simple(self):
        """Test scanning dictionary for PHI."""
        detector = PHIDetector()
        data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "notes": "Patient contacted at 555-123-4567"
        }
        redacted = detector.scan_dict(data)
        
        assert "123-45-6789" not in redacted["ssn"]
        assert "555-123-4567" not in redacted["notes"]
    
    def test_scan_dict_nested(self):
        """Test scanning nested dictionary."""
        detector = PHIDetector()
        data = {
            "patient": {
                "contact": {
                    "email": "patient@example.com",
                    "phone": "555-123-4567"
                }
            }
        }
        redacted = detector.scan_dict(data)
        
        assert "patient@example.com" not in str(redacted)
        assert "555-123-4567" not in str(redacted)
    
    def test_scan_dict_with_list(self):
        """Test scanning dictionary with list values."""
        detector = PHIDetector()
        data = {
            "contacts": [
                "555-123-4567",
                "patient@example.com"
            ]
        }
        redacted = detector.scan_dict(data)
        
        assert "555-123-4567" not in str(redacted["contacts"])
        assert "patient@example.com" not in str(redacted["contacts"])
    
    def test_validate_hipaa_compliance_clean(self):
        """Test HIPAA compliance validation for clean text."""
        detector = PHIDetector()
        text = "This text contains no PHI."
        report = detector.validate_hipaa_compliance(text)
        
        assert report["is_compliant"] is True
        assert report["phi_detected"] == 0
        assert len(report["violations"]) == 0
    
    def test_validate_hipaa_compliance_violations(self):
        """Test HIPAA compliance validation with violations."""
        detector = PHIDetector()
        text = "SSN: 123-45-6789, Email: patient@example.com"
        report = detector.validate_hipaa_compliance(text)
        
        assert report["is_compliant"] is False
        assert report["phi_detected"] > 0
        assert len(report["violations"]) > 0
        assert "phi_by_type" in report


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_phi_detector_singleton(self):
        """Test global PHI detector is singleton."""
        detector1 = get_phi_detector()
        detector2 = get_phi_detector()
        assert detector1 is detector2
    
    def test_redact_phi_from_text_convenience(self):
        """Test convenience function for text redaction."""
        text = "SSN: 123-45-6789"
        redacted, phi_found = redact_phi_from_text(text)
        
        assert phi_found is True
        assert "123-45-6789" not in redacted
    
    def test_redact_phi_from_dict_convenience(self):
        """Test convenience function for dict redaction."""
        data = {"ssn": "123-45-6789"}
        redacted = redact_phi_from_dict(data)
        
        assert "123-45-6789" not in redacted["ssn"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_text(self):
        """Test with empty text."""
        detector = PHIDetector()
        phi_items = detector.detect_phi("")
        assert len(phi_items) == 0
    
    def test_empty_dict(self):
        """Test with empty dictionary."""
        detector = PHIDetector()
        redacted = detector.scan_dict({})
        assert redacted == {}
    
    def test_none_values_in_dict(self):
        """Test dictionary with None values."""
        detector = PHIDetector()
        data = {"field1": None, "field2": "value"}
        redacted = detector.scan_dict(data)
        assert redacted["field1"] is None
    
    def test_numeric_values_in_dict(self):
        """Test dictionary with numeric values."""
        detector = PHIDetector()
        data = {"age": 45, "count": 100}
        redacted = detector.scan_dict(data)
        assert redacted["age"] == 45
        assert redacted["count"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
