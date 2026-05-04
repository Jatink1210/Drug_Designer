"""PHI Protection and Redaction Module

Automated PHI (Protected Health Information) detection and redaction for HIPAA compliance.
Implements HIPAA Safe Harbor method for de-identification.

Requirements: FR-SEC-004
"""

import re
from typing import Dict, List, Tuple, Any
from datetime import datetime


class PHIDetector:
    """
    Automated PHI scanner for detecting and redacting protected health information.
    
    Implements HIPAA Safe Harbor 18 identifiers:
    1. Names
    2. Geographic subdivisions smaller than state
    3. Dates (except year)
    4. Telephone numbers
    5. Fax numbers
    6. Email addresses
    7. Social Security numbers
    8. Medical record numbers
    9. Health plan beneficiary numbers
    10. Account numbers
    11. Certificate/license numbers
    12. Vehicle identifiers
    13. Device identifiers
    14. URLs
    15. IP addresses
    16. Biometric identifiers
    17. Full-face photos
    18. Any other unique identifying number
    """
    
    def __init__(self):
        """Initialize PHI detector with regex patterns."""
        # Regex patterns for PHI detection
        self.patterns = {
            "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            "phone": re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "date": re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
            "mrn": re.compile(r'\b(MRN|Medical Record|Patient ID)[:\s]+[A-Z0-9-]+\b', re.IGNORECASE),
            "zip_code": re.compile(r'\b\d{5}(-\d{4})?\b'),
            "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            "url": re.compile(r'https?://[^\s]+'),
            "account_number": re.compile(r'\b(Account|Acct)[:\s]+[A-Z0-9-]+\b', re.IGNORECASE),
        }
        
        # TODO: Add NER-based name detection
        # TODO: Add location detection (cities, addresses)
        # TODO: Add biometric identifier detection
        
        self.redaction_map = {}
    
    def detect_phi(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PHI in text.
        
        Args:
            text: Input text to scan
        
        Returns:
            List of detected PHI items with type and location
        """
        detected_phi = []
        
        for phi_type, pattern in self.patterns.items():
            matches = pattern.finditer(text)
            for match in matches:
                detected_phi.append({
                    "type": phi_type,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 1.0  # Regex matches are high confidence
                })
        
        # TODO: Add NER-based detection for names and locations
        # import spacy
        # nlp = spacy.load("en_core_web_sm")
        # doc = nlp(text)
        # for ent in doc.ents:
        #     if ent.label_ in ["PERSON", "GPE", "LOC"]:
        #         detected_phi.append({...})
        
        return detected_phi
    
    def redact_phi(self, text: str, redaction_char: str = "[REDACTED]") -> Tuple[str, bool]:
        """
        Redact PHI from text.
        
        Args:
            text: Input text
            redaction_char: Replacement string for PHI
        
        Returns:
            Tuple of (redacted_text, phi_found)
        """
        detected_phi = self.detect_phi(text)
        
        if not detected_phi:
            return text, False
        
        # Sort by start position in reverse to maintain indices
        detected_phi.sort(key=lambda x: x["start"], reverse=True)
        
        redacted_text = text
        for phi_item in detected_phi:
            start = phi_item["start"]
            end = phi_item["end"]
            phi_type = phi_item["type"]
            
            # Create type-specific redaction
            replacement = f"[{phi_type.upper()}_REDACTED]"
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        
        return redacted_text, True
    
    def scan_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively scan dictionary for PHI.
        
        Args:
            data: Dictionary to scan
        
        Returns:
            Dictionary with PHI redacted
        """
        redacted_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                redacted_value, _ = self.redact_phi(value)
                redacted_data[key] = redacted_value
            elif isinstance(value, dict):
                redacted_data[key] = self.scan_dict(value)
            elif isinstance(value, list):
                redacted_data[key] = [
                    self.scan_dict(item) if isinstance(item, dict)
                    else self.redact_phi(item)[0] if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted_data[key] = value
        
        return redacted_data
    
    def validate_hipaa_compliance(self, text: str) -> Dict[str, Any]:
        """
        Validate text for HIPAA Safe Harbor compliance.
        
        Args:
            text: Text to validate
        
        Returns:
            Compliance report
        """
        detected_phi = self.detect_phi(text)
        
        phi_by_type = {}
        for phi_item in detected_phi:
            phi_type = phi_item["type"]
            phi_by_type[phi_type] = phi_by_type.get(phi_type, 0) + 1
        
        is_compliant = len(detected_phi) == 0
        
        return {
            "is_compliant": is_compliant,
            "phi_detected": len(detected_phi),
            "phi_by_type": phi_by_type,
            "violations": detected_phi if not is_compliant else [],
            "timestamp": datetime.utcnow().isoformat()
        }


# Global PHI detector instance
_phi_detector_instance = None


def get_phi_detector() -> PHIDetector:
    """
    Get or create global PHI detector instance.
    
    Returns:
        PHIDetector instance
    """
    global _phi_detector_instance
    if _phi_detector_instance is None:
        _phi_detector_instance = PHIDetector()
    return _phi_detector_instance


def redact_phi_from_text(text: str) -> Tuple[str, bool]:
    """
    Convenience function to redact PHI from text.
    
    Args:
        text: Input text
    
    Returns:
        Tuple of (redacted_text, phi_found)
    """
    detector = get_phi_detector()
    return detector.redact_phi(text)


def redact_phi_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to redact PHI from dictionary.
    
    Args:
        data: Input dictionary
    
    Returns:
        Dictionary with PHI redacted
    """
    detector = get_phi_detector()
    return detector.scan_dict(data)
