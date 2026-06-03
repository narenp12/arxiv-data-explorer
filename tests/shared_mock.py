import sys
from unittest.mock import MagicMock


class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"session_state has no attribute {name!r}")

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            dict.__delitem__(self, name)
        except KeyError:
            raise AttributeError(name)


class CacheMock:
    """Mocks both @st.cache_data / @st.cache_resource decorators and .clear()."""

    def __call__(self, f=None, **kw):
        return f if callable(f) else (lambda g: g)

    def clear(self):
        pass


def install_streamlit_mock():
    _st_mock = MagicMock()
    _st_mock.cache_data = CacheMock()
    _st_mock.cache_resource = CacheMock()
    _st_mock.session_state = MockSessionState()
    _st_mock.spinner = lambda msg=None: MagicMock().__enter__.return_value
    sys.modules["streamlit"] = _st_mock
    return _st_mock
