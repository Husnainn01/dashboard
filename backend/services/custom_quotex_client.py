"""
Custom Quotex Client
Extracts essential functionality from PyQuotex with proper proxy/SSL handling
"""

import asyncio
import json
import ssl
import time
import logging
import requests
import websocket
from urllib.parse import urlparse
import certifi

class CustomQuotexClient:
    def __init__(self, email, password, proxy_url=None, lang='en'):
        self.email = email
        self.password = password
        self.proxy_url = proxy_url
        self.lang = lang
        self.host = "qxbroker.com"
        self.https_url = f"https://{self.host}"
        self.wss_url = f"wss://ws2.{self.host}/socket.io/?EIO=3&transport=websocket"
        
        # Session data
        self.session_data = {}
        self.is_connected = False
        self.websocket_client = None
        self.account_balance = None
        
        # Configure proxy for requests
        self.proxies = None
        if self.proxy_url:
            self.proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Setup requests session with proxy
        self.session = requests.Session()
        if self.proxies:
            self.session.proxies.update(self.proxies)
            self.session.verify = False
            
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings()
    
    async def authenticate(self):
        """Login to Quotex using the proper flow (like PyQuotex)"""
        try:
            self.logger.info("🔑 Starting authentication...")
            
            # Step 1: Get CSRF token from sign-in page (not modal)
            token_url = f"{self.https_url}/{self.lang}/sign-in"
            
            token_headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Linux"',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Dnt': '1'
            }
            
            if self.proxy_url and 'oxylabs' in self.proxy_url:
                token_headers['x-oxylabs-geo-location'] = 'United States'
            
            self.logger.info(f"🌐 Getting CSRF token from: {token_url}")
            
            token_response = self.session.get(
                token_url,
                headers=token_headers,
                timeout=30
            )
            
            if token_response.status_code != 200:
                return False, f"Failed to get CSRF token: {token_response.status_code}"
            
            # Extract CSRF token from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(token_response.text, 'html.parser')
            
            # Debug: Log the response content
            self.logger.info(f"📄 Token response content (first 1000 chars): {token_response.text[:1000]}")
            
            # Try multiple ways to find the CSRF token
            token_input = (
                soup.find('input', {'name': '_token'}) or
                soup.find('input', attrs={'name': '_token'}) or 
                soup.find('input', {'id': '_token'}) or
                soup.find('meta', {'name': 'csrf-token'})
            )
            
            csrf_token = None
            if token_input:
                if token_input.name == 'meta':
                    csrf_token = token_input.get('content')
                else:
                    csrf_token = token_input.get('value')
            
            if not csrf_token:
                # Log all input fields and meta tags for debugging
                all_inputs = soup.find_all('input')
                all_metas = soup.find_all('meta')
                self.logger.info(f"🔍 Found {len(all_inputs)} input fields:")
                for inp in all_inputs:
                    self.logger.info(f"  - {inp.get('name', 'no-name')}: {inp.get('type', 'no-type')} = {inp.get('value', 'no-value')}")
                
                self.logger.info(f"🔍 Found {len(all_metas)} meta tags:")
                for meta in all_metas:
                    self.logger.info(f"  - {meta.get('name', 'no-name')}: {meta.get('content', 'no-content')}")
                
                self.logger.error("❌ CSRF token not found in response")
                return False, "CSRF token not found"
            
            self.logger.info(f"✅ Got CSRF token: {csrf_token[:20]}...")
            
            # Step 2: Login with form data  
            login_url = f"{self.https_url}/{self.lang}/sign-in/"
            
            login_headers = {
                'User-Agent': token_headers['User-Agent'],
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': f"{self.https_url}/{self.lang}/sign-in/modal",
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-User': '?1'
            }
            
            if self.proxy_url and 'oxylabs' in self.proxy_url:
                login_headers['x-oxylabs-geo-location'] = 'United States'
            
            login_data = {
                '_token': csrf_token,
                'email': self.email,
                'password': self.password,
                'remember': '1'
            }
            
            self.logger.info(f"🔐 Posting login data to: {login_url}")
            
            login_response = self.session.post(
                login_url,
                data=login_data,
                headers=login_headers,
                timeout=30,
                allow_redirects=True
            )
            
            self.logger.info(f"📊 Login response status: {login_response.status_code}")
            self.logger.info(f"📍 Final URL: {login_response.url}")
            
            # Check if login was successful (should redirect to /trade)
            if 'trade' not in login_response.url:
                # Parse error message from HTML
                soup = BeautifulSoup(login_response.text, 'html.parser')
                error_div = soup.find('div', {'class': 'hint--danger'}) or soup.find('div', {'class': 'input-control-cabinet__hint'})
                error_msg = error_div.text.strip() if error_div else "Login failed - no redirect to trade page"
                self.logger.error(f"❌ Login failed: {error_msg}")
                return False, f"Login failed: {error_msg}"
            
            # Step 3: Extract session token from trade page JavaScript
            soup = BeautifulSoup(login_response.text, 'html.parser')
            scripts = soup.find_all('script', {'type': 'text/javascript'})
            
            session_token = None
            for script in scripts:
                script_text = script.get_text() if script else ""
                if 'window.settings' in script_text:
                    import re
                    match = re.sub(r'window\.settings\s*=\s*', '', script_text.strip().replace(';', ''))
                    try:
                        settings = json.loads(match)
                        session_token = settings.get('token')
                        break
                    except:
                        continue
            
            if not session_token:
                self.logger.error("❌ Session token not found in JavaScript")
                return False, "Session token not found"
            
            # Store session data
            self.session_data = {
                'token': session_token,
                'cookies': '; '.join([f"{c.name}={c.value}" for c in self.session.cookies]),
                'user_agent': login_headers['User-Agent']
            }
            
            self.logger.info(f"✅ Authentication successful! Token: {session_token[:20]}...")
            return True, "Login successful"
            
        except Exception as e:
            self.logger.error(f"❌ Authentication error: {str(e)}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False, str(e)
    
    def _create_websocket_client(self):
        """Create WebSocket client with proxy support"""
        try:
            headers = {
                "User-Agent": self.session_data.get("user_agent"),
                "Origin": self.https_url,
                "Host": f"ws2.{self.host}",
            }
            
            # Configure SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # WebSocket configuration
            ws_config = {
                "on_message": self._on_message,
                "on_error": self._on_error,
                "on_close": self._on_close,
                "on_open": self._on_open,
                "header": headers,
                "sslopt": {
                    "context": ssl_context,
                    "check_hostname": False,
                    "cert_reqs": ssl.CERT_NONE
                }
            }
            
            # Add proxy configuration for WebSocket if available  
            if self.proxy_url:
                parsed_proxy = urlparse(self.proxy_url)
                ws_config["http_proxy_host"] = parsed_proxy.hostname
                ws_config["http_proxy_port"] = parsed_proxy.port
                
                # Add proxy authentication if present
                if parsed_proxy.username and parsed_proxy.password:
                    ws_config["http_proxy_auth"] = (parsed_proxy.username, parsed_proxy.password)
            
            self.websocket_client = websocket.WebSocketApp(
                self.wss_url,
                **ws_config
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ WebSocket setup error: {str(e)}")
            return False
    
    def _on_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            
            # Parse Socket.IO message
            if message.startswith('42'):
                json_data = json.loads(message[2:])
                self._handle_socket_message(json_data)
                
        except Exception as e:
            self.logger.error(f"❌ Message handling error: {str(e)}")
    
    def _handle_socket_message(self, data):
        """Handle parsed Socket.IO messages"""
        try:
            if isinstance(data, list) and len(data) >= 2:
                event_type = data[0]
                event_data = data[1] if len(data) > 1 else {}
                
                # Handle different event types
                if event_type == "authorization/reject":
                    self.logger.error("❌ WebSocket authorization rejected")
                    self.is_connected = False
                elif "balance" in str(event_data):
                    self.account_balance = event_data
                    self.logger.info(f"💰 Balance updated: {event_data}")
                    
        except Exception as e:
            self.logger.error(f"❌ Socket message handling error: {str(e)}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        self.logger.error(f"❌ WebSocket error: {str(error)}")
        self.is_connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self.logger.info("🔌 WebSocket connection closed")
        self.is_connected = False
    
    def _on_open(self, ws):
        """Handle WebSocket open"""
        self.logger.info("🔗 WebSocket connected")
        self.is_connected = True
        
        # Send initial messages
        ws.send('42["tick"]')
        if self.session_data.get('token'):
            auth_msg = f'42["authorization","{self.session_data["token"]}"]'
            ws.send(auth_msg)
    
    async def connect(self):
        """Main connection method"""
        try:
            # Step 1: Authenticate
            auth_success, auth_msg = await self.authenticate()
            if not auth_success:
                return False, auth_msg
            
            # Step 2: Setup WebSocket
            if not self._create_websocket_client():
                return False, "Failed to create WebSocket client"
            
            # Step 3: Start WebSocket connection
            import threading
            
            def run_websocket():
                self.websocket_client.run_forever(
                    ping_interval=30,
                    ping_timeout=10
                )
            
            ws_thread = threading.Thread(target=run_websocket)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection
            max_wait = 10  # seconds
            wait_time = 0
            while not self.is_connected and wait_time < max_wait:
                await asyncio.sleep(0.5)
                wait_time += 0.5
            
            if self.is_connected:
                return True, "Connected successfully"
            else:
                return False, "WebSocket connection timeout"
                
        except Exception as e:
            self.logger.error(f"❌ Connection error: {str(e)}")
            return False, str(e)
    
    async def get_balance(self):
        """Get account balance"""
        if not self.is_connected:
            return None
        
        # Wait for balance data
        max_wait = 5
        wait_time = 0
        while not self.account_balance and wait_time < max_wait:
            await asyncio.sleep(0.5)
            wait_time += 0.5
        
        return self.account_balance
    
    def disconnect(self):
        """Disconnect from Quotex"""
        if self.websocket_client:
            self.websocket_client.close()
        self.is_connected = False
        self.logger.info("🔌 Disconnected from Quotex")

# Example usage
async def main():
    proxy_url = 'http://husnain_BRA4f:May4732=123=@unblock.oxylabs.io:60000'
    
    client = CustomQuotexClient(
        email="kingkafann@gmail.com",
        password="bazam@1498",
        proxy_url=proxy_url
    )
    
    success, message = await client.connect()
    print(f"Connection: {message}")
    
    if success:
        balance = await client.get_balance()
        print(f"Balance: {balance}")
        
        # Keep alive for testing
        await asyncio.sleep(10)
        
        client.disconnect()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 