from config import config
import util
import database
import checks
import alerts

import time
import multiprocessing
import threading
import random

recent_failures = set()
recent_failures_lock = threading.Lock()
print_lock = threading.Lock()

def safe_print(msg, params = ()):
	with print_lock:
		print msg % params

class MonitorPool:
	q = multiprocessing.Queue()
	num_threads = config['num_threads']

	def start(self):
		for i in xrange(self.num_threads):
			t = threading.Thread(target=self.worker)
			t.daemon = True
			t.start()

	def free(self):
		return self.num_threads - self.q.qsize()

	def queue(self, check_id, check_name, check_type, check_data, status, confirmations, lock_uid):
		self.q.put((check_id, check_name, check_type, check_data, status, confirmations, lock_uid))

	def handle_change(self, thread_name, check_id, check_name, lock_uid, status, check_result):
		if status == 'offline':
			updown = 'down'
		elif status == 'online':
			updown = 'up'

		safe_print("[%s] ... confirmed, target is %s state now", (thread_name, status))
		update_result = database.query("UPDATE checks SET status = %s, confirmations = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (status, check_id, lock_uid))

		if update_result.rowcount == 1:
			# we still had the lock at the point where status was toggled
			# then, send the alert
			alert_result = database.query("SELECT contacts.id, contacts.type, contacts.data FROM contacts, alerts WHERE contacts.id = alerts.contact_id AND alerts.check_id = %s AND alerts.type IN ('both', %s)", (check_id, updown))

			for alert_row in alert_result.fetchall():
				safe_print("[%s] ... alerting contact %d", (thread_name, alert_row['id']))
				alert_func = getattr(alerts, alert_row['type'], None)

				if not alert_func:
					util.die("Invalid alert handler [%s]!" % (alert_row['type']))

				# build context
				context = {}
				context['check_id'] = check_id
				context['check_name'] = check_name
				context['contact_id'] = alert_row['id']
				context['title'] = "Check %s: %s" % (status, check_name)
				context['status'] = status
				context['updown'] = updown
				context['message'] = check_result['message']

				alert_func(util.decode(alert_row['data']), context)

			# also add an event
			database.query("INSERT INTO check_events (check_id, type) VALUES (%s, %s)", (check_id, updown))

	def worker(self):
		thread_name = threading.currentThread().getName()

		while True:
			check_id, check_name, check_type, check_data, status, confirmations, lock_uid = self.q.get()

			safe_print("[%s] processing check %d: calling checks.%s", (thread_name, check_id, check_type))
			check_result = checks.run_check(check_type, util.decode(check_data))

			safe_print("[%s] check %d result: %s", (thread_name, check_id, str(check_result)))

			if not type(check_result) is dict or 'status' not in check_result:
				util.die("[%s] bad check handler [%s]: returned non-dict or missing status" % (thread_name, check_type))
			elif 'message' not in check_result:
				if check_result['status'] == 'fail':
					check_result['message'] = "Check offline: %s" % (check_name)
				else:
					check_result['message'] = "Check online: %s" % (check_name)

			if check_result['status'] == 'fail':
				safe_print("[%s] ... got failure!", (thread_name))

				if status == 'online':
					with recent_failures_lock:
						recent_failures.add((check_id, util.time()))

					if confirmations + 1 >= config['confirmations']:
						# target has failed
						self.handle_change(thread_name, check_id, check_name, lock_uid, 'offline', check_result)
					else:
						# increase confirmations
						database.query("UPDATE checks SET confirmations = confirmations + 1, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, lock_uid))
				else:
					database.query("UPDATE checks SET confirmations = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, lock_uid))
			elif check_result['status'] == 'success':
				safe_print("[%s] ... got success", (thread_name))

				if status == 'offline':
					if confirmations + 1 >= config['confirmations']:
						# target has come back online
						self.handle_change(thread_name, check_id, check_name, lock_uid, 'online', check_result)
					else:
						# increase confirmations
						database.query("UPDATE checks SET confirmations = confirmations + 1, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, lock_uid))
				else:
					database.query("UPDATE checks SET confirmations = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, lock_uid))
			else:
				util.die("Check handler [%s] returned invalid status code [%s]!") % (check_type, check_result['status'])

pool = MonitorPool()
pool.start()
last_cleanup = 0

while True:
	safe_print("[monitor] sleeping")
	time.sleep(random.uniform(config['sleep_interval'] * 2 / 3, config['sleep_interval'] * 4 / 3))

	if util.time() - last_cleanup >= 60000:
		last_cleanup = util.time()
		database.query("UPDATE checks SET `lock` = '' WHERE TIMESTAMPDIFF(SECOND, last_locked, NOW()) >= 60")

		with recent_failures_lock:
			for check_tuple in set(recent_failures):
				if util.time() - check_tuple[1] >= 60000:
					recent_failures.remove(check_tuple)

	uid = util.uid(16)
	free_threads = pool.free()

	update_query = "UPDATE checks SET `lock` = %s, last_locked = NOW() WHERE `lock` = '' AND (TIMESTAMPDIFF(SECOND, last_checked, NOW()) >= check_interval OR confirmations > 0)"
	params = [uid]

	with recent_failures_lock:
		if recent_failures:
			update_query += " AND id NOT IN (" + ', '.join(['%s' for check_tuple in recent_failures]) + ")"
			params.extend([check_tuple[0] for check_tuple in recent_failures])

	update_query += " ORDER BY RAND() LIMIT %d" % (free_threads)
	safe_print("[monitor] fetching up to %d...", (free_threads))
	database.query(update_query, params)

	result = database.query("SELECT id, name, type, data, status, confirmations FROM checks WHERE `lock` = %s", (uid,))
	safe_print("[monitor] fetched %d checks", (result.rowcount))

	for row in result.fetchall():
		check_id = row['id']
		check_name = row['name']
		check_type = row['type']
		check_data = row['data']
		status = row['status']
		confirmations = row['confirmations']

		pool.queue(check_id, check_name, check_type, check_data, status, confirmations, uid)
