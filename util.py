def uid(length):
	import random
	characters = "0123456789abcdefghijklmnopqrstuvwxyz"
	return ''.join(random.choice(characters) for _ in xrange(length))

def decode(data):
	import urllib

	array = []
	parts = data.split('&')

	for part in parts:
		keys = part.split('=')

		if len(keys) >= 2:
			k = urllib.unquote_plus(keys[0])
			v = urllib.unquote_plus(keys[1])
			array[k] = v

	return array

def die(message):
	print message
	import sys
	sys.exit(-1)

def time():
	import time
	return int(round(time.time() * 1000))
