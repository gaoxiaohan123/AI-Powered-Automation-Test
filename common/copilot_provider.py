# -*- coding: utf-8 -*-
import asyncio
import os


class CopilotProviderError(RuntimeError):
    pass


def copilot_config():
    token = (
        os.environ.get('GITHUB_COPILOT_TOKEN')
        or os.environ.get('COPILOT_API_KEY')
        or os.environ.get('GITHUB_TOKEN')
        or ''
    ).strip()
    timeout_raw = (os.environ.get('COPILOT_TIMEOUT_SEC') or '180').strip()
    try:
        timeout_sec = max(5, min(600, int(timeout_raw)))
    except ValueError:
        timeout_sec = 180
    return {
        'api_key': token,
        'chat_url': 'GitHub Copilot SDK runtime',
        'model': (os.environ.get('COPILOT_MODEL') or 'auto').strip() or 'auto',
        'timeout_sec': timeout_sec,
        'working_directory': os.environ.get('COPILOT_WORKING_DIRECTORY') or os.getcwd(),
    }


def _prompt_from_messages(messages):
    parts = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = message.get('content')
        if isinstance(content, list):
            content = '\n'.join(
                str(item.get('text') or '') for item in content if isinstance(item, dict)
            )
        content = str(content or '').strip()
        if not content:
            continue
        role = str(message.get('role') or 'user').strip().lower()
        prefix = 'System instructions' if role == 'system' else 'User request'
        parts.append(f'{prefix}:\n{content}')
    if not parts:
        raise CopilotProviderError('Copilot request has no prompt content')
    return '\n\n'.join(parts)


def _sdk_response_content(response):
    data = getattr(response, 'data', None)
    return str(getattr(data, 'content', '') or '').strip()


async def _send_and_collect_content(session, prompt, timeout_sec, event_types):
    assistant_message_type, idle_type, error_type = event_types
    completed = asyncio.Event()
    # The agentic runtime may stream several assistant messages (reasoning, code,
    # closing remark). Keep the longest content per message id; the generated
    # script is virtually always the longest message.
    messages = {}
    error_message = ''

    def _best_content():
        return max(messages.values(), key=len) if messages else ''

    def handle_event(event):
        nonlocal error_message
        data = getattr(event, 'data', None)
        if isinstance(data, assistant_message_type):
            content = str(getattr(data, 'content', '') or '').strip()
            if content:
                key = getattr(data, 'message_id', None) or id(data)
                if len(content) >= len(messages.get(key, '')):
                    messages[key] = content
        elif isinstance(data, error_type):
            error_message = str(getattr(data, 'message', '') or data)
            completed.set()
        elif isinstance(data, idle_type):
            completed.set()

    unsubscribe = session.on(handle_event)
    try:
        await session.send(prompt)
        try:
            await asyncio.wait_for(completed.wait(), timeout=timeout_sec)
        except TimeoutError:
            best = _best_content()
            if best:
                return best
            await session.abort()
            raise CopilotProviderError(
                f'GitHub Copilot SDK timed out after {timeout_sec}s without an assistant response'
            )
        if error_message:
            raise CopilotProviderError(f'GitHub Copilot SDK session error: {error_message}')
        return _best_content()
    finally:
        unsubscribe()


async def _run_sdk_completion(prompt, config):
    try:
        from copilot import CopilotClient
        from copilot.session import PermissionHandler
        from copilot.session_events import AssistantMessageData, SessionErrorData, SessionIdleData
    except ImportError as exc:
        raise CopilotProviderError(
            'GitHub Copilot SDK is not installed. Run: pip install github-copilot-sdk'
        ) from exc

    client = CopilotClient(
        github_token=config['api_key'] or None,
        use_logged_in_user=not bool(config['api_key']),
        working_directory=config['working_directory'],
    )
    session = None
    try:
        await client.start()
        # Empty allowlist keeps the agentic runtime from answering with file edits
        # ("I created the file") instead of returning the script as message text.
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model=config['model'],
            available_tools=[],
        )
        empty_reason = ''
        for attempt in range(2):
            content = await _send_and_collect_content(
                session,
                prompt,
                config['timeout_sec'],
                (AssistantMessageData, SessionIdleData, SessionErrorData),
            )
            if content:
                return content
            empty_reason = 'no assistant message event or an assistant message with empty content'
            if attempt == 0:
                await asyncio.sleep(0.25)
        raise CopilotProviderError(
            f'GitHub Copilot SDK returned {empty_reason} after two attempts'
        )
    finally:
        if session is not None:
            await session.disconnect()
        await client.stop()


def chat_completion(payload, config=None):
    config = config or copilot_config()
    prompt = _prompt_from_messages(payload.get('messages'))
    content = None
    for attempt in range(2):
        try:
            content = asyncio.run(_run_sdk_completion(prompt, config))
            break
        except CopilotProviderError:
            raise
        except Exception as exc:
            # Transient network read timeouts are worth one retry with a fresh client.
            if attempt == 0 and 'timed out' in str(exc).lower():
                continue
            raise CopilotProviderError(f'GitHub Copilot SDK request failed: {exc}') from exc
    return {'choices': [{'message': {'content': content}}]}