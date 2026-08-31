"""Tests for the crash handler module, specifically sensitive line redaction."""

import sys
import textwrap
from pathlib import Path

from avatars import __version__
from avatars.crash_handler import (
    REDACTED_PLACEHOLDER,
    _find_sensitive_lines_from_source,
    _is_sensitive_variable_name,
    generate_crash_report,
    get_full_file_content,
    is_user_code,
)


class TestIsUserCode:
    """Tests for determining if a file is user code or library code."""

    def test_regular_user_file_is_user_code(self) -> None:
        """A regular Python file in a user's project is considered user code."""
        assert is_user_code("/home/user/project/my_script.py") is True
        assert is_user_code("/Users/john/work/analysis.py") is True
        assert is_user_code("C:\\Users\\john\\project\\main.py") is True

    def test_site_packages_is_library_code(self) -> None:
        """Files in site-packages are considered library code."""
        assert is_user_code("/usr/lib/python3.10/site-packages/requests/api.py") is False
        assert is_user_code("/home/user/.venv/lib/python3.10/site-packages/numpy/core.py") is False

    def test_dist_packages_is_library_code(self) -> None:
        """Files in dist-packages are considered library code."""
        assert is_user_code("/usr/lib/python3/dist-packages/apt/cache.py") is False

    def test_lib_python_is_library_code(self) -> None:
        """Files in lib/python paths are considered library code."""
        assert is_user_code("/usr/lib/python3.10/os.py") is False

    def test_avatars_library_is_treated_as_user_code(self) -> None:
        """The avatars library should be treated as user code even when installed."""
        # When avatars is installed in site-packages, it should still show context
        assert (
            is_user_code("/home/user/.venv/lib/python3.10/site-packages/avatars/runner.py") is True
        )
        assert is_user_code("/usr/lib/python3.10/site-packages/avatars/manager.py") is True
        assert (
            is_user_code("/home/user/.venv/lib/python3.10/site-packages/avatars/crash_handler.py")
            is True
        )

    def test_avatars_in_development_is_user_code(self) -> None:
        """The avatars library in development mode is user code."""
        assert is_user_code("/home/user/dev/avatar/services/client/src/avatars/runner.py") is True


class TestIsSensitiveVariableName:
    """Tests for fuzzy matching of sensitive variable names."""

    def test_exact_matches(self) -> None:
        """Exact sensitive names are detected."""
        assert _is_sensitive_variable_name("password") is True
        assert _is_sensitive_variable_name("secret") is True
        assert _is_sensitive_variable_name("apikey") is True
        assert _is_sensitive_variable_name("pwd") is True

    def test_case_insensitive(self) -> None:
        """Matching is case-insensitive."""
        assert _is_sensitive_variable_name("PASSWORD") is True
        assert _is_sensitive_variable_name("Password") is True
        assert _is_sensitive_variable_name("SECRET") is True
        assert _is_sensitive_variable_name("ApiKey") is True

    def test_underscore_variations(self) -> None:
        """Underscores are ignored in matching."""
        assert _is_sensitive_variable_name("api_key") is True
        assert _is_sensitive_variable_name("API_KEY") is True
        assert _is_sensitive_variable_name("pass_word") is True

    def test_common_variations(self) -> None:
        """Common variations of sensitive names are detected."""
        assert _is_sensitive_variable_name("passwd") is True  # 86% match to password
        assert _is_sensitive_variable_name("secrets") is True  # 92% match to secret
        assert _is_sensitive_variable_name("passwords") is True  # high match to password
        assert _is_sensitive_variable_name("api_keys") is True  # high match to apikey

    def test_short_abbreviations_matched(self) -> None:
        """Short abbreviations are matched via explicit patterns."""
        assert _is_sensitive_variable_name("pwd") is True
        assert _is_sensitive_variable_name("PWD") is True
        assert _is_sensitive_variable_name("pw") is True

    def test_non_sensitive_names(self) -> None:
        """Non-sensitive variable names are not flagged."""
        assert _is_sensitive_variable_name("username") is False
        assert _is_sensitive_variable_name("email") is False
        assert _is_sensitive_variable_name("data") is False
        assert _is_sensitive_variable_name("config") is False
        assert _is_sensitive_variable_name("url") is False
        assert _is_sensitive_variable_name("api") is False


class TestFindSensitiveLines:
    """Tests for AST-based sensitive line detection."""

    def test_finds_manager_call_with_api_key_variable(self) -> None:
        """Detect Manager(api_key=...) call and the api_key variable assignment."""
        source = textwrap.dedent("""
            base_url = "https://avatar.example.com"
            api_key = "secret123"
            manager = Manager(base_url=base_url, api_key=api_key)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # Line 2: api_key assignment, Line 3: Manager(...) call
        assert 2 in sensitive_lines
        assert 3 in sensitive_lines
        # Line 1 (base_url) should not be redacted
        assert 1 not in sensitive_lines

    def test_finds_multiple_manager_calls(self) -> None:
        """Detect multiple Manager(...) calls with different api_key variables."""
        source = textwrap.dedent("""
            key1 = "first_secret"
            manager1 = Manager(api_key=key1)
            key2 = "second_secret"
            manager2 = Manager(api_key=key2)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # All api_key assignments and Manager(...) calls should be redacted
        assert 1 in sensitive_lines  # key1 assignment
        assert 2 in sensitive_lines  # first Manager(...) call
        assert 3 in sensitive_lines  # key2 assignment
        assert 4 in sensitive_lines  # second Manager(...) call

    def test_literal_api_key_only_redacts_call(self) -> None:
        """When api_key is a literal, only the Manager(...) call is redacted."""
        source = textwrap.dedent("""
            base_url = "https://avatar.example.com"
            manager = Manager(base_url=base_url, api_key="literal_key")
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # Only the Manager(...) call should be redacted (line 2)
        assert 2 in sensitive_lines
        # base_url line should not be redacted
        assert 1 not in sensitive_lines

    def test_api_key_from_env_var(self) -> None:
        """Detect api_key assignment from os.environ.get()."""
        source = textwrap.dedent("""
            import os
            base_url = os.environ.get("AVATAR_URL")
            api_key = os.environ.get("AVATAR_API_KEY")
            manager = Manager(base_url=base_url, api_key=api_key)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # api_key assignment and Manager(...) call should be redacted
        assert 3 in sensitive_lines  # api_key = os.environ.get(...)
        assert 4 in sensitive_lines  # Manager(...) call
        # import and base_url should not be redacted
        assert 1 not in sensitive_lines
        assert 2 not in sensitive_lines

    def test_no_manager_call(self) -> None:
        """Sensitive variable names are redacted even without a Manager(...) call."""
        source = textwrap.dedent("""
            password = "secret"
            print(password)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # password assignment should still be redacted (sensitive variable name)
        assert 1 in sensitive_lines
        # print statement should not be redacted
        assert 2 not in sensitive_lines

    def test_multiline_manager_call(self) -> None:
        """Detect multiline Manager(...) calls."""
        source = textwrap.dedent("""
            api_key = "secret"
            manager = Manager(
                base_url="https://avatar.example.com",
                api_key=api_key
            )
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # api_key assignment should be redacted
        assert 1 in sensitive_lines
        # All lines of the multiline call should be redacted
        assert 2 in sensitive_lines
        assert 3 in sensitive_lines
        assert 4 in sensitive_lines
        assert 5 in sensitive_lines

    def test_annotated_assignment(self) -> None:
        """Detect type-annotated api_key assignments."""
        source = textwrap.dedent("""
            api_key: str = "secret"
            manager = Manager(api_key=api_key)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # Both the annotated assignment and the Manager(...) call should be redacted
        assert 1 in sensitive_lines
        assert 2 in sensitive_lines

    def test_syntax_error_returns_empty_set(self) -> None:
        """Invalid Python syntax returns empty set (graceful degradation)."""
        source = "this is not valid python code {"

        sensitive_lines = _find_sensitive_lines_from_source(source)

        assert len(sensitive_lines) == 0

    def test_sensitive_variable_names_without_manager_call(self) -> None:
        """Various sensitive variable names are redacted via fuzzy matching."""
        source = textwrap.dedent("""
            password = "secret1"
            passwd = "secret2"
            secret = "secret3"
            api_key = "key123"
            apikey = "key456"
            secrets = "multiple"
            username = "user"
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # All sensitive variable assignments should be redacted (fuzzy matched)
        assert 1 in sensitive_lines  # password
        assert 2 in sensitive_lines  # passwd (fuzzy matches "password")
        assert 3 in sensitive_lines  # secret
        assert 4 in sensitive_lines  # api_key (underscores removed -> apikey)
        assert 5 in sensitive_lines  # apikey
        assert 6 in sensitive_lines  # secrets (fuzzy matches "secret")
        # username is not sensitive
        assert 7 not in sensitive_lines

    def test_manager_call_via_attribute_access(self) -> None:
        """Detect Manager(...) calls reached through attribute access."""
        source = textwrap.dedent("""
            key = "secret"
            manager = avatars.manager.Manager(api_key=key)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        assert 1 in sensitive_lines  # key assignment
        assert 2 in sensitive_lines  # avatars.manager.Manager(...) call

    def test_manager_call_without_api_key_not_redacted(self) -> None:
        """A Manager(...) call without an api_key argument is not redacted."""
        source = textwrap.dedent("""
            manager = Manager(base_url="https://avatar.example.com")
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        assert 1 not in sensitive_lines

    def test_same_variable_reused_for_api_key(self) -> None:
        """Handle cases where the same variable is assigned multiple times."""
        source = textwrap.dedent("""
            key = get_api_key_from_keychain()
            manager1 = Manager(api_key=key)
            key = "new_key"
            manager2 = Manager(api_key=key)
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # All key assignments and Manager(...) calls should be redacted
        assert 1 in sensitive_lines
        assert 2 in sensitive_lines
        assert 3 in sensitive_lines
        assert 4 in sensitive_lines

    def test_realistic_quickstart_pattern(self) -> None:
        """Test a realistic pattern from the quickstart tutorial."""
        source = textwrap.dedent("""
            import os
            from avatars.manager import Manager

            api_key = os.environ.get("AVATAR_API_KEY", "")

            manager = Manager(api_key=api_key)

            runner = manager.create_runner(set_name="test")
            runner.add_table("data", "data.csv")
        """).strip()

        sensitive_lines = _find_sensitive_lines_from_source(source)

        # api_key assignment (line 4) and Manager(...) call (line 6) should be redacted
        assert 4 in sensitive_lines  # api_key = os.environ.get(...)
        assert 6 in sensitive_lines  # manager = Manager(api_key=api_key)

        # These should NOT be redacted
        assert 1 not in sensitive_lines  # import os
        assert 2 not in sensitive_lines  # from avatars...
        assert 8 not in sensitive_lines  # runner = ...
        assert 9 not in sensitive_lines  # runner.add_table...


class TestCrashReportIntegration:
    """Integration tests verifying the full crash report redacts sensitive info."""

    def test_get_full_file_content_redacts_api_key(self, tmp_path: Path) -> None:
        """Verify get_full_file_content redacts api_key lines in a real file."""
        # Create a temporary Python file with sensitive content
        test_file = tmp_path / "user_script.py"
        test_file.write_text(
            textwrap.dedent("""
                import os
                from avatars.manager import Manager

                base_url = os.environ.get("AVATAR_URL")
                api_key = "super_secret_key_12345"

                manager = Manager(base_url=base_url, api_key=api_key)

                runner = manager.create_runner(set_name="test")
            """).strip()
        )

        content = get_full_file_content(str(test_file))

        # Verify api_key-related lines are redacted
        assert REDACTED_PLACEHOLDER in content

        # Verify actual secrets are NOT in the output
        assert "super_secret_key_12345" not in content
        assert "Manager(base_url=base_url, api_key=api_key)" not in content

        # Verify non-sensitive content IS present
        assert "import os" in content
        assert "AVATAR_URL" in content
        assert 'set_name="test"' in content

    def test_full_crash_report_redacts_sensitive_info(self, tmp_path: Path) -> None:
        """Verify the complete crash report redacts sensitive information in stack context."""
        # Create a temporary Python file with sensitive content that will raise
        test_file = tmp_path / "user_script.py"
        script_content = textwrap.dedent("""
            import os
            password = "my_super_secret_password"
            secret = "another_secret_value"
            username = "safe_username"
            raise ValueError("intentional error for testing")
        """).strip()
        test_file.write_text(script_content)

        # Simulate an exception with a traceback pointing to our test file
        try:
            exec(compile(script_content, str(test_file), "exec"))
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()

            # Generate the crash report
            report = generate_crash_report(exc_type, exc_value, exc_tb)  # type: ignore[arg-type]

            # The stack trace context for the temp file should have redacted lines
            # Find the section for the temp file in the stack trace
            temp_file_section_start = report.find(str(test_file))
            assert temp_file_section_start != -1, "Temp file should be in the report"

            # Extract just the context section for the temp file
            context_start = report.find("Context:", temp_file_section_start)
            # Find the next section (either another [USER]/[LIB] or the === divider)
            next_section = report.find("\n[", context_start)
            full_file_section = report.find("FULL USER FILE CONTENT", context_start)
            end_marker = min(
                next_section if next_section != -1 else len(report),
                full_file_section if full_file_section != -1 else len(report),
            )
            temp_file_context = report[context_start:end_marker]

            # The context for the temp file should have REDACTED placeholders
            assert REDACTED_PLACEHOLDER in temp_file_context

            # The context should NOT show the actual password/secret values
            # (they should be redacted)
            assert "my_super_secret_password" not in temp_file_context
            assert "another_secret_value" not in temp_file_context

            # But safe content should still be visible in context
            assert "safe_username" in temp_file_context

            # The crash report structure should be correct
            assert "CRASH REPORT" in report
            assert "EXCEPTION" in report

    def test_crash_report_includes_sdk_version(self, tmp_path: Path) -> None:
        """Verify the crash report includes the Avatars SDK version."""
        test_file = tmp_path / "simple_script.py"
        script_content = 'raise ValueError("test error")'
        test_file.write_text(script_content)

        try:
            exec(compile(script_content, str(test_file), "exec"))
        except ValueError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            report = generate_crash_report(exc_type, exc_value, exc_tb)  # type: ignore[arg-type]

            # Verify the SDK version is in the system information section
            assert f"Avatars SDK: {__version__}" in report
