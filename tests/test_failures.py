"""Offline adapter boundary tests: rejected input and failed delivery."""
import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import requests
from adapters.base import DeliveryError
from adapters.discord import run
from adapters.telegram import TelegramAdapter
from core.bot import BotCore
from database import ProcessedMessages


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = ProcessedMessages(str(Path(temp.name) / 'test.db'))
        self.core = BotCore(self.repo)
        self.session = MagicMock()
        self.response = self.session.post.return_value.__enter__.return_value
        self.response.status_code = 200
        self.response.json.return_value = {'ok': True, 'result': {'message_id': 1}}
        self.bot = TelegramAdapter(self.core, 'dummy-token', {'123'}, self.session)
        self.update = {'update_id': 10, 'message': {'from': {'id': 123, 'is_bot': False},
                       'chat': {'id': 123, 'type': 'private'}, 'text': '2'}}

    def test_telegram_rejects_unknown_users_groups_and_bots(self):
        for field, value in [('user', 999), ('bot', True), ('chat', 'group'), ('chat', 'supergroup')]:
            update = copy.deepcopy(self.update)
            if field == 'user':
                update['message']['from']['id'] = value
            elif field == 'bot':
                update['message']['from']['is_bot'] = value
            else:
                update['message']['chat']['type'] = value
            with self.subTest(field=field, value=value), patch.object(self.core, 'handle') as handle:
                self.assertIsNone(self.bot.receive(update))
                handle.assert_not_called()
        self.session.post.assert_not_called()

    def test_telegram_http_failures_leave_message_retryable(self):
        for status in (302, 401, 403, 429, 500):
            with self.subTest(status=status):
                self.response.status_code = status
                with self.assertRaises(DeliveryError):
                    self.bot.receive(self.update)
                self.assertEqual(self.repo.state('telegram:123:123'), 'menu')
                self.assertFalse(self.repo.contains(self.repo.key('telegram:10', 'live')))
        self.response.status_code = 200
        self.bot.receive(self.update)
        self.assertEqual(self.repo.state('telegram:123:123'), 'survey_rating')
        self.assertEqual(self.session.post.call_args.kwargs['json']['chat_id'], '123')

    def test_telegram_timeout_and_connection_errors_are_sanitized(self):
        for error in (requests.Timeout('dummy-token'), requests.ConnectionError('dummy-token')):
            with self.subTest(error=type(error).__name__):
                self.session.post.side_effect = error
                with self.assertRaises(DeliveryError) as caught:
                    self.bot.receive(self.update)
                self.assertNotIn('dummy-token', str(caught.exception))
                self.assertEqual(self.repo.state('telegram:123:123'), 'menu')
                self.assertFalse(self.repo.contains(self.repo.key('telegram:10', 'live')))

    def test_telegram_invalid_response_does_not_commit(self):
        for result in ([], {'ok': False}, {'ok': True, 'result': {}}, {'ok': True, 'result': None}):
            with self.subTest(result=result):
                self.response.json.return_value = result
                with self.assertRaises(DeliveryError):
                    self.bot.receive(self.update)
                self.assertFalse(self.repo.contains(self.repo.key('telegram:10', 'live')))
        self.response.json.side_effect = ValueError('dummy-token')
        with self.assertRaisesRegex(DeliveryError, '^Telegram request failed$'):
            self.bot.receive(self.update)

    def test_telegram_polling_failure_does_not_ack_failed_update(self):
        self.bot.api = Mock(side_effect=[[self.update], DeliveryError('failure')])
        with self.assertRaises(DeliveryError):
            self.bot.run()
        self.assertEqual([c.args[0] for c in self.bot.api.call_args_list], ['getUpdates', 'sendMessage'])
        self.assertFalse(self.repo.contains(self.repo.key('telegram:10', 'live')))

    def discord_handler(self):
        client = Mock()
        handlers = {}
        def event(fn):
            handlers[fn.__name__] = fn
            return fn
        client.event = event
        sdk = MagicMock()
        sdk.Client.return_value = client
        with patch.dict('sys.modules', {'discord': sdk}):
            run(self.core, 'dummy-token', {'123'}, {'456'})
        return handlers['on_message'], sdk

    def test_discord_denied_events_never_reach_core(self):
        handler, _ = self.discord_handler()
        for user, channel, bot in [(999, 456, False), (123, 999, False), (123, 456, True)]:
            msg = NS(id=1, author=NS(id=user, bot=bot), channel=NS(id=channel, send=AsyncMock()), content='2')
            with self.subTest(user=user, channel=channel, bot=bot), patch.object(self.core, 'handle') as handle:
                asyncio.run(handler(msg))
                handle.assert_not_called()
                msg.channel.send.assert_not_awaited()

    def test_discord_send_failure_preserves_state_then_same_channel_reply(self):
        handler, sdk = self.discord_handler()
        msg = NS(id=1, author=NS(id=123, bot=False), channel=NS(id=456, send=AsyncMock()), content='2')
        msg.channel.send.side_effect = PermissionError('dummy-private-text')
        with self.assertLogs(level='ERROR') as logs:
            asyncio.run(handler(msg))
        self.assertNotIn('dummy-private-text', '\n'.join(logs.output))
        self.assertEqual(self.repo.state('discord:456:123'), 'menu')
        self.assertFalse(self.repo.contains(self.repo.key('discord:1', 'live')))
        msg.channel.send.side_effect = None
        asyncio.run(handler(msg))
        self.assertEqual(self.repo.state('discord:456:123'), 'survey_rating')
        self.assertEqual(msg.channel.send.await_count, 2)
        self.assertEqual(msg.channel.send.call_args.kwargs['allowed_mentions'], sdk.AllowedMentions.none())
        asyncio.run(handler(msg))
        self.assertEqual(msg.channel.send.await_count, 2)
