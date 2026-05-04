#!/usr/bin/env python3
"""
Environment Variable Validation Script

Validates that all required environment variables are set and properly formatted.
Part of Task 23.2: Configure environment variables

Usage:
    python scripts/validate_env.py
    
Exit codes:
    0: All validations passed
    1: One or more validations failed
"""

import os
import sys
import re
from typing import List, Tuple, Dict
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Required variables (MUST be set)
REQUIRED_VARS = [
    'JWT_SECRET',
    'ENCRYPTION_KEY',
    'PG_ENCRYPT_KEY',
    'POSTGRES_PASSWORD',
    'NEO4J_PASSWORD',
    'MINIO_ROOT_PASSWORD',
]

# High priority variables (SHOULD be set)
HIGH_PRIORITY_VARS = [
    'GRAFANA_ADMIN_PASSWORD',
    'GRAFANA_SECRET_KEY',
]

# Variables that should not contain CHANGE_ME
NO_CHANGE_ME_VARS = REQUIRED_VARS + HIGH_PRIORITY_VARS

# Optional but recommended variables
RECOMMENDED_VARS = [
    'SENTRY_DSN',
    'OPENAI_API_KEY',
    'NCBI_API_KEY',
]


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✅ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}❌ {text}{RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ️  {text}{RESET}")


def load_env_file(env_file: str = '.env') -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    env_path = Path(env_file)
    
    if not env_path.exists():
        print_warning(f"Environment file {env_file} not found")
        return env_vars
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_vars[key] = value
    
    return env_vars


def check_required_variables(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Check that all required variables are set."""
    errors = []
    
    for var in REQUIRED_VARS:
        value = env_vars.get(var) or os.getenv(var)
        if not value:
            errors.append(f"Missing required variable: {var}")
    
    return len(errors) == 0, errors


def check_change_me_placeholders(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Check for CHANGE_ME placeholders."""
    errors = []
    
    for var in NO_CHANGE_ME_VARS:
        value = env_vars.get(var) or os.getenv(var, '')
        if 'CHANGE_ME' in value:
            errors.append(f"Variable {var} contains CHANGE_ME placeholder")
    
    return len(errors) == 0, errors


def validate_jwt_secret(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate JWT_SECRET format and length."""
    errors = []
    
    jwt_secret = env_vars.get('JWT_SECRET') or os.getenv('JWT_SECRET', '')
    
    if jwt_secret:
        if len(jwt_secret) < 32:
            errors.append("JWT_SECRET should be at least 32 characters (256 bits)")
        
        # Check if it looks like a secure random string
        if jwt_secret.lower() in ['secret', 'password', 'changeme']:
            errors.append("JWT_SECRET appears to be a weak/default value")
    
    return len(errors) == 0, errors


def validate_encryption_key(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate ENCRYPTION_KEY format (Fernet key)."""
    errors = []
    
    encryption_key = env_vars.get('ENCRYPTION_KEY') or os.getenv('ENCRYPTION_KEY', '')
    
    if encryption_key:
        try:
            from cryptography.fernet import Fernet
            Fernet(encryption_key.encode())
        except Exception as e:
            errors.append(f"ENCRYPTION_KEY is not a valid Fernet key: {str(e)}")
    
    return len(errors) == 0, errors


def validate_pg_encrypt_key(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate PG_ENCRYPT_KEY format (64 hex characters)."""
    errors = []
    
    pg_key = env_vars.get('PG_ENCRYPT_KEY') or os.getenv('PG_ENCRYPT_KEY', '')
    
    if pg_key:
        if not re.match(r'^[0-9a-fA-F]{64}$', pg_key):
            errors.append("PG_ENCRYPT_KEY should be 64 hexadecimal characters (256 bits)")
    
    return len(errors) == 0, errors


def validate_password_strength(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate password strength for database and service passwords."""
    errors = []
    warnings = []
    
    password_vars = [
        'POSTGRES_PASSWORD',
        'NEO4J_PASSWORD',
        'MINIO_ROOT_PASSWORD',
        'GRAFANA_ADMIN_PASSWORD',
    ]
    
    for var in password_vars:
        password = env_vars.get(var) or os.getenv(var, '')
        
        if password:
            # Check minimum length
            if len(password) < 16:
                errors.append(f"{var} should be at least 16 characters")
            
            # Check for weak passwords
            weak_passwords = ['password', 'admin', 'changeme', '12345678']
            if password.lower() in weak_passwords:
                errors.append(f"{var} is a weak/common password")
            
            # Check complexity (optional warning)
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
            
            if not (has_upper and has_lower and has_digit and has_special):
                warnings.append(
                    f"{var} should contain uppercase, lowercase, digits, and special characters"
                )
    
    return len(errors) == 0, errors + warnings


def validate_environment_setting(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate ENVIRONMENT setting."""
    warnings = []
    
    environment = env_vars.get('ENVIRONMENT') or os.getenv('ENVIRONMENT', 'development')
    
    valid_environments = ['development', 'staging', 'production']
    if environment not in valid_environments:
        warnings.append(
            f"ENVIRONMENT should be one of: {', '.join(valid_environments)} (got: {environment})"
        )
    
    # Warn if DEBUG is enabled in production
    debug = env_vars.get('DEBUG') or os.getenv('DEBUG', 'false')
    if environment == 'production' and debug.lower() == 'true':
        warnings.append("DEBUG is enabled in production environment (security risk)")
    
    return True, warnings


def check_recommended_variables(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Check recommended but optional variables."""
    warnings = []
    
    for var in RECOMMENDED_VARS:
        value = env_vars.get(var) or os.getenv(var)
        if not value:
            warnings.append(f"Recommended variable not set: {var}")
    
    return True, warnings


def validate_database_urls(env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate database connection URLs."""
    errors = []
    
    # Check PostgreSQL URL format if provided
    postgres_url = env_vars.get('POSTGRES_URL') or os.getenv('POSTGRES_URL', '')
    if postgres_url:
        if not postgres_url.startswith('postgresql'):
            errors.append("POSTGRES_URL should start with 'postgresql://' or 'postgresql+asyncpg://'")
    
    # Check Neo4j URI format
    neo4j_uri = env_vars.get('NEO4J_URI') or os.getenv('NEO4J_URI', '')
    if neo4j_uri:
        if not neo4j_uri.startswith('bolt://') and not neo4j_uri.startswith('neo4j://'):
            errors.append("NEO4J_URI should start with 'bolt://' or 'neo4j://'")
    
    # Check Redis URL format
    redis_url = env_vars.get('REDIS_URL') or os.getenv('REDIS_URL', '')
    if redis_url:
        if not redis_url.startswith('redis://'):
            errors.append("REDIS_URL should start with 'redis://'")
    
    return len(errors) == 0, errors


def generate_secrets_help():
    """Print help for generating secrets."""
    print_header("Secret Generation Commands")
    
    print("Generate required secrets using these commands:\n")
    
    print(f"{BLUE}JWT_SECRET (256-bit):{RESET}")
    print('  python -c "import secrets; print(secrets.token_urlsafe(32))"')
    print()
    
    print(f"{BLUE}ENCRYPTION_KEY (Fernet):{RESET}")
    print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    print()
    
    print(f"{BLUE}PG_ENCRYPT_KEY (256-bit hex):{RESET}")
    print('  openssl rand -hex 32')
    print()
    
    print(f"{BLUE}GRAFANA_SECRET_KEY:{RESET}")
    print('  python -c "import secrets; print(secrets.token_urlsafe(32))"')
    print()
    
    print(f"{BLUE}Strong Password (16+ chars):{RESET}")
    print('  python -c "import secrets; import string; chars = string.ascii_letters + string.digits + string.punctuation; print(\'\'.join(secrets.choice(chars) for _ in range(24)))"')
    print()


def main():
    """Main validation function."""
    print_header("Drug Designer Environment Validation")
    
    # Load .env file
    print_info("Loading environment variables from .env file...")
    env_vars = load_env_file('.env')
    
    if env_vars:
        print_success(f"Loaded {len(env_vars)} variables from .env file")
    else:
        print_warning("No .env file found, checking system environment variables only")
    
    # Run all validations
    all_passed = True
    all_errors = []
    all_warnings = []
    
    # 1. Check required variables
    print_header("Checking Required Variables")
    passed, errors = check_required_variables(env_vars)
    if passed:
        print_success(f"All {len(REQUIRED_VARS)} required variables are set")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 2. Check for CHANGE_ME placeholders
    print_header("Checking for Placeholder Values")
    passed, errors = check_change_me_placeholders(env_vars)
    if passed:
        print_success("No CHANGE_ME placeholders found")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 3. Validate JWT secret
    print_header("Validating JWT Secret")
    passed, errors = validate_jwt_secret(env_vars)
    if passed:
        print_success("JWT_SECRET is valid")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 4. Validate encryption key
    print_header("Validating Encryption Key")
    passed, errors = validate_encryption_key(env_vars)
    if passed:
        print_success("ENCRYPTION_KEY is valid")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 5. Validate PostgreSQL encryption key
    print_header("Validating PostgreSQL Encryption Key")
    passed, errors = validate_pg_encrypt_key(env_vars)
    if passed:
        print_success("PG_ENCRYPT_KEY is valid")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 6. Validate password strength
    print_header("Validating Password Strength")
    passed, messages = validate_password_strength(env_vars)
    if passed:
        print_success("All passwords meet minimum requirements")
    else:
        all_passed = False
        for msg in messages:
            if "should contain" in msg:
                all_warnings.append(msg)
                print_warning(msg)
            else:
                all_errors.append(msg)
                print_error(msg)
    
    # 7. Validate environment setting
    print_header("Validating Environment Settings")
    passed, warnings = validate_environment_setting(env_vars)
    if warnings:
        all_warnings.extend(warnings)
        for warning in warnings:
            print_warning(warning)
    else:
        print_success("Environment settings are valid")
    
    # 8. Validate database URLs
    print_header("Validating Database URLs")
    passed, errors = validate_database_urls(env_vars)
    if passed:
        print_success("Database URLs are valid")
    else:
        all_passed = False
        all_errors.extend(errors)
        for error in errors:
            print_error(error)
    
    # 9. Check recommended variables
    print_header("Checking Recommended Variables")
    passed, warnings = check_recommended_variables(env_vars)
    if warnings:
        all_warnings.extend(warnings)
        for warning in warnings:
            print_warning(warning)
    else:
        print_success("All recommended variables are set")
    
    # Print summary
    print_header("Validation Summary")
    
    if all_passed:
        print_success("✅ All validations passed!")
        if all_warnings:
            print(f"\n{YELLOW}Warnings: {len(all_warnings)}{RESET}")
            for warning in all_warnings:
                print(f"  {YELLOW}⚠️  {warning}{RESET}")
        print()
        return 0
    else:
        print_error(f"❌ Validation failed with {len(all_errors)} error(s)")
        print()
        for error in all_errors:
            print(f"  {RED}❌ {error}{RESET}")
        
        if all_warnings:
            print(f"\n{YELLOW}Warnings: {len(all_warnings)}{RESET}")
            for warning in all_warnings:
                print(f"  {YELLOW}⚠️  {warning}{RESET}")
        
        print()
        generate_secrets_help()
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Validation interrupted by user{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {str(e)}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
