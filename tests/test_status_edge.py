import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from core.bot import BotCore
from database import ProcessedMessages
from models import IncomingMessage
from adapters.mock import MockAdapter
import run_bot
from status import build_status


class StatusEdgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / 'secretdir' / 'test.db')
        self.repo = ProcessedMessages(self.path)
        self.sender = Mock()
        self.n = 0

    def core(self, admins=('telegram:1',), adapters=('telegram',)):
        return BotCore(self.repo, admins=set(admins), active_adapters=adapters)

    def send(self, core, user, text, channel='telegram', scope=None):
        self.n += 1
        self.sender.reset_mock()
        return core.handle(IncomingMessage(f'id{self.n}', user, text), self.sender, channel=channel, scope=scope)

    def test_variants_slash_case_whitespace(self):
        c = self.core()
        for t in ['status', '/status', 'STATUS', ' Status ', '/STATUS\n', '\tstatus']:
            self.assertIn('[status]', self.send(c, '1', t), repr(t))

    def test_near_miss_not_status(self):
        c = self.core()
        for t in ['statuses', 'status now', '//status', '/status@bot', 'st atus', '']:
            self.assertNotIn('[status]', self.send(c, '1', t) or '', repr(t))

    def test_none_text_admin_no_crash(self):
        self.assertNotIn('[status]', self.send(self.core(), '1', None))

    def test_non_admin_reply_identical_to_unknown_input(self):
        c = self.core()
        a = self.send(c, '2', 'status')
        b = self.send(c, '2', 'foobar')
        self.assertEqual(a, b)

    def test_admin_entry_is_channel_specific(self):
        c = self.core(admins=['telegram:1'])
        self.assertNotIn('[status]', self.send(c, '1', 'status', channel='discord', scope='5'))
        self.assertNotIn('[status]', self.send(c, '1', 'status', channel='mock'))
        self.assertNotIn('[status]', self.send(c, '1', 'status', channel='whatsapp'))

    def test_same_user_id_other_channel(self):
        c = self.core(admins=['telegram:1', 'discord:1'])
        self.assertIn('[status]', self.send(c, '1', 'status', channel='discord', scope='chan9'))
        self.assertIn('[status]', self.send(c, '1', 'status', channel='telegram', scope='c'))
        self.assertNotIn('[status]', self.send(c, '2', 'status', channel='discord', scope='chan9'))

    def test_inexact_admin_entries_not_matched(self):
        for entry in ['1', 'Telegram:1', ' telegram:1', 'telegram:01']:
            self.assertNotIn('[status]', self.send(self.core(admins=[entry]), '1', 'status'), entry)

    def test_empty_admin_entries(self):
        self.assertNotIn('[status]', self.send(self.core(admins=[]), '', 'status'))
        self.assertNotIn('[status]', self.send(self.core(admins=['']), '', 'status'))

    def test_state_unchanged_by_status(self):
        c = self.core()
        self.send(c, '1', '2')
        self.send(c, '1', 'status')
        self.assertEqual(self.repo.state('telegram:1:1'), 'survey_rating')
        self.send(c, '1', '3')
        self.send(c, '1', 'status')
        self.assertEqual(self.repo.state('telegram:1:1'), 'survey_comment')

    def test_non_admin_status_is_normal_survey_comment(self):
        c = self.core()
        self.send(c, '2', '2'); self.send(c, '2', '3'); self.send(c, '2', 'status')
        self.assertEqual(self.repo.state('telegram:2:2'), 'menu')

    def test_duplicate_status_message_id_skipped(self):
        c = self.core()
        m = IncomingMessage('dup', '1', 'status')
        self.assertIn('[status]', c.handle(m, self.sender, channel='telegram'))
        self.assertIsNone(c.handle(m, self.sender, channel='telegram'))

    def test_delivery_failure_then_retry(self):
        c = self.core()
        self.sender.send_text.side_effect = RuntimeError('net')
        m = IncomingMessage('d', '1', 'status')
        with self.assertRaises(RuntimeError):
            c.handle(m, self.sender, channel='telegram')
        self.sender.send_text.side_effect = None
        self.assertIn('[status]', c.handle(m, self.sender, channel='telegram'))

    def test_real_db_ok_and_no_path_leak(self):
        r = self.send(self.core(adapters=['discord', 'telegram']), '1', 'status')
        self.assertIn('有効なAdapter: discord, telegram', r)
        self.assertIn('DB接続: 接続OK', r)
        for leak in [self.path, 'secretdir', '.db']:
            self.assertNotIn(leak, r)

    def test_real_db_path_is_directory_reports_failed(self):
        self.repo.path = str(Path(self.path).parent)
        r = build_status(self.repo, ['telegram'])
        self.assertIn('DB接続: 接続失敗', r)
        self.assertNotIn('secretdir', r)

    def test_real_db_corrupt_file_reports_failed(self):
        Path(self.path).write_bytes(b'this is not a sqlite database' * 50)
        r = build_status(self.repo, ['telegram'])
        self.assertIn('DB接続: 接続失敗', r)
        self.assertNotIn('not a database', r.lower())

    def assert_broken_db_status(self, core):
        with self.assertLogs(level='ERROR') as cm:
            r = self.send(core, '1', 'status')
        self.assertIn('[status]', r)
        self.assertIn('DB接続: 接続失敗', r)
        self.sender.send_text.assert_called_once()
        out = r + '\n'.join(cm.output)
        for leak in [self.path, 'secretdir', 'not a database', 'unable to open', 'SECRET123', 'priv']:
            self.assertNotIn(leak, out)

    def test_handle_db_path_is_directory_admin_status_replies(self):
        c = self.core()
        self.repo.path = str(Path(self.path).parent)
        self.assert_broken_db_status(c)

    def test_handle_db_corrupt_admin_status_replies(self):
        c = self.core()
        Path(self.path).write_bytes(b'this is not a sqlite database' * 50)
        self.assert_broken_db_status(c)

    def test_handle_contains_raises_admin_status_replies(self):
        c = self.core()
        self.repo.contains = Mock(side_effect=RuntimeError('token=SECRET123 C:\\priv\\x.db'))
        self.assert_broken_db_status(c)

    def test_broken_db_non_admin_and_normal_input_unchanged(self):
        c = self.core()
        self.repo.contains = Mock(side_effect=RuntimeError('boom'))
        with self.assertRaises(RuntimeError):
            self.send(c, '2', 'status')  # non-admin: treated as normal input
        with self.assertRaises(RuntimeError):
            self.send(c, '1', 'hello')  # admin, non-status input

    def test_broken_db_status_send_failure_propagates(self):
        c = self.core()
        self.repo.contains = Mock(side_effect=RuntimeError('boom'))
        self.sender.send_text.side_effect = RuntimeError('net')
        with self.assertRaises(RuntimeError), self.assertLogs(level='ERROR'):
            c.handle(IncomingMessage('x', '1', 'status'), self.sender, channel='telegram')

    def test_handle_state_raises_admin_status_replies(self):
        c = self.core()
        self.repo.state = Mock(side_effect=RuntimeError('token=SECRET123 C:\\priv\\x.db'))
        self.assert_broken_db_status(c)

    def test_broken_db_status_not_recorded_as_processed(self):
        c = self.core()
        self.repo.contains = Mock(side_effect=RuntimeError('boom'))
        apply = Mock()
        self.repo.apply = apply
        with self.assertLogs(level='ERROR'):
            self.send(c, '1', 'status')
        apply.assert_not_called()

    def test_apply_failure_after_send_propagates_and_retry_possible(self):
        c = self.core()
        m = IncomingMessage('ap', '1', 'status')
        real_apply = self.repo.apply
        self.repo.apply = Mock(side_effect=RuntimeError('apply-fail'))
        with self.assertRaises(RuntimeError):
            c.handle(m, self.sender, channel='telegram')
        self.assertIn('接続OK', self.sender.send_text.call_args.args[1])
        self.repo.apply = real_apply
        self.assertIn('[status]', c.handle(m, self.sender, channel='telegram'))
        self.assertIsNone(c.handle(m, self.sender, channel='telegram'))

    def test_normal_dedup_and_state_transition_with_healthy_db(self):
        c = self.core()
        m = IncomingMessage('n1', '2', '2')
        self.assertIn('アンケートを開始', c.handle(m, self.sender, channel='telegram'))
        self.assertIsNone(c.handle(m, self.sender, channel='telegram'))
        self.assertEqual(self.repo.state('telegram:2:2'), 'survey_rating')

    def test_db_check_false_is_ng(self):
        self.repo.check = Mock(return_value=False)
        self.assertIn('接続NG', self.send(self.core(), '1', 'status'))

    def test_exception_message_not_in_reply_or_logs(self):
        self.repo.check = Mock(side_effect=RuntimeError('token=SECRET123 C:\\priv\\x.db'))
        with self.assertLogs(level='ERROR') as cm:
            r = self.send(self.core(), '1', 'status')
        self.assertNotIn('SECRET123', r)
        self.assertNotIn('priv', r)
        self.assertNotIn('SECRET123', '\n'.join(cm.output))

    def test_string_active_adapters_not_split(self):
        r = self.send(self.core(adapters='telegram'), '1', 'status')
        self.assertIn('有効なAdapter: telegram', r)

    def test_no_adapters(self):
        self.assertIn('有効なAdapter: なし', self.send(self.core(adapters=[]), '1', 'status'))

    def test_build_status_total_failure_fallback(self):
        with patch('core.bot.build_status', side_effect=Exception('boom')):
            r = self.send(self.core(), '1', 'status')
        self.assertIn('取得失敗', r)
        self.assertNotIn('boom', r)

    def test_mock_adapter_end_to_end(self):
        bot = MockAdapter(BotCore(self.repo, admins={'mock:local'}, active_adapters=['mock']))
        self.assertIn('有効なAdapter: mock', bot.receive('/status'))
        self.assertIn('[status]', bot.receive('status'))
        self.assertNotIn('[status]', bot.receive('status', user='other'))

    def test_regression_normal_flow_for_admin(self):
        c = self.core()
        self.assertIn('1：お問い合わせ', self.send(c, '1', 'hello'))
        self.assertIn('アンケートを開始', self.send(c, '1', '2'))
        self.assertIn('リセット', self.send(c, '1', 'reset'))

    def test_admin_set_copied(self):
        s = {'telegram:1'}
        c = BotCore(self.repo, admins=s)
        s.add('telegram:2')
        self.assertNotIn('[status]', self.send(c, '2', 'status'))


class AdminsParseTests(unittest.TestCase):
    def parse(self, value):
        env = {} if value is None else {'ADMIN_USERS': value}
        with patch.dict(os.environ, env, clear=True):
            return run_bot.admins()

    def test_unset_empty_blank(self):
        self.assertEqual(self.parse(None), frozenset())
        self.assertEqual(self.parse(''), frozenset())
        self.assertEqual(self.parse('  , ,'), frozenset())

    def test_whitespace_trimmed(self):
        self.assertEqual(self.parse(' telegram:1 , discord:2 ,'), {'telegram:1', 'discord:2'})

    def test_malformed_entries_rejected(self):
        for value in ['1', 'telegram:', ':1', 'TELEGRAM:1', 'whatsapp:1', 'telegram: ', 'telegram:1,bad']:
            with self.assertRaises(ValueError, msg=value):
                self.parse(value)

    def test_empty_sender_never_admin(self):
        # Defense in depth: even a hand-built "telegram:" entry must not match an empty sender.
        c = BotCore(Mock(), admins={'telegram:'})
        self.assertFalse(c.is_status_request(IncomingMessage('m', '', 'status'), 'telegram'))

    def test_valid_channels_accepted(self):
        self.assertEqual(self.parse('mock:local,telegram:1,discord:2'), {'mock:local', 'telegram:1', 'discord:2'})


if __name__ == '__main__':
    unittest.main()
