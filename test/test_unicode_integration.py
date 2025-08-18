#!/usr/bin/env python3
"""Integration test for Unicode error handling."""

import pytest
import tempfile
import json
from pathlib import Path
from claude_code_log.converter import convert_jsonl_to_html


class TestUnicodeIntegration:
    """Integration tests for Unicode error handling."""
    
    def test_problematic_unicode_file_conversion(self):
        """Test that files with problematic Unicode can be converted without errors."""
        
        # Create a test JSONL file with problematic Unicode characters
        test_data = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Test message with problematic Unicode"
            },
            "uuid": "test-uuid-123",
            "sessionId": "test-session-123",
            "timestamp": "2025-08-18T17:00:00.000Z",
            "parentUuid": None,
            "isSidechain": False,
            "userType": "external",
            "cwd": "/test/path",
            "version": "1.0.0",
            "gitBranch": "main"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_problematic_unicode.jsonl"
            output_file = Path(temp_dir) / "output.html"
            
            # Write the test data as JSON
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(test_data, f)
            
            # Read the file and add problematic characters
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace part of the content with problematic surrogate characters
            problematic_content = content.replace(
                "Test message with problematic Unicode",
                "Test message with \ud83d surrogate and \ude00 more \udead characters"
            )
            
            # Write back using surrogatepass to allow writing surrogates
            with open(test_file, 'w', encoding='utf-8', errors='surrogatepass') as f:
                f.write(problematic_content)
            
            # Convert the file - this should not raise UnicodeEncodeError
            result_path = convert_jsonl_to_html(test_file, output_file, use_cache=False)
            
            # Verify the output file was created
            assert output_file.exists()
            assert result_path == output_file
            
            # Verify the output can be read as UTF-8
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Verify the HTML content is non-empty and contains expected content
            assert len(html_content) > 0
            assert "Test message with" in html_content
            
            # Verify no surrogate characters remain in the output
            for char in html_content:
                code_point = ord(char)
                assert not (0xD800 <= code_point <= 0xDFFF), f"Found surrogate character {hex(code_point)} in output"
                
    def test_directory_mode_with_problematic_unicode(self):
        """Test directory processing with problematic Unicode files."""
        
        test_data = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Directory test with unicode issues"
            },
            "uuid": "test-uuid-456",
            "sessionId": "test-session-456",
            "timestamp": "2025-08-18T17:00:00.000Z",
            "parentUuid": None,
            "isSidechain": False,
            "userType": "external",
            "cwd": "/test/path",
            "version": "1.0.0",
            "gitBranch": "main"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "test_project"
            project_dir.mkdir()
            
            test_file = project_dir / "test_unicode.jsonl"
            
            # Create file with problematic content
            with open(test_file, 'w', encoding='utf-8') as f:
                json.dump(test_data, f)
            
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            problematic_content = content.replace(
                "Directory test with unicode issues",
                "Directory test with \ud83d unicode \ude00 issues"
            )
            
            with open(test_file, 'w', encoding='utf-8', errors='surrogatepass') as f:
                f.write(problematic_content)
            
            # Process the directory - should not raise UnicodeEncodeError
            result_path = convert_jsonl_to_html(project_dir, use_cache=False)
            
            # Verify output files were created
            expected_output = project_dir / "combined_transcripts.html"
            assert expected_output.exists()
            assert result_path == expected_output
            
            # Verify content is readable and clean
            with open(expected_output, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            assert len(html_content) > 0
            assert "Directory test with" in html_content
            
            # Verify no surrogate characters remain
            for char in html_content:
                code_point = ord(char)
                assert not (0xD800 <= code_point <= 0xDFFF), f"Found surrogate character {hex(code_point)} in output"