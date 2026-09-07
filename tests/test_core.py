import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import requests
from core.bot import BotCore
from database import ProcessedMessages
from models import IncomingMessage
from adapters.mock import MockAdapter
from adapters.telegram import TelegramAdapter
from adapters.discord import normalize
from adapters.base import DeliveryError

class CoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = ProcessedMessages(str(Path(temp.name) / 'test.db'))
        self.core = BotCore(self.repo)
        self.sender = Mock()

    def test_mock_flow(self):
        bot = MockAdapter(self.core)
        for text in ['reset', '2', '9', '5', 'good']:
            bot.receive(text)
        self.assertIn('ご協力', bot.replies[-1][1])
        self.assertEqual(len(bot.replies), 5)

    def test_channel_and_scope_isolation(self):
        msg = IncomingMessage('1', '123', '2')
        for channel, scope in [('discord', 'a'), ('telegram', 'a'), ('whatsapp', None)]:
            self.core.handle(msg, self.sender, channel=channel, scope=scope)
        self.assertEqual(self.sender.send_text.call_count, 3)
        self.assertEqual(self.repo.state('discord:a:123'), 'survey_rating')
        self.assertEqual(self.repo.state('discord:b:123'), 'menu')
        self.assertEqual(self.repo.state('123'), 'survey_rating')

    def test_delivery_failure_retry_and_restart(self):
        msg = IncomingMessage('1', '123', '2')
        self.sender.send_text.side_effect = DeliveryError('failed')
        with self.assertRaises(DeliveryError):
            self.core.handle(msg, self.sender, channel='telegram')
        self.assertEqual(self.repo.state('telegram:123:123'), 'menu')
        self.sender.send_text.side_effect = None
        self.core.handle(msg, self.sender, channel='telegram')
        BotCore(self.repo).handle(msg, self.sender, channel='telegram')
        self.assertEqual(self.sender.send_text.call_count, 2)

    def test_telegram_filters_and_mapping(self):
        bot = TelegramAdapter(self.core, 'fake', {'123'})
        bot.send_text = Mock()
        update = {'update_id': 9, 'message': {'from': {'id': 123}, 'chat': {'id': 123, 'type': 'group'}, 'text': '2'}}
        bot.receive(update)
        bot.send_text.assert_not_called()
        update['message']['chat']['type'] = 'private'
        bot.receive(update)
        bot.send_text.assert_called_once()
        self.assertEqual(bot.send_text.call_args.args[0], '123')
        bot.receive(update)
        self.assertEqual(bot.send_text.call_count, 1)

    def test_telegram_http_errors_sanitized(self):
        session = Mock()
        session.post.side_effect = requests.Timeout('secret')
        bot = TelegramAdapter(self.core, 'fake', {'123'}, session)
        with self.assertRaises(DeliveryError) as error:
            bot.send_text('123', 'hi')
        self.assertNotIn('secret', str(error.exception))

    def test_telegram_response_validation(self):
        from unittest.mock import MagicMock
        session = MagicMock()
        response = session.post.return_value.__enter__.return_value
        response.status_code = 200
        response.json.return_value = {'ok': True, 'result': {'message_id': 1}}
        bot = TelegramAdapter(self.core, 'fake', {'123'}, session)
        bot.send_text('123', 'hello')
        self.assertEqual(session.post.call_args.kwargs['json']['chat_id'], '123')
        response.json.return_value = {'ok': False}
        with self.assertRaises(DeliveryError):
            bot.send_text('123', 'hello')

    def test_discord_filters(self):
        msg = NS(id=1, author=NS(id=123, bot=False), channel=NS(id=456), content='2')
        self.assertIsNotNone(normalize(msg, {'123'}, {'456'}))
        self.assertIsNone(normalize(msg, {'999'}, {'456'}))
        self.assertIsNone(normalize(msg, {'123'}, {'999'}))
        msg.author.bot = True
        self.assertIsNone(normalize(msg, {'123'}, {'456'}))
