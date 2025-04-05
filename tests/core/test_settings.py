# Inside tests/core/test_settings.py

import importlib
import src.core.settings as settings
from pathlib import Path # Make sure Path is imported

# ... other imports ...

def test_config_missing(monkeypatch, tmp_path):
    """
    Test the behavior when the configuration file is missing by mocking Path.exists.
    """
    # Determine the expected config file path *as calculated by settings.py*
    # We still need the original BASE_DIR calculation logic temporarily
    # Note: This assumes the test file structure relative to src/core/settings.py
    # It's often better to derive BASE_DIR within the test if possible or mock Path(__file__)
    # For simplicity, let's assume settings.BASE_DIR points correctly initially.
    real_base_dir = settings.BASE_DIR # Get the normally calculated BASE_DIR
    expected_config_path = real_base_dir / 'config.ini'

    # Store original 'exists' method
    original_exists = Path.exists

    # --- Crucial Change: Mock Path.exists ---
    def mock_exists(path_instance):
        # If the path being checked is the config file path, return False
        if path_instance == expected_config_path:
            print(f"Mocking exists for {path_instance}: returning False") # Debug print
            return False
        # Otherwise, delegate to the original method for other paths
        print(f"Mocking exists for {path_instance}: calling original") # Debug print
        return original_exists(path_instance)

    monkeypatch.setattr(Path, "exists", mock_exists)
    # -----------------------------------------

    # No need to patch BASE_DIR or CONFIG_FILE_PATH anymore
    # No need to set settings.config = None here

    try:
        # Reload the settings module; now Path.exists will be mocked during reload
        importlib.reload(settings)

        # Assert that the settings module correctly identified the config as missing
        assert settings.config is None
        assert settings.config_loaded is False # Also check the flag

    finally:
        # Restore original Path.exists - monkeypatch usually does this,
        # but explicit restore can be clearer or needed if not using fixture properly.
        # monkeypatch fixture handles teardown automatically, so this might be redundant
        # monkeypatch.undo() # Or let the fixture handle it
        pass # Let monkeypatch handle cleanup