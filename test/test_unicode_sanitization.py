#!/usr/bin/env python3
"""Test Unicode sanitization functionality."""

import pytest
from claude_code_log.converter import sanitize_unicode_for_utf8


class TestUnicodeSanitization:
    """Test cases for Unicode sanitization."""
    
    def test_normal_text_unchanged(self):
        """Normal text should pass through unchanged."""
        text = "Hello, world! This is normal text with emojis: 😀🌍"
        result = sanitize_unicode_for_utf8(text)
        assert result == text
        
    def test_empty_string(self):
        """Empty string should be handled correctly."""
        result = sanitize_unicode_for_utf8("")
        assert result == ""
        
    def test_none_input(self):
        """None input should be handled correctly.""" 
        result = sanitize_unicode_for_utf8(None)
        assert result is None
        
    def test_surrogate_characters_replaced(self):
        """Surrogate characters should be replaced with replacement character."""
        # Create a string with a high surrogate character
        text_with_surrogate = "Text with surrogate: \ud83d and more text"
        result = sanitize_unicode_for_utf8(text_with_surrogate)
        
        # The surrogate should be replaced with some replacement character
        assert "\ud83d" not in result
        # Check that some replacement occurred (could be '?' or '\ufffd')
        assert ("�" in result or "?" in result or "\ufffd" in result)
        assert "Text with surrogate:" in result
        assert "and more text" in result
        
    def test_encoding_errors_handled(self):
        """Text that causes encoding errors should be sanitized."""
        # This should be handled gracefully even if it causes encoding issues
        problematic_text = "Normal text \ud83d incomplete emoji \ude00 more text"
        result = sanitize_unicode_for_utf8(problematic_text)
        
        # Should not raise an exception and should replace problematic characters
        assert result is not None
        assert "Normal text" in result
        assert "more text" in result
        # Surrogates should be replaced
        assert "\ud83d" not in result
        assert "\ude00" not in result
        
    def test_valid_unicode_preserved(self):
        """Valid Unicode characters including emojis should be preserved."""
        text = "Hello 👋 World 🌍 with various unicode: café, naïve, résumé"
        result = sanitize_unicode_for_utf8(text)
        assert result == text
        
    def test_can_encode_result(self):
        """The result should always be encodable as UTF-8."""
        # Test with various problematic inputs
        test_cases = [
            "Normal text",
            "Text with \ud83d surrogate",
            "Multiple \ud83d \ude00 surrogates \udead",
            "Mixed \ud83d valid 😀 and \ude00 invalid",
            "",
        ]
        
        for test_text in test_cases:
            result = sanitize_unicode_for_utf8(test_text)
            # This should never raise UnicodeEncodeError
            try:
                result.encode('utf-8')
            except UnicodeEncodeError:
                pytest.fail(f"Sanitized text still cannot be encoded: {repr(result)}")