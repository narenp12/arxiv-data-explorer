import sys
from unittest.mock import MagicMock


class MockSessionState(dict):
    def __getattr__(self, name):
        return self[name]
    def __setattr__(self, name, value):
        self[name] = value


def install_streamlit_mock():
    _st_mock = MagicMock()
    _st_mock.cache_data = lambda f=None, **kw: f if callable(f) else (lambda g: g)
    _st_mock.cache_resource = lambda f=None, **kw: f if callable(f) else (lambda g: g)
    _st_mock.session_state = MockSessionState()
    _st_mock.spinner = lambda msg=None: MagicMock().__enter__.return_value
    sys.modules["streamlit"] = _st_mock
    return _st_mock
