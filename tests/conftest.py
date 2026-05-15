"""
Shared test configuration.

Installs adsk/server mocks before any test module is collected,
so both test_document_tracker and test_session_manager can coexist
in the same pytest process.
"""

from tests.fixtures.mock_adsk import setup

# Install mocks at collection time — before any addin code is imported
setup()
