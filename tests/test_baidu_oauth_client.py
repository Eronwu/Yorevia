"""Credential-free client tests; runnable with stdlib unittest."""
import os
import unittest
from unittest.mock import patch
from yorevia.baidu_oauth import BaiduOAuth, broker_origin, verification_url

class OAuthClientTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {'YOREVIA_BAIDU_OAUTH_URL':'https://auth.example.test'}):
            self.client=BaiduOAuth()
        self.start=dict(session_id='s'*32, verification_url='https://openapi.baidu.com/device', user_code='ABCD-1234', interval=5, expires_in=60)

    def test_configuration_and_url_allowlist(self):
        for url in ['http://example.test','https://u:p@example.test','https://example.test/path','https://example.test/?token=x']:
            with self.assertRaises(ValueError):broker_origin(url)
        for url in ['https://evil.test/device','https://openapi.baidu.com.evil.test/device','https://openapi.baidu.com/device?token=x','https://openapi.baidu.com:444/device']:
            with self.assertRaises(ValueError):verification_url(url)

    @patch('yorevia.baidu_oauth.webbrowser.open',return_value=True)
    def test_token_never_returned_on_start_and_one_use(self, browser):
        with patch.object(self.client,'request',return_value=self.start) as request:
            result=self.client.start('a'*16)
            self.assertNotIn('proof',result)
            self.assertEqual(len(request.call_args.args[1]['proof_hash']),64)
        browser.assert_called_once_with('https://openapi.baidu.com/device',new=2)
        self.client.session['next_poll']=0
        with patch.object(self.client,'request',return_value={'status':'authorized','access_token':'fake-token-123456'}):
            self.assertEqual(self.client.poll('a'*16),'fake-token-123456')
            with self.assertRaises(ValueError):self.client.poll('a'*16)

    @patch('yorevia.baidu_oauth.webbrowser.open',return_value=True)
    def test_cancel_scope_expiry_and_throttle(self,_):
        with patch.object(self.client,'request',return_value=self.start):self.client.start('a'*16)
        with patch.object(self.client,'request') as request:
            self.client.cancel('b'*16)
            self.assertIsNotNone(self.client.session)
            self.assertIsNone(self.client.poll('a'*16))
            request.assert_not_called()
            self.client.session['expires']=0
            with self.assertRaises(ValueError):self.client.poll('a'*16)
            self.assertIsNone(self.client.session)

    @patch('yorevia.baidu_oauth.webbrowser.open',return_value=True)
    def test_cancel_during_poll_discards_late_token(self,_):
        with patch.object(self.client,'request',return_value=self.start):self.client.start('a'*16)
        self.client.session['next_poll']=0
        def response(*_):
            self.client.session=None
            return {'status':'authorized','access_token':'fake-token-123456'}
        with patch.object(self.client,'request',side_effect=response):
            with self.assertRaises(ValueError):self.client.poll('a'*16)

    @patch('yorevia.baidu_oauth.webbrowser.open',return_value=True)
    def test_pending_updates_interval(self,_):
        with patch.object(self.client,'request',return_value=self.start):self.client.start('a'*16)
        self.client.session['next_poll']=0
        with patch.object(self.client,'request',return_value={'status':'pending','interval':15}):
            self.assertIsNone(self.client.poll('a'*16))
            self.assertEqual(self.client.session['interval'],15)

    def test_invalid_configuration_does_not_break_offline_service(self):
        with patch.dict(os.environ, {'YOREVIA_BAIDU_OAUTH_URL':'not-a-valid-url'}):
            from yorevia.service import Service
            service=Service()
            try:
                self.assertFalse(service.baidu_oauth.origin)
                self.assertTrue(service.call('status'))
                with self.assertRaisesRegex(ValueError,'配置无效'):service.baidu_oauth.start('a'*16)
            finally:service.close()

    def test_unconfigured_disabled(self):
        with patch.dict(os.environ, {'YOREVIA_BAIDU_OAUTH_URL':''}):client=BaiduOAuth()
        with self.assertRaises(ValueError):client.start('a'*16)

    @patch('yorevia.baidu_oauth.webbrowser.open')
    def test_unsafe_provider_url_never_opened(self,browser):
        self.start['verification_url']='https://evil.test/device'
        with patch.object(self.client,'request',return_value=self.start):
            with self.assertRaises(ValueError):self.client.start('a'*16)
        browser.assert_not_called()

    def test_request_error_redacted(self):
        with patch.object(self.client.opener,'open',side_effect=ValueError('secret-provider-token')):
            with self.assertRaisesRegex(ValueError,'授权服务暂时不可用') as raised:
                self.client.request('start',{})
            self.assertNotIn('secret-provider-token',str(raised.exception))

if __name__=='__main__':unittest.main()
