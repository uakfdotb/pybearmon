import util

def email(data, context):
	'''
	Sends an email to target with the given parameters.
	From address and email method are specified in configuration.

	data['email']: the email address to send to
	context['title']: email subject
	context['message']: email body (plaintext)
	'''
	from config import config

	if 'email' not in data:
		util.die('alerts.email: missing email')

	import email.utils
	from_address = email.utils.parseaddr(config['mail_from'])[1]

	if not from_address:
		util.die('alerts.email: invalid from address [%s] specified in configuration' % (config['mail_from'],))

	to_address = email.utils.parseaddr(data['email'])[1]

	if not to_address:
		util.die('alerts.email: invalid to address [%s] contact' % (data['email'],))

	if config['mail_ssl']:
		from smtplib import SMTP_SSL as SMTP
	else:
		from smtplib import SMTP
	from email.MIMEText import MIMEText

	conn = SMTP(config['mail_host'], config['mail_port'])
	conn.login(config['mail_username'], config['mail_password'])

	try:
		msg = MIMEText(context['message'], 'plain')
		msg['From'] = from_address
		msg['To'] = to_address
		msg['Subject'] = context['title']

		conn.sendmail(from_address, to_address, msg.as_string())
	finally:
		conn.close()

def sms_twilio(data, context):
	'''
	Sends an SMS message via Twilio to the given number.
	The message is "[title] message"
	config must include the strings twilio_accountsid, twilio_authtoken, and twilio_number

	data['number']: phone number to send SMS message to.
	data['twilio_accountsid'], data['twilio_authtoken'], data['twilio_number']: optional Twilio configuration
	context['title']: used in creating SMS message
	context['message']: used in creating SMS message
	'''
	from config import config
	from twilio.rest import TwilioRestClient

	if 'number' not in data:
		util.die('alert_sms_twilio: missing number')

	config_target = config

	if 'twilio_accountsid' in data and 'twilio_authtoken' in data and 'twilio_number' in data:
		config_target = data

	sms_message = "[%s] %s" % (context['title'], context['message'])
	client = TwilioRestClient(config_target['twilio_accountsid'], config_target['twilio_authtoken'])

	message = client.messages.create(body = sms_message, to = data['number'], from_ = config_target['twilio_number'])

def http(data, context):
	'''
	Notifies a web hook over HTTP regarding alert.
	All context parameters are sent, via GET.

	data['url']: the target web hook
	context: encoded as GET parameters
	'''
	if 'url' not in data:
		util.die('alert_http: missing url')

	import urllib
	import checks
	url = data['url'] + '?' + urllib.urlencode(context)

	result = checks.http_helper({'url': url})

	if result['status'] == 'fail' and 'message' in result:
		print "alert_http: error: " + result['message']

def pushover(data, context):
	'''
	Sends alert to Pushovers API.
	
	data['token']: Application token
	data['user']: User token
	data['priority']: At what priority to send notification. https://pushover.net/api#priority
	context['title']: used to craft notification message
	context['message']: used to craft notification message
	pushmessage: Prettier updown message for notification
	'''
	if 'token' not in data or 'user' not in data or 'priority' not in data:
		util.die('alert_pushover: details missing!')
		return
	
	if context['updown'] == 'down':
		pushmessage = context['title'] + " - " + context['message']
	elif context['updown'] == 'up':
		pushmessage = context['title']

	import httplib, urllib
	conn = httplib.HTTPSConnection("api.pushover.net:443")
	conn.request("POST", "/1/messages.json",
		urllib.urlencode({
		"token": data['token'],
		"user": data['user'],
		"priority": data['priority'],
		"message": pushmessage,
		}), { "Content-type": "application/x-www-form-urlencoded" })
	