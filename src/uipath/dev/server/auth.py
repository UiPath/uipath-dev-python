"""Interactive OAuth authentication service for the dev server.

Implements the same PKCE-based authorization code flow as the Python SDK's
``uipath auth`` CLI command.  A temporary callback server is spun up on one of
the registered redirect-URI ports (8104, 8055, 42042) to receive the token from
the browser.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import http.server
import json
import logging
import os
import socketserver
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CLIENT_ID = "36dea5b8-e8bb-423d-8e7b-c808df8f1c00"
SCOPES = (
    "offline_access ProcessMining OrchestratorApiUserAccess StudioWebBackend "
    "IdentityServerApi ConnectionService DataService DocumentUnderstanding "
    "Du.Digitization.Api Du.Classification.Api Du.Extraction.Api "
    "Du.Validation.Api EnterpriseContextService Directory JamJamApi "
    "LLMGateway LLMOps OMS RCS.FolderAuthorization TM.Projects "
    "TM.TestCases TM.Requirements TM.TestSets AutomationSolutions"
)
CANDIDATE_PORTS = [8104, 8055, 42042]

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def _generate_state() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


def _parse_jwt_payload(token: str) -> dict[str, Any]:
    """Decode the payload section of a JWT (no signature verification)."""
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


# ---------------------------------------------------------------------------
# Port finder
# ---------------------------------------------------------------------------


def _try_bind_server(
    candidates: list[int], handler_class: type
) -> socketserver.TCPServer | None:
    """Try to bind a TCPServer on the first available candidate port."""
    socketserver.TCPServer.allow_reuse_address = True
    for port in candidates:
        try:
            httpd = socketserver.TCPServer(("127.0.0.1", port), handler_class)
            return httpd
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# Auth state
# ---------------------------------------------------------------------------


@dataclass
class AuthState:
    """Mutable state for the in-progress or completed OAuth flow."""

    status: str = "unauthenticated"  # unauthenticated | pending | needs_tenant | authenticated | expired
    environment: str = "cloud"
    token_data: dict[str, Any] = field(default_factory=dict)
    tenants: list[dict[str, str]] = field(default_factory=list)
    organization: dict[str, str] = field(default_factory=dict)
    uipath_url: str | None = None
    # Remembered from last session for seamless re-auth
    _last_tenant: str | None = None
    _last_org: dict[str, str] = field(default_factory=dict)
    _last_environment: str | None = None
    # Callback invoked after successful authentication
    _on_authenticated: Callable[[], None] | None = None
    # internal
    _code_verifier: str | None = None
    _state: str | None = None
    _port: int | None = None
    _callback_server: _CallbackServer | None = None
    _token_event: asyncio.Event | None = None
    _loop: asyncio.AbstractEventLoop | None = None
    _wait_task: asyncio.Task[None] | None = None


_auth = AuthState()


def get_auth_state() -> AuthState:
    """Return the module-level auth state singleton."""
    return _auth


def reset_auth_state() -> None:
    """Reset the auth state to its initial (unauthenticated) values.

    Preserves registered callbacks (e.g. ``_on_authenticated``).
    """
    _auth.status = "unauthenticated"
    _auth.environment = "cloud"
    _auth.token_data = {}
    _auth.tenants = []
    _auth.organization = {}
    _auth.uipath_url = None
    _auth._last_tenant = None
    _auth._last_org = {}
    _auth._last_environment = None
    _auth._code_verifier = None
    _auth._state = None
    _auth._port = None
    _auth._callback_server = None
    if _auth._wait_task and not _auth._wait_task.done():
        _auth._wait_task.cancel()
    _auth._wait_task = None
    if _auth._token_event:
        _auth._token_event.set()
    _auth._token_event = None
    _auth._loop = None


# ---------------------------------------------------------------------------
# Callback HTML (adapted from SDK index.html)
# ---------------------------------------------------------------------------

_CALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UiPath CLI Authentication</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background-color: rgb(241, 246, 248);
            color: #24292e;
            line-height: 1.5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            background-color: #ffffff;
            border-bottom: 1px solid #e1e4e8;
            padding: 16px 0;
        }

        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 16px;
            display: flex;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 32px 0;
            font-size: 20px;
            font-weight: 600;
            color: #24292e;
            text-decoration: none;
        }

        .logo-icon {
            width: 120px;
            height: 40px;
            margin-right: 12px;
        }

        .container {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px 16px;
        }

        .auth-card {
            background: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 32px;
            max-width: 440px;
            width: 100%;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24);
        }

        .auth-header {
            text-align: center;
            margin-bottom: 24px;
        }

        .auth-title {
            font-size: 24px;
            font-weight: 600;
            color: #24292e;
            margin-bottom: 8px;
        }

        .auth-subtitle {
            font-size: 16px;
            color: #586069;
        }

        .status-section {
            margin: 24px 0;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 16px;
        }

        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid #e1e4e8;
            border-top: 3px solid #fa4616;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            display: none;
        }

        @keyframes spin {
            0% {
                transform: rotate(0deg);
            }

            100% {
                transform: rotate(360deg);
            }
        }

        .success-check {
            width: 48px;
            height: 48px;
            background-color: #28a745;
            border-radius: 50%;
            display: none;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
            font-weight: bold;
        }

        .error-x {
            width: 48px;
            height: 48px;
            background-color: #d73a49;
            border-radius: 50%;
            display: none;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            font-weight: bold;
        }

        .status-message {
            text-align: center;
            font-size: 16px;
            color: #586069;
            margin-bottom: 16px;
        }

        .status-message.success {
            color: #28a745;
        }

        .status-message.error {
            color: #d73a49;
        }

        .progress-container {
            margin: 16px 0;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: #e1e4e8;
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background-color: #fa4616;
            border-radius: 4px;
            width: 0%;
            transition: width 0.3s ease;
        }

        .info-box {
            background-color: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 16px;
            margin: 16px 0;
            font-size: 14px;
            color: #586069;
            display: none;
        }

        .info-box.show {
            display: block;
        }

        .info-box strong {
            color: #24292e;
        }

        .action-buttons {
            text-align: center;
            margin-top: 24px;
        }

        .btn {
            display: inline-block;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 500;
            line-height: 20px;
            white-space: nowrap;
            vertical-align: middle;
            cursor: pointer;
            border: 1px solid;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.15s ease-in-out;
        }

        .btn-primary {
            color: #ffffff;
            background-color: #fa4616;
            border-color: #fa4616;
        }

        .btn-primary:hover {
            background-color: #e63e14;
            border-color: #e63e14;
        }

        .btn-secondary {
            color: #24292e;
            background-color: #f6f8fa;
            border-color: #e1e4e8;
        }

        .btn-secondary:hover {
            background-color: #e1e4e8;
            border-color: #d0d7de;
        }

        .debug-section {
            margin-top: 24px;
            border-top: 1px solid #e1e4e8;
            padding-top: 16px;
        }

        .debug-toggle {
            font-size: 12px;
            color: #586069;
            background: none;
            border: none;
            cursor: pointer;
            text-decoration: underline;
        }

        .debug-toggle:hover {
            color: #24292e;
        }

        .debug-log {
            background-color: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 12px;
            margin-top: 8px;
            font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', monospace;
            font-size: 12px;
            color: #24292e;
            max-height: 200px;
            overflow-y: auto;
            white-space: pre-wrap;
            display: none;
        }

        .debug-log.show {
            display: block;
        }

        @media (max-width: 544px) {
            .auth-card {
                border: none;
                box-shadow: none;
                padding: 24px 16px;
            }

            .auth-title {
                font-size: 20px;
            }
        }

        /* Fade in animation */
        .fade-in {
            animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>

<body>


    <main class="container">
        <div class="auth-card fade-in">
            <div class="logo">
                <svg class="logo-icon" focusable="false" aria-hidden="false" role="img" viewBox="0 0 62 21" width="120"
                    height="40" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path
                        d="M10.5847 6.01996H10.2875C9.51138 6.01996 9.0293 6.49219 9.0293 7.25215V13.3657C9.0293 16.2642 8.12889 17.4465 5.92142 17.4465C3.71394 17.4465 2.81351 16.2589 2.81351 13.3474V7.25216C2.81351 6.49219 2.33141 6.01996 1.55545 6.01996H1.2581C0.482103 6.01996 0 6.49219 0 7.25216V13.3657C0 17.7812 1.9923 20.02 5.92142 20.02C9.85054 20.02 11.8427 17.7812 11.8427 13.3657V7.25216C11.8427 6.49219 11.3606 6.01996 10.5847 6.01996Z"
                        fill="#000000"></path>
                    <path
                        d="M15.3983 9.7298H15.152C14.3567 9.7298 13.8628 10.2204 13.8628 11.0098V18.74C13.8628 19.5294 14.3567 20.02 15.152 20.02H15.3983C16.1934 20.02 16.6874 19.5294 16.6874 18.74V11.0098C16.6874 10.2203 16.1934 9.7298 15.3983 9.7298Z"
                        fill="#fa4616"></path>
                    <path
                        d="M18.8096 4.9445C17.0123 4.66045 15.594 3.26496 15.3053 1.49653C15.2999 1.46315 15.2559 1.46315 15.2504 1.49653C14.9618 3.26496 13.5435 4.66045 11.7462 4.9445C11.7122 4.94985 11.7122 4.99314 11.7462 4.99849C13.5435 5.28248 14.9618 6.67803 15.2504 8.44646C15.2559 8.47984 15.2999 8.47984 15.3053 8.44646C15.594 6.67803 17.0123 5.28248 18.8096 4.99849C18.8435 4.99314 18.8435 4.94985 18.8096 4.9445ZM17.0437 4.98499C16.1451 5.12699 15.4359 5.82476 15.2916 6.70898C15.2889 6.72567 15.2669 6.72567 15.2642 6.70898C15.1198 5.82476 14.4107 5.12699 13.512 4.98499C13.495 4.98231 13.495 4.96067 13.512 4.958C14.4107 4.81597 15.1198 4.11822 15.2642 3.23401C15.2669 3.21732 15.2889 3.21732 15.2916 3.23401C15.4359 4.11822 16.1451 4.81597 17.0437 4.958C17.0607 4.96067 17.0607 4.98231 17.0437 4.98499Z"
                        fill="#fa4616"></path>
                    <path
                        d="M19.8865 2.18349C18.9878 2.32548 18.2787 3.02325 18.1343 3.90747C18.1316 3.92416 18.1096 3.92416 18.1069 3.90747C17.9626 3.02325 17.2534 2.32548 16.3548 2.18349C16.3378 2.18081 16.3378 2.15917 16.3548 2.15649C17.2534 2.01447 17.9626 1.31672 18.1069 0.432502C18.1096 0.41581 18.1316 0.41581 18.1343 0.432502C18.2787 1.31672 18.9878 2.01446 19.8865 2.15649C19.9035 2.15917 19.9035 2.18081 19.8865 2.18349Z"
                        fill="#fa4616"></path>
                    <path
                        d="M22.8632 6.01996H20.1216C19.3373 6.01996 18.8501 6.49722 18.8501 7.26531V18.7746C18.8501 19.5427 19.3374 20.02 20.1216 20.02H20.4222C21.2064 20.02 21.6937 19.5427 21.6937 18.7746V16.0502H22.8819C27.6395 16.0502 29.5801 14.5973 29.5801 11.0351C29.5801 7.47291 27.6341 6.01996 22.8632 6.01996ZM26.6991 10.9983C26.6991 12.8309 25.8116 13.4493 23.1823 13.4493H21.6937V8.5657H23.1823C25.8116 8.5657 26.6991 9.17948 26.6991 10.9983Z"
                        fill="#000000"></path>
                    <path
                        d="M40.1401 8.6104H39.9147C39.1305 8.6104 38.6433 9.08767 38.6433 9.85576V9.85735C37.8378 8.94386 36.5902 8.4082 35.1642 8.4082C33.7113 8.4082 32.3975 8.93097 31.4648 9.88042C30.4488 10.9143 29.9119 12.4066 29.9119 14.1957C29.9119 15.9926 30.452 17.4935 31.4739 18.536C32.4119 19.4929 33.7291 20.02 35.1829 20.02C36.5819 20.02 37.8388 19.4777 38.6443 18.5774C38.6443 18.5783 38.6444 18.8369 38.6444 18.8378C38.6705 19.5689 39.1522 20.02 39.9147 20.02H40.1401C40.9244 20.02 41.4117 19.5429 41.4117 18.7748V9.85576C41.4117 9.08768 40.9244 8.6104 40.1401 8.6104ZM38.6996 14.1957C38.6996 16.2973 37.5536 17.6029 35.7087 17.6029C33.8407 17.6029 32.6803 16.2973 32.6803 14.1957C32.6803 12.1053 33.8263 10.8068 35.6712 10.8068C37.5108 10.8068 38.6996 12.1371 38.6996 14.1957Z"
                        fill="#000000"></path>
                    <path
                        d="M56.5101 8.41922C55.0376 8.41922 53.9872 8.99357 53.3294 9.7174V7.2661C53.3294 6.49753 52.8419 6.01996 52.0571 6.01996H51.8317C51.0469 6.01996 50.5593 6.49753 50.5593 7.2661V18.7738C50.5593 19.5424 51.0469 20.02 51.8317 20.02H52.0571C52.8419 20.02 53.3294 19.5424 53.3294 18.7738V14.1551C53.3294 11.1982 54.7693 10.8562 55.8525 10.8562C57.6713 10.8562 58.4131 11.7428 58.4131 13.916V18.7738C58.4131 19.5424 58.9007 20.02 59.6855 20.02H59.911C60.6957 20.02 61.1832 19.5424 61.1832 18.7738V13.7503C61.1832 10.163 59.6547 8.41922 56.5101 8.41922Z"
                        fill="#000000"></path>
                    <path
                        d="M49.7629 18.6115C49.724 18.2411 49.4976 17.7119 48.4196 17.7119C47.1449 17.7119 46.5383 17.3228 46.5383 15.112V10.8563H48.4383C49.2218 10.8563 49.7086 10.421 49.7086 9.72061C49.7086 9.03146 49.2218 8.60325 48.4383 8.60325H46.5406V7.2661C46.5406 6.49753 46.0501 6.01996 45.2606 6.01996H45.0338C44.2443 6.01996 43.7538 6.49753 43.7538 7.2661V8.60325H43.317C42.626 8.60325 42.1968 9.03147 42.1968 9.72061C42.1968 10.421 42.6836 10.8563 43.4671 10.8563H43.7538V15.3513C43.7538 18.6237 45.0538 20.02 48.1007 20.02C48.1056 20.02 48.1106 20.0198 48.1155 20.0197C48.2927 20.0195 48.4824 20.0168 48.6757 19.9999C49.0598 19.9643 49.3503 19.8316 49.5392 19.6053C49.7274 19.38 49.8027 18.9843 49.7629 18.6115Z"
                        fill="#000000"></path>
                </svg>
            </div>

            <div class="auth-header">
                <h1 class="auth-title" id="main-title">Authenticate CLI</h1>
                <p class="auth-subtitle" id="subtitle">Completing authentication flow...</p>
            </div>

            <div class="status-section">
                <div class="status-indicator">
                    <div class="spinner" id="spinner"></div>
                    <div class="success-check" id="success-check">&check;</div>
                    <div class="error-x" id="error-x">&times;</div>
                </div>

                <div class="progress-container" id="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                </div>

                <div class="status-message" id="status-message">
                    Processing authentication request...
                </div>
            </div>

            <div class="info-box" id="info-box">
                <strong>Authenticating...</strong><br>
                Securely exchanging authorization code for access tokens.
            </div>

            <div class="debug-section">
                <button class="debug-toggle" onclick="toggleDebug()">Show debug info</button>
                <div class="debug-log" id="debug-log"></div>
            </div>
        </div>
    </main>

    <script>
        const baseUrl = '__REDIRECT_URI__'.replace('/oidc/login', '');
        const logs = [];
        let debugMode = false;

        // UI Helper Functions
        function showSpinner() {
            document.getElementById('spinner').style.display = 'block';
            document.getElementById('progress-container').style.display = 'block';
            updateProgress(20);
        }

        function hideSpinner() {
            document.getElementById('spinner').style.display = 'none';
        }

        function showSuccess() {
            hideSpinner();
            document.getElementById('success-check').style.display = 'flex';
            document.getElementById('progress-container').style.display = 'none';
        }

        function showError() {
            hideSpinner();
            document.getElementById('error-x').style.display = 'flex';
            document.getElementById('progress-container').style.display = 'none';
        }

        function updateProgress(percent) {
            document.getElementById('progress-fill').style.width = percent + '%';
        }

        function updateStatus(message, type) {
            type = type || 'normal';
            const statusEl = document.getElementById('status-message');
            statusEl.textContent = message;
            statusEl.className = 'status-message ' + type;
        }

        function showInfoBox(content) {
            const infoBox = document.getElementById('info-box');
            infoBox.innerHTML = content;
            infoBox.classList.add('show');
        }

        function hideInfoBox() {
            document.getElementById('info-box').classList.remove('show');
        }

        function toggleDebug() {
            debugMode = !debugMode;
            const logEl = document.getElementById('debug-log');
            const toggleBtn = document.querySelector('.debug-toggle');

            if (debugMode) {
                logEl.textContent = JSON.stringify(logs, null, 2);
                logEl.classList.add('show');
                toggleBtn.textContent = 'Hide debug info';
            } else {
                logEl.classList.remove('show');
                toggleBtn.textContent = 'Show debug info';
            }
        }

        function closeWindow() {
            try {
                window.open('', '_self', '');
                window.close();
            } catch (e) {
                window.location.href = 'about:blank';
            }
        }

        // Parse URL query parameters
        function getQueryParams() {
            const params = {};
            const queryString = window.location.search;
            const urlParams = new URLSearchParams(queryString);

            for (const [key, value] of urlParams.entries()) {
                params[key] = value;
            }
            return params;
        }

        // Exchange authorization code for tokens
        async function exchangeCodeForToken(code, codeVerifier) {
            try {
                updateProgress(50);
                updateStatus('Exchanging authorization code...');

                const formData = new URLSearchParams();
                formData.append('grant_type', 'authorization_code');
                formData.append('code', code);
                formData.append('redirect_uri', '__REDIRECT_URI__');
                formData.append('client_id', '__CLIENT_ID__');
                formData.append('code_verifier', codeVerifier);

                const domainOrUrl = '__DOMAIN__';
                let tokenUrl;
                if (domainOrUrl.startsWith('http')) {
                    tokenUrl = domainOrUrl + '/identity_/connect/token';
                } else {
                    tokenUrl = 'https://' + domainOrUrl + '.uipath.com/identity_/connect/token';
                }

                const response = await fetch(tokenUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: formData
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('Token request failed: ' + response.status + ' ' + response.statusText + ' - ' + errorText);
                }

                const tokenData = await response.json();
                updateProgress(80);
                return tokenData;
            } catch (error) {
                console.error('Error exchanging code for token:', error);
                logs.push({
                    timestamp: new Date().toISOString(),
                    message: 'Error exchanging code for token:',
                    error: error.message
                });
                throw error;
            }
        }

        async function delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }

        // Main authentication handler
        async function handleAuthentication() {
            const params = getQueryParams();
            showSpinner();

            logs.push({
                timestamp: new Date().toISOString(),
                message: 'Authentication started',
                params: params
            });

            try {
                if (params.code && params.state) {
                    updateStatus('Validating authorization...');
                    await delay(300);

                    const codeVerifier = "__CODE_VERIFIER__";
                    const state = "__STATE__";

                    if (!codeVerifier) {
                        throw new Error('Code verifier not found');
                    }

                    if (!params.state || params.state != state) {
                        throw new Error('Invalid state parameter');
                    }

                    updateProgress(30);
                    const tokenData = await exchangeCodeForToken(params.code, codeVerifier);

                    updateStatus('Sending credentials to Dev Server...');
                    updateProgress(90);

                    await fetch(baseUrl + '/set_token/' + state, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(tokenData)
                    });

                    updateProgress(100);
                    await delay(300);

                    // Success state
                    showSuccess();
                    document.getElementById('main-title').textContent = 'Authentication Complete';
                    document.getElementById('subtitle').textContent = 'UiPath Developer Console authenticated successfully';
                    updateStatus('You can close this tab', 'success');

                    // Auto-close after 3 seconds
                    setTimeout(closeWindow, 3000);

                    window.history.replaceState({}, document.title, window.location.pathname);

                } else if (params.error) {
                    throw new Error('OAuth error: ' + params.error + ' - ' + (params.error_description || 'Unknown error'));
                } else {
                    updateStatus('Waiting for authentication...');
                    showInfoBox('<strong>Waiting...</strong><br>Complete the authentication process to continue.');
                }
            } catch (error) {
                console.error('Authentication error:', error);
                logs.push({
                    timestamp: new Date().toISOString(),
                    message: 'Authentication failed',
                    error: error.message
                });

                showError();
                document.getElementById('main-title').textContent = 'Authentication Failed';
                document.getElementById('subtitle').textContent = 'Unable to complete authentication';
                updateStatus(error.message, 'error');

                const errBox = document.getElementById('info-box');
                errBox.textContent = '';
                const strong = document.createElement('strong');
                strong.textContent = 'Error: ';
                errBox.appendChild(strong);
                errBox.appendChild(document.createTextNode(error.message));
                errBox.appendChild(document.createElement('br'));
                errBox.appendChild(document.createElement('br'));
                errBox.appendChild(document.createTextNode('Please try signing in again.'));
                errBox.classList.add('show');
            }
        }

        // Start when page loads
        document.addEventListener('DOMContentLoaded', handleAuthentication);
    </script>
</body>

</html>
"""

# ---------------------------------------------------------------------------
# Callback HTTP server
# ---------------------------------------------------------------------------


def _make_handler(
    html: str,
    port: int,
    csrf_state: str,
    token_callback: Any,
) -> type:
    """Build the HTTP request handler class with closures over request params."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            content = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self._cors()
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:
            if self.path == f"/set_token/{csrf_state}":
                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, ValueError):
                    self.send_error(400, "Malformed JSON")
                    return
                self.send_response(200)
                self._cors()
                self.end_headers()
                self.wfile.write(b"OK")
                # Small delay so the browser gets the response before we shut down
                time.sleep(0.5)
                token_callback(body)
            else:
                self.send_error(404)

        def do_OPTIONS(self) -> None:
            self.send_response(200)
            self._cors()
            self.end_headers()

        def _cors(self) -> None:
            origin = f"http://localhost:{port}"
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    return Handler


class _CallbackServer:
    """Temporary HTTP server that receives the OAuth token from the browser."""

    def __init__(self, httpd: socketserver.TCPServer) -> None:
        self.httpd: socketserver.TCPServer | None = httpd
        self.port: int = httpd.server_address[1]
        self._thread: threading.Thread | None = None
        self._shutdown = False

    def start(self) -> None:
        self._shutdown = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            while not self._shutdown and self.httpd:
                self.httpd.handle_request()
        except Exception:
            pass

    def stop(self) -> None:
        self._shutdown = True
        if self.httpd:
            self.httpd.server_close()
            self.httpd = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_VALID_ENVIRONMENTS = {"cloud", "staging", "alpha"}


def build_auth_url(environment: str) -> dict[str, Any]:
    """Start the OAuth flow: generate PKCE, spin up callback server, return auth URL."""
    if environment not in _VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment '{environment}'. Must be one of: {', '.join(sorted(_VALID_ENVIRONMENTS))}"
        )

    auth = get_auth_state()

    # Stop any previous callback server and cancel any pending wait task
    if auth._callback_server:
        auth._callback_server.stop()
    if auth._wait_task and not auth._wait_task.done():
        auth._wait_task.cancel()

    verifier, challenge = _generate_pkce()
    state = _generate_state()
    domain = f"https://{environment}.uipath.com"

    # Build handler and bind server atomically (no TOCTOU race)
    # We need the port first to construct the HTML, so we do a two-step:
    # 1. Build a temporary handler, bind to get the port
    # 2. Rebuild the handler with the correct HTML, then swap
    def on_token(token_data: dict[str, Any]) -> None:
        auth.token_data = token_data
        if auth._loop and auth._token_event:
            auth._loop.call_soon_threadsafe(auth._token_event.set)

    # _make_handler needs the port for CORS, and the HTML needs the port for
    # redirect_uri. We build a placeholder handler to bind, then rebuild.
    placeholder = _make_handler("", 0, state, on_token)
    httpd = _try_bind_server(CANDIDATE_PORTS, placeholder)
    if httpd is None:
        raise RuntimeError(
            f"All callback ports ({', '.join(str(p) for p in CANDIDATE_PORTS)}) are in use"
        )

    port = httpd.server_address[1]
    redirect_uri = f"http://localhost:{port}/oidc/login"

    html = (
        _CALLBACK_HTML.replace("__STATE__", state)
        .replace("__CODE_VERIFIER__", verifier)
        .replace("__REDIRECT_URI__", redirect_uri)
        .replace("__CLIENT_ID__", CLIENT_ID)
        .replace("__DOMAIN__", domain)
    )

    # Replace the handler with the real one containing the correct HTML/port
    httpd.RequestHandlerClass = _make_handler(html, port, state, on_token)

    query = urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{domain}/identity_/connect/authorize?{query}"

    # Store state for later (preserve remembered tenant info for re-auth)
    auth.status = "pending"
    auth.environment = environment
    auth._code_verifier = verifier
    auth._state = state
    auth._port = port

    # Set up asyncio event for signalling
    loop = asyncio.get_running_loop()
    auth._token_event = asyncio.Event()
    auth._loop = loop

    server = _CallbackServer(httpd)
    server.start()
    auth._callback_server = server

    auth._wait_task = asyncio.ensure_future(_wait_for_token(auth))

    return {"auth_url": auth_url, "status": "pending"}


async def _wait_for_token(auth: AuthState) -> None:
    """Wait for the callback server to receive the token, then resolve tenants."""
    try:
        if auth._token_event:
            await asyncio.wait_for(auth._token_event.wait(), timeout=300)
    except asyncio.TimeoutError:
        logger.warning("OAuth flow timed out after 5 minutes")
        auth.status = "unauthenticated"
        return
    finally:
        if auth._callback_server:
            auth._callback_server.stop()
            auth._callback_server = None

    if not auth.token_data:
        auth.status = "unauthenticated"
        return

    # Resolve tenants
    try:
        domain = f"https://{auth.environment}.uipath.com"
        access_token = auth.token_data.get("access_token", "")
        claims = _parse_jwt_payload(access_token)
        prt_id = claims.get("prt_id", "")

        url = f"{domain}/{prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            data = resp.json()

        auth.tenants = data.get("tenants", [])
        auth.organization = data.get("organization", {})

        tenant_names = [t["name"] for t in auth.tenants]

        if auth._last_tenant and auth._last_tenant in tenant_names:
            # Re-auth: auto-select the previously used tenant
            _finalize_tenant(auth, auth._last_tenant)
        elif len(auth.tenants) == 1:
            # Auto-select single tenant
            _finalize_tenant(auth, auth.tenants[0]["name"])
        else:
            auth.status = "needs_tenant"
    except Exception:
        logger.exception("Failed to resolve tenants")
        auth.status = "unauthenticated"


def select_tenant(tenant_name: str) -> dict[str, Any]:
    """Select a tenant and finalize authentication."""
    auth = get_auth_state()
    tenant = next((t for t in auth.tenants if t["name"] == tenant_name), None)
    if not tenant:
        raise ValueError(f"Tenant '{tenant_name}' not found")
    _finalize_tenant(auth, tenant_name)
    return {"status": "authenticated", "uipath_url": auth.uipath_url}


def _update_env_file(env_contents: dict[str, str]) -> None:
    """Merge *env_contents* into the CWD ``.env`` file.

    New keys take priority; existing keys not in *env_contents* are preserved.
    Comments and blank lines are kept as-is.
    """
    env_path = Path.cwd() / ".env"
    lines: list[str] = []
    seen_keys: set[str] = set()

    if env_path.exists():
        with open(env_path) as f:
            for raw_line in f:
                stripped = raw_line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    # Preserve comments and blank lines
                    lines.append(raw_line)
                    continue
                key = stripped.split("=", 1)[0]
                if key in env_contents:
                    lines.append(f"{key}={env_contents[key]}\n")
                else:
                    lines.append(raw_line)
                seen_keys.add(key)

    # Append new keys that weren't already in the file
    for key, value in env_contents.items():
        if key not in seen_keys:
            lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)


def _finalize_tenant(auth: AuthState, tenant_name: str) -> None:
    """Write .env and os.environ with the resolved credentials."""
    org_name = auth.organization.get("name", "")
    org_id = auth.organization.get("id", "")
    domain = f"https://{auth.environment}.uipath.com"
    uipath_url = f"{domain}/{org_name}/{tenant_name}"
    access_token = auth.token_data.get("access_token", "")

    # Resolve tenant ID from the tenants list
    tenant = next((t for t in auth.tenants if t["name"] == tenant_name), None)
    tenant_id = tenant["id"] if tenant else ""

    auth.uipath_url = uipath_url
    auth.status = "authenticated"

    # Remember for seamless re-auth after expiry
    auth._last_tenant = tenant_name
    auth._last_org = dict(auth.organization)
    auth._last_environment = auth.environment

    # Write .env using the same approach as `uipath auth`
    _update_env_file(
        {
            "UIPATH_ACCESS_TOKEN": access_token,
            "UIPATH_URL": uipath_url,
            "UIPATH_TENANT_ID": tenant_id,
            "UIPATH_ORGANIZATION_ID": org_id,
        }
    )

    # Reload .env into os.environ (same as CLI root: cwd + override)
    load_dotenv(
        dotenv_path=os.path.join(os.getcwd(), ".env"),
        override=True,
    )

    if auth._on_authenticated:
        try:
            auth._on_authenticated()
        except Exception:
            logger.exception("Error in post-authentication callback")


def logout() -> None:
    """Clear auth state and env vars."""
    auth = get_auth_state()
    if auth._callback_server:
        auth._callback_server.stop()

    os.environ.pop("UIPATH_ACCESS_TOKEN", None)
    os.environ.pop("UIPATH_URL", None)
    os.environ.pop("UIPATH_TENANT_ID", None)
    os.environ.pop("UIPATH_ORGANIZATION_ID", None)

    reset_auth_state()


def _check_token_expiry(auth: AuthState) -> None:
    """Flip status to 'expired' if the current token has expired."""
    if auth.status != "authenticated":
        return
    access_token = auth.token_data.get("access_token", "")
    if not access_token:
        return
    try:
        claims = _parse_jwt_payload(access_token)
        exp = claims.get("exp")
        if exp is not None and float(exp) < time.time():
            auth.status = "expired"
    except Exception:
        pass


def get_status() -> dict[str, Any]:
    """Return current auth status for the frontend."""
    auth = get_auth_state()

    _check_token_expiry(auth)

    result: dict[str, Any] = {"status": auth.status}

    if auth.status == "needs_tenant":
        result["tenants"] = [t["name"] for t in auth.tenants]

    if auth.status in ("authenticated", "expired"):
        result["uipath_url"] = auth.uipath_url

    return result


def restore_session() -> None:
    """Check env/.env for existing credentials and restore auth state if valid."""
    auth = get_auth_state()
    if auth.status != "unauthenticated":
        return

    # Try os.environ first, then .env file
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN", "")
    uipath_url = os.environ.get("UIPATH_URL", "")

    if not access_token or not uipath_url:
        # Try reading from .env
        env_path = Path.cwd() / ".env"
        if env_path.exists():
            env_vars: dict[str, str] = {}
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
            access_token = access_token or env_vars.get("UIPATH_ACCESS_TOKEN", "")
            uipath_url = uipath_url or env_vars.get("UIPATH_URL", "")

    if not access_token or not uipath_url:
        return

    # Check token expiry
    try:
        claims = _parse_jwt_payload(access_token)
        exp = claims.get("exp")
        if exp is not None and float(exp) < time.time():
            logger.debug("Existing token is expired, skipping restore")
            return
    except Exception:
        return

    # Token is valid — restore state
    auth.status = "authenticated"
    auth.uipath_url = uipath_url
    auth.token_data = {"access_token": access_token}

    # Ensure os.environ is populated
    os.environ["UIPATH_ACCESS_TOKEN"] = access_token
    os.environ["UIPATH_URL"] = uipath_url
