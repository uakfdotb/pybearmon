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
	# keys: url, timeout
	if 'url' not in data:
		util.die('checks.http_helper: missing url')

	import httplib2

	try:
		handle = httplib2.Http(timeout = float(extract(data, 'timeout', 10)))
		resp, content = handle.request(data['url'], 'GET')
		return {'status': 'success', 'code': resp.status, 'content': content}
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
	global config

	if 'hostname' not in data:
		util.die('checks.ssl_expire: missing hostname')

	hostname = data['hostname']
	port = int(extract(data, 'port', 443))
	days = int(extract(data, 'days', 7))
	timeout = float(extract(data, 'timeout', 10))

	import socket
	from OpenSSL import SSL
	from datetime import datetime

	ctx = SSL.Context(SSL.TLSv1_METHOD)
	ctx.set_verify(SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT, pyopenssl_check_callback)
	ctx.load_verify_locations(config['cacerts_path'])

	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((hostname, port))
	ssl_sock = SSL.Connection(ctx, sock)
	ssl_sock.set_connect_state()
	ssl_sock.set_tlsext_host_name(hostname)
	ssl_sock.do_handshake()

	cert = ssl_sock.get_peer_certificate()

	if 'notAfter' in cert:
		expire_date = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")
		expire_in = expire_date - datetime.now()

		if expire_in.days < days:
			return {'status': 'fail', 'message': 'SSL certificate will expire in %d hours' % (expire_in.hours,)}
 		else:
 			return {'status': 'success'}
	else:
		return {'status': 'fail', 'message': 'parsed SSL information missing notAfter'}

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
	sock.connect((target, port))
	sock.close()
	return {'status': 'success'}
