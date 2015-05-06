import util

def extract(data, key, default):
	if key in data:
		return data[key]
	else:
		return default

def run_check(name, data):
	import checks

	try:
		return getattr(checks, name)(data)
	except Exception as e:
		return {'status': 'fail', 'message': 'exception: ' + str(e)}

def http_contains(data):
	# keys: substring, url (also http_helper params)
	if 'substring' not in data or 'url' not in data:
		util.die('checks.http_contains: missing substring')

	result = http_helper(data)

	if result['status'] == 'fail':
		return result
	elif data['substring'] in result['content']:
		return {'status': 'success'}
	else:
		return {'status': 'fail', 'message': "target [%s] does not contain string [%s]" % (data['url'], data['substring'])}

def http_helper(data):
	from config import config

	# keys: url, timeout
	if 'url' not in data:
		util.die('checks.http_helper: missing url')

	import httplib2

	try:
		handle = httplib2.Http(timeout = float(extract(data, 'timeout', 10)))
		resp, content = handle.request(data['url'], 'GET', headers={'User-Agent': config['user_agent']})
		return {'status': 'success', 'code': resp.status, 'content': content}
	except httplib2.RelativeURIError as e:
		return {'status': 'fail', 'message': 'RelativeURIError (possibly invalid URI: %s)' % (data['url'])}
	except httplib2.HttpLib2Error as e:
		return {'status': 'fail', 'message': e.strerror}

def http_status(data):
	# keys: status, url (also http_helper params)
	if 'status' not in data or 'url' not in data:
		util.die('checks.http_status: missing status')

	result = http_helper(data)

	if result['status'] == 'fail':
		return result
	elif str(result['code']) == data['status']:
		return {'status': 'success'}
	else:
		return {'status': 'fail', 'message': "target [%s] returned unexpected status [%s], expected [%s]" % (data['url'], str(result['code']), data['status'])}

def http_ok(data):
	data['status'] = '200'
	return http_status(data)

def ssl_expire(data):
	# keys: hostname, optional port (default 443), days (default 7), and timeout (default 10)
	from config import config

	if 'hostname' not in data:
		util.die('checks.ssl_expire: missing hostname')

	hostname = data['hostname']
	port = int(extract(data, 'port', 443))
	days = int(extract(data, 'days', 7))
	timeout = float(extract(data, 'timeout', 10))

	import ssl
	from datetime import datetime
	import socket

	try:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(timeout)
		sock.connect((hostname, port))
		ssl_sock = ssl.wrap_socket(sock, cert_reqs=ssl.CERT_REQUIRED, ca_certs='/etc/ssl/certs/ca-certificates.crt', ciphers=("HIGH:-aNULL:-eNULL:-PSK:RC4-SHA:RC4-MD5"))
		cert = ssl_sock.getpeercert()
		ssl_sock.close()
	except ssl.SSLError as e:
		return {'status': 'fail', 'message': 'SSL connection failure: %s' % (e.strerror)}

	try:
		expire_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
	except:
		return {'status': 'fail', 'message': 'Certificate has unknown date format: %s' % (cert['notAfter'])}

	expire_in = expire_date - datetime.now()

	if expire_in.days < days:
		return {'status': 'fail', 'message': 'SSL certificate will expire in %d hours' % (expire_in.total_seconds() / 3600,)}
	else:
		return {'status': 'success'}

def ping(data):
	# keys: target
	if 'target' not in data:
		util.die('checks.ping: missing target')

	import subprocess

	target = data['target']
	result = subprocess.Popen(['ping', target, '-c', '3', '-w', '3'], stdout=subprocess.PIPE).stdout.read()

	if '100% packet loss' in result:
		return {'status': 'fail', 'message': "No response from %s" % (target,)}
	else:
		return {'status': 'success'}

def tcp_connect(data):
	# keys: target, port; optional: timeout
	if 'target' not in data or 'port' not in data:
		util.die('checks.tcp_connect: missing target or port')

	target = data['target']
	port = int(data['port'])
	timeout = float(extract(data, 'timeout', 5))

	import socket
	sock = socket.socket()
	sock.settimeout(timeout)
	sock.connect((target, port))
	sock.close()
	return {'status': 'success'}
