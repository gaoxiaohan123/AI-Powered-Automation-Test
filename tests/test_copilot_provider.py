import asyncio
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from common import copilot_provider


class CopilotProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            'api_key': 'test-long-lived-pat',
            'chat_url': 'GitHub Copilot SDK runtime',
            'model': 'test-model',
            'timeout_sec': 5,
            'working_directory': '.',
        }

    @patch('common.copilot_provider._run_sdk_completion', new_callable=AsyncMock)
    def test_wraps_sdk_content_as_openai_completion(self, mock_completion):
        mock_completion.return_value = 'done'

        response = copilot_provider.chat_completion({
            'model': 'test-model',
            'messages': [
                {'role': 'system', 'content': 'Be concise.'},
                {'role': 'user', 'content': 'Analyze the failure.'},
            ],
        }, self.config)

        self.assertEqual('done', response['choices'][0]['message']['content'])
        prompt, config = mock_completion.call_args.args
        self.assertIn('System instructions:\nBe concise.', prompt)
        self.assertIn('User request:\nAnalyze the failure.', prompt)
        self.assertEqual('test-model', config['model'])

    def test_rejects_empty_prompt(self):
        with self.assertRaises(copilot_provider.CopilotProviderError):
            copilot_provider.chat_completion({'messages': []}, self.config)

    def test_collector_keeps_longest_assistant_message(self):
        code = 'import os\n\nclass Test_X(unittest.TestCase):\n    pass'
        session = _FakeSession([
            SimpleNamespace(data=_Assistant('Sure, generating the script...', 'm1')),
            SimpleNamespace(data=_Assistant(code, 'm2')),
            SimpleNamespace(data=_Assistant('Done!', 'm3')),
            SimpleNamespace(data=_Idle()),
        ])

        content = asyncio.run(copilot_provider._send_and_collect_content(
            session, 'prompt', 5, (_Assistant, _Idle, _Error),
        ))

        self.assertEqual(code, content)

    def test_session_is_created_without_any_tools(self):
        source = inspect.getsource(copilot_provider._run_sdk_completion)

        self.assertIn('available_tools=[]', source)


class _Assistant:
    def __init__(self, content, message_id):
        self.content = content
        self.message_id = message_id


class _Idle:
    pass


class _Error:
    def __init__(self, message=''):
        self.message = message


class _FakeSession:
    def __init__(self, events):
        self._events = events
        self._handler = None

    def on(self, handler):
        self._handler = handler
        return lambda: None

    async def send(self, prompt):
        for event in self._events:
            self._handler(event)

    async def abort(self):
        pass


if __name__ == '__main__':
    unittest.main()