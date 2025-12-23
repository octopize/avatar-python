"""
Global custom exception hook for crash reporting.

This module implements a sys.excepthook handler that:
1. Executes pre-crash cleanup commands
2. Generates detailed crash reports with system info and stack traces
3. Shows source code context for user code while filtering library frames
4. Includes full content of the user's main script file
5. Dumps YAML config from all Runner instances

Note: This module intentionally uses print() to stderr and broad exception
handling because during a crash, logging infrastructure may not be available
and we must ensure the crash handler itself doesn't fail.
"""
# ruff: noqa: T201, BLE001

from __future__ import annotations

import ast
import linecache
import os
import platform
import sys
import traceback
import weakref
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

from avatars import __version__
from avatars.config import config

# Placeholder for redacted sensitive content
REDACTED_PLACEHOLDER = "[REDACTED - SENSITIVE]"

if TYPE_CHECKING:
    from avatars.runner import Runner

# --- Configuration ---
# Patterns that identify "Library" code to hide detailed context for
LIBRARY_PATHS = ["site-packages", "dist-packages", "lib/python"]

# Patterns that identify our own library code (should NOT be hidden)
OWN_LIBRARY_PATTERNS = ["avatars"]

# Number of context lines to show before and after the error line
CONTEXT_LINES = 3

# Default crash report filename

# Global registry of Runner instances (weak references to avoid memory leaks)
_runner_registry: weakref.WeakSet[Runner] = weakref.WeakSet()


def register_runner(runner: Runner) -> None:
    """
    Register a Runner instance for crash reporting.

    Args:
        runner: The Runner instance to register.
    """
    _runner_registry.add(runner)


def unregister_runner(runner: Runner) -> None:
    """
    Unregister a Runner instance.

    Args:
        runner: The Runner instance to unregister.
    """
    _runner_registry.discard(runner)


def _get_runner_yaml_dumps() -> list[tuple[str, str]]:
    """
    Get YAML dumps from all registered Runner instances.

    Returns:
        List of (display_name, yaml_content) tuples.
    """
    results = []
    for runner in list(_runner_registry):
        try:
            yaml_content = runner.get_yaml()
            display_name = runner.display_name or "unnamed"
            results.append((display_name, yaml_content))
        except Exception as e:
            results.append((getattr(runner, "display_name", "unknown"), f"Error: {e}"))
    return results


def pre_crash_command() -> None:
    """
    Command to run before showing the exception.

    This function silently captures Runner YAML configs for the crash report.
    """
    # Silently dump YAML from all Runner instances (no user-visible output)
    _get_runner_yaml_dumps()


def get_file_context(filename: str, lineno: int, context_lines: int = CONTEXT_LINES) -> str:
    """
    Read the file and return lines of code around the error.

    Args:
        filename: Path to the source file.
        lineno: The line number where the error occurred.
        context_lines: Number of lines to show before and after.

    Returns:
        A formatted string with the code context, with the error line marked.
    """
    start = max(1, lineno - context_lines)
    end = lineno + context_lines
    code_snippet = []

    # Get sensitive lines to redact
    sensitive_lines = _find_sensitive_lines(filename)

    try:
        # linecache is efficient and handles caching automatically
        for i in range(start, end + 1):
            line = linecache.getline(filename, i).rstrip()
            if line or i == lineno:  # Always show the error line even if empty
                marker = "-> " if i == lineno else "   "
                if i in sensitive_lines:
                    code_snippet.append(f"{marker}{i}: {REDACTED_PLACEHOLDER}")
                else:
                    code_snippet.append(f"{marker}{i}: {line}")
    except Exception:
        code_snippet.append("   (Could not retrieve source code)")

    return "\n".join(code_snippet) if code_snippet else "   (No source code available)"


def _find_sensitive_lines(filename: str) -> set[int]:
    """
    Parse a Python file and find lines that contain sensitive information.

    This uses AST parsing to find:
    1. Lines containing .authenticate(...) calls
    2. Lines that assign values to variables used as the password argument

    Args:
        filename: Path to the Python source file.

    Returns:
        A set of 1-indexed line numbers that should be redacted.
    """
    try:
        with open(filename, encoding="utf-8") as f:
            source = f.read()
        return _find_sensitive_lines_from_source(source)
    except Exception:
        return set()


# Patterns for fuzzy matching sensitive variable names
_SENSITIVE_PATTERNS = ("password", "secret", "apikey", "pwd")

# Threshold for fuzzy matching (0.0 to 1.0)
_FUZZY_MATCH_THRESHOLD = 0.8


def _is_sensitive_variable_name(name: str) -> bool:
    """
    Check if a variable name is sensitive using fuzzy string matching.

    Args:
        name: The variable name to check.

    Returns:
        True if the name fuzzy-matches a sensitive pattern.
    """
    # Normalize: lowercase and remove underscores for comparison
    normalized = name.lower().replace("_", "")

    for pattern in _SENSITIVE_PATTERNS:
        if SequenceMatcher(None, normalized, pattern).ratio() >= _FUZZY_MATCH_THRESHOLD:
            return True
    return False


def _find_sensitive_lines_from_source(source: str) -> set[int]:
    """
    Parse Python source code and find lines containing sensitive information.

    Args:
        source: Python source code as a string.

    Returns:
        A set of 1-indexed line numbers that should be redacted.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    sensitive_lines: set[int] = set()
    password_variables: set[str] = set()

    # First pass: find all .authenticate() calls and collect password variable names
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if this is a .authenticate(...) method call
            if isinstance(node.func, ast.Attribute) and node.func.attr == "authenticate":
                # Mark the line(s) of the authenticate call as sensitive
                sensitive_lines.add(node.lineno)
                if hasattr(node, "end_lineno") and node.end_lineno:
                    for line in range(node.lineno, node.end_lineno + 1):
                        sensitive_lines.add(line)

                # Find the password argument (2nd positional or password= keyword)
                password_arg = None

                # Check positional arguments (password is typically 2nd arg)
                if len(node.args) >= 2:
                    password_arg = node.args[1]

                # Check keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == "password":
                        password_arg = keyword.value
                        break

                # If password arg is a variable name, track it for redaction
                if password_arg is not None and isinstance(password_arg, ast.Name):
                    password_variables.add(password_arg.id)

    # Second pass: find all assignments to password variables or sensitive variable names
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    # Redact if it's a tracked password variable OR has a sensitive name
                    if target.id in password_variables or _is_sensitive_variable_name(target.id):
                        sensitive_lines.add(node.lineno)
                        if hasattr(node, "end_lineno") and node.end_lineno:
                            for line in range(node.lineno, node.end_lineno + 1):
                                sensitive_lines.add(line)
        elif isinstance(node, ast.AnnAssign):
            # Handle annotated assignments like `password: str = "secret"`
            if isinstance(node.target, ast.Name) and node.value is not None:
                if node.target.id in password_variables or _is_sensitive_variable_name(
                    node.target.id
                ):
                    sensitive_lines.add(node.lineno)
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        for line in range(node.lineno, node.end_lineno + 1):
                            sensitive_lines.add(line)

    return sensitive_lines


def get_full_file_content(filename: str) -> str:
    """
    Read and return the entire content of a file with line numbers.

    Sensitive lines (containing passwords or authenticate calls) are redacted.

    Args:
        filename: Path to the source file.

    Returns:
        The full file content with line numbers, with sensitive lines redacted.
    """
    try:
        with open(filename, encoding="utf-8") as f:
            lines = f.readlines()

        # Get sensitive lines to redact
        sensitive_lines = _find_sensitive_lines(filename)

        numbered_lines = []
        for i, line in enumerate(lines, 1):
            if i in sensitive_lines:
                numbered_lines.append(f"{i:4d}: {REDACTED_PLACEHOLDER}")
            else:
                numbered_lines.append(f"{i:4d}: {line.rstrip()}")
        return "\n".join(numbered_lines)
    except Exception as e:
        return f"(Could not read file: {e})"


def _find_user_main_file(exc_tb: TracebackType | None) -> str | None:
    """
    Find the main user file from the traceback (first user code frame).

    Args:
        exc_tb: The traceback object.

    Returns:
        The path to the main user file, or None if not found.
    """
    if exc_tb is None:
        return None

    stack_summary = traceback.extract_tb(exc_tb)
    for frame in stack_summary:
        if is_user_code(frame.filename):
            return frame.filename
    return None


def is_user_code(filename: str) -> bool:
    """
    Heuristic to determine if a file is user code or library code.

    Args:
        filename: The file path to check.

    Returns:
        True if the file appears to be user code, False for library code.
        Note: Our own library (avatars) is treated as user code so its
        context is shown in crash reports.
    """
    # First check if this is our own library - always show context for it
    for own_pattern in OWN_LIBRARY_PATTERNS:
        if own_pattern in filename:
            return True

    # If the file path contains typical library indicators, it's not user code
    for path_pattern in LIBRARY_PATHS:
        if path_pattern in filename:
            return False
    return True


def generate_crash_report(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> str:
    """
    Generate a detailed crash report.

    Args:
        exc_type: The exception type.
        exc_value: The exception instance.
        exc_tb: The traceback object.

    Returns:
        A formatted crash report string.
    """
    report = []
    report.append("=" * 60)
    report.append(f"CRASH REPORT - {datetime.now().isoformat()}")
    report.append("=" * 60)

    # System/Environment information
    report.append("\n[SYSTEM INFORMATION]")
    report.append(f"  OS: {platform.system()} {platform.release()} ({platform.machine()})")
    report.append(f"  Python: {platform.python_version()}")
    report.append(f"  Avatars SDK: {__version__}")
    report.append(f"  Executable: {sys.executable}")
    report.append(f"  Working Directory: {os.getcwd()}")

    # Exception details
    report.append("\n[EXCEPTION]")
    report.append(f"  Type: {exc_type.__module__}.{exc_type.__name__}")
    report.append(f"  Message: {exc_value}")

    report.append("\n" + "-" * 60)
    report.append("STACK TRACE & SOURCE CONTEXT")
    report.append("-" * 60)

    # Walk through the stack trace
    if exc_tb is not None:
        stack_summary = traceback.extract_tb(exc_tb)

        for frame in stack_summary:
            filename = frame.filename
            lineno = frame.lineno
            func_name = frame.name

            # Determine if this is user or library code
            code_type = "[USER]" if is_user_code(filename) else "[LIB]"
            report.append(f"\n{code_type} File: {filename}")
            report.append(f"       Line {lineno}, in {func_name}()")

            # Only show extended source context for USER code
            if is_user_code(filename) and lineno is not None:
                context = get_file_context(filename, lineno)
                report.append("       Context:")
                # Indent the context lines
                for context_line in context.split("\n"):
                    report.append(f"         {context_line}")
            else:
                report.append("         [Library Code - Context Hidden]")

    # Include full content of the main user file
    user_main_file = _find_user_main_file(exc_tb)
    if user_main_file:
        report.append("\n" + "=" * 60)
        report.append("FULL USER FILE CONTENT")
        report.append("=" * 60)
        report.append(f"File: {user_main_file}")
        report.append("-" * 60)
        report.append(get_full_file_content(user_main_file))

    # Include Runner YAML dumps
    runner_dumps = _get_runner_yaml_dumps()
    if runner_dumps:
        report.append("\n" + "=" * 60)
        report.append("RUNNER YAML CONFIGURATIONS")
        report.append("=" * 60)
        for display_name, yaml_content in runner_dumps:
            report.append(f"\n--- Runner: {display_name} ---")
            report.append(yaml_content)

    report.append("\n" + "=" * 60)
    report.append("END OF CRASH REPORT")
    report.append("=" * 60)

    return "\n".join(report)


def custom_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """
    Custom exception hook that generates crash reports.

    This replaces the default sys.excepthook to provide enhanced
    crash reporting with source context for user code.

    Args:
        exc_type: The exception type.
        exc_value: The exception instance.
        exc_tb: The traceback object.
    """
    # 1. Run pre-crash command
    try:
        pre_crash_command()
    except Exception as e:
        print(f">> Warning: pre-crash command failed: {e}", file=sys.stderr)

    # 2. Generate the crash report
    report_text = generate_crash_report(exc_type, exc_value, exc_tb)

    # 3. Determine crash report path
    crash_report_path = config.CRASH_REPORT_PATH

    # 4. Save to file
    try:
        with open(crash_report_path, "w") as f:
            f.write(report_text)
        file_saved = True
    except Exception as e:
        print(f"\n[!] Could not save crash report: {e}", file=sys.stderr)
        file_saved = False

    # 5. Print the standard Python traceback so the user sees the familiar format
    print(file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)

    if file_saved:
        report_path = Path(crash_report_path).resolve()
        print(f"\n[!] A crash report has been generated at '{report_path}'.", file=sys.stderr)
        print(
            "    Please include this file if you want to be assisted at support@octopize.io.",
            file=sys.stderr,
        )


# Store the original excepthook
_original_excepthook = sys.excepthook
_hook_installed = False


def install_hook() -> None:
    """
    Install the custom exception hook.

    This replaces sys.excepthook with our custom handler.
    Safe to call multiple times - will only install once.
    """
    global _hook_installed
    if not _hook_installed:
        sys.excepthook = custom_excepthook
        _hook_installed = True


def uninstall_hook() -> None:
    """
    Restore the original exception hook.

    This restores the original sys.excepthook behavior.
    """
    global _hook_installed
    sys.excepthook = _original_excepthook
    _hook_installed = False


def is_hook_installed() -> bool:
    """Check if the custom exception hook is currently installed."""
    return _hook_installed


# --- Auto-install the hook when this module is imported ---
install_hook()
