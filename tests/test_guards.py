"""The guards in conftest.py must really stop an unmocked Gemini/network call."""

import socket

import pytest

import ml_models.ai_logic as ai_logic
from app.services import policy_impact, response_service


@pytest.mark.parametrize("module", [ai_logic, policy_impact, response_service])
def test_unpatched_ask_gemini_raises_in_every_module(module):
    with pytest.raises(AssertionError, match="without being mocked"):
        module.ask_gemini("hello")


def test_real_network_is_blocked():
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.getaddrinfo("example.com", 443)
