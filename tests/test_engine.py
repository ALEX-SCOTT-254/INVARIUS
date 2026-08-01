from backend.app.core.engine import InvariusEngine


def test_engine_version():
    engine = InvariusEngine()
    assert engine.VERSION == "0.1.0"
