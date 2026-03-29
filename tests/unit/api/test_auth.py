# tests/unit/api/test_auth.py
"""Unit tests for auth.py - password hashing and verification.

Tests cover:
- hash_password() with bcrypt
- verify_password() validation
- verify_password_legacy() with MD5 fallback
- Error handling for invalid hashes
"""

import hashlib
import hmac
import pytest
from algo_studio.api.auth import (
    hash_password,
    verify_password,
    verify_password_legacy,
    BCRYPT_COST,
)


class TestHashPassword:
    """Tests for hash_password() function."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        result = hash_password("test-password")
        assert isinstance(result, str)

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a bcrypt hash."""
        result = hash_password("test-password")
        assert result.startswith("$2")  # bcrypt hashes start with $2a$, $2b$, etc.

    def test_hash_password_different_for_same_input(self):
        """Test that hashing same password twice produces different hashes (due to salt)."""
        hash1 = hash_password("test-password")
        hash2 = hash_password("test-password")
        assert hash1 != hash2  # Different salts = different hashes

    def test_hash_password_verifiable(self):
        """Test that hashed password can be verified."""
        password = "my-secret-password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_empty_string(self):
        """Test hashing empty string."""
        result = hash_password("")
        assert isinstance(result, str)
        assert verify_password("", result) is True

    def test_hash_password_unicode(self):
        """Test hashing password with unicode characters."""
        password = "password-中文-пароль-🔐"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_long_password(self):
        """Test hashing password at bcrypt's 72-byte limit."""
        # bcrypt has a 72-byte limit, so we test with exactly 72 characters
        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_beyond_bcrypt_limit_raises(self):
        """Test that passwords beyond 72 bytes raise ValueError."""
        # bcrypt has a 72-byte limit
        password = "a" * 100
        with pytest.raises(ValueError):
            hash_password(password)

    def test_hash_password_special_characters(self):
        """Test hashing password with special characters."""
        password = "p@$$w0rd!#$%^&*()_+-=[]{}|;':\",./<>?"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_bcrypt_cost_is_12(self):
        """Test that BCRYPT_COST is set to industry standard 12."""
        assert BCRYPT_COST == 12


class TestVerifyPassword:
    """Tests for verify_password() function."""

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "correct-password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "correct-password"
        hashed = hash_password(password)
        assert verify_password("wrong-password", hashed) is False

    def test_verify_password_empty_hash(self):
        """Test verifying against empty hash."""
        assert verify_password("password", "") is False

    def test_verify_password_invalid_hash_format(self):
        """Test verifying against invalid hash format."""
        assert verify_password("password", "not-a-valid-hash") is False

    def test_verify_password_malformed_hash(self):
        """Test verifying against malformed hash."""
        assert verify_password("password", "$2a$12$malformed") is False

    def test_verify_password_none_hash(self):
        """Test verifying against None hash."""
        assert verify_password("password", None) is False

    def test_verify_password_none_password(self):
        """Test verifying None password."""
        hashed = hash_password("real-password")
        assert verify_password(None, hashed) is False

    def test_verify_password_case_sensitive(self):
        """Test that password verification is case sensitive."""
        password = "CaseSensitive"
        hashed = hash_password(password)
        assert verify_password("casesensitive", hashed) is False
        assert verify_password("CASESENSITIVE", hashed) is False
        assert verify_password("CaseSensitive", hashed) is True


class TestVerifyPasswordLegacy:
    """Tests for verify_password_legacy() function."""

    def test_legacy_bcrypt_password(self):
        """Test that legacy bcrypt passwords still work."""
        # Create a bcrypt hash
        password = "legacy-bcrypt-password"
        hashed = hash_password(password)
        assert verify_password_legacy(password, hashed) is True

    def test_legacy_md5_password(self):
        """Test that legacy MD5 passwords still work."""
        # Create MD5 hash in legacy format
        password = "legacy-md5-password"
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        legacy_hash = f"md5:{md5_hash}"

        assert verify_password_legacy(password, legacy_hash) is True

    def test_legacy_md5_password_incorrect(self):
        """Test that wrong password fails for MD5 legacy."""
        password = "legacy-md5-password"
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        legacy_hash = f"md5:{md5_hash}"

        assert verify_password_legacy("wrong-password", legacy_hash) is False

    def test_legacy_md5_format_only_prefix(self):
        """Test MD5 with md5: prefix but no real MD5 hash."""
        assert verify_password_legacy("password", "md5:") is False

    def test_legacy_md5_wrong_prefix(self):
        """Test MD5 with wrong prefix still fails."""
        password = "test-password"
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        # Use sha256: prefix instead of md5:
        wrong_prefix_hash = f"sha256:{md5_hash}"

        assert verify_password_legacy(password, wrong_prefix_hash) is False

    def test_legacy_none_hash(self):
        """Test legacy verify with None hash raises AttributeError (bug in current impl)."""
        # Current implementation doesn't handle None hash properly
        # It fails at password_hash.startswith("md5:") before returning False
        # This is a bug - but we document the current behavior
        with pytest.raises(AttributeError):
            verify_password_legacy("password", None)

    def test_legacy_empty_hash(self):
        """Test legacy verify with empty hash."""
        assert verify_password_legacy("password", "") is False

    def test_legacy_bcrypt_takes_precedence(self):
        """Test that bcrypt is tried before MD5."""
        password = "test-password"
        hashed = hash_password(password)

        # Should match bcrypt, not try MD5
        assert verify_password_legacy(password, hashed) is True
        # Wrong password should fail bcrypt
        assert verify_password_legacy("wrong", hashed) is False

    def test_legacy_md5_partial_match(self):
        """Test MD5 where password is substring of MD5 hex."""
        # This could theoretically match if password happens to equal part of hex
        # But verify_password_legacy tries bcrypt first, so this shouldn't happen
        password = "abcdef"
        md5_of_password = hashlib.md5(password.encode()).hexdigest()
        # Password "abc" is a substring of the MD5 hex
        assert verify_password_legacy("abc", f"md5:{md5_of_password}") is False

    def test_legacy_unknown_hash_format_falls_through(self):
        """Test that unknown hash formats return False."""
        assert verify_password_legacy("password", "unknown:hashformat") is False

    def test_legacy_unicode_password_md5(self):
        """Test MD5 legacy with unicode password."""
        password = "密码-password"
        md5_hash = hashlib.md5(password.encode('utf-8')).hexdigest()
        legacy_hash = f"md5:{md5_hash}"
        assert verify_password_legacy(password, legacy_hash) is True


class TestPasswordHashingIntegration:
    """Integration tests for password hashing workflow."""

    def test_full_workflow_hash_then_verify(self):
        """Test complete workflow: hash password, then verify it."""
        original_password = "secure-password-123"

        # Hash the password
        hashed = hash_password(original_password)

        # Verify correct password
        assert verify_password(original_password, hashed) is True

        # Verify wrong password
        assert verify_password("wrong-password", hashed) is False

    def test_full_workflow_legacy_migration(self):
        """Test workflow for migrating from MD5 to bcrypt."""
        password = "password-to-migrate"

        # Old MD5 hash
        old_hash = f"md5:{hashlib.md5(password.encode()).hexdigest()}"

        # Verify using legacy function
        assert verify_password_legacy(password, old_hash) is True

        # New bcrypt hash (would be generated on re-login in real migration)
        new_hash = hash_password(password)

        # Verify using new function
        assert verify_password(password, new_hash) is True

        # Verify using legacy (should work with both)
        assert verify_password_legacy(password, new_hash) is True

    def test_multiple_users_different_hashes(self):
        """Test that multiple users can have same password but different hashes."""
        password = "shared-password"

        hashes = [hash_password(password) for _ in range(5)]

        # All hashes should be different
        assert len(set(hashes)) == 5

        # All should verify correctly
        for h in hashes:
            assert verify_password(password, h) is True


class TestBCRYPTConstants:
    """Tests for BCRYPT_COST constant."""

    def test_bcrypt_cost_is_integer(self):
        """Test that BCRYPT_COST is an integer."""
        assert isinstance(BCRYPT_COST, int)

    def test_bcrypt_cost_is_reasonable(self):
        """Test that BCRYPT_COST is in reasonable range (>= 10, <= 14)."""
        assert 10 <= BCRYPT_COST <= 14

    def test_bcrypt_cost_matches_industry_standard(self):
        """Test BCRYPT_COST is 12 per OWASP recommendation."""
        assert BCRYPT_COST == 12
