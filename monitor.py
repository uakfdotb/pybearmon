import config
import util
import database
import checks
import alerts

uid = util.uid(16)
last_cleanup = 0

while True:
	if util.time() - last_cleanup >= 60:
		database.query("UPDATE checks SET `lock` = '' WHERE TIMESTAMPDIFF(SECOND, last_locked, NOW()) >= 60")
		last_cleanup = util.time()

	database.query("UPDATE checks SET `lock` = %s, last_locked = NOW() WHERE `lock` = '' AND TIMESTAMPDIFF(SECOND, last_checked, NOW()) >= check_interval ORDER BY RAND() LIMIT 1", (uid,))
	result = database.query("SELECT id, name, type, data, fail_count, success_count, status, turn_count FROM checks WHERE `lock` = %s LIMIT 1", (uid,))
	row = result.fetchone()

	if row:
		check_id = row['id']
		check_name = row['name']
		check_type = row['type']
		fail_count = row['fail_count']
		success_count = row['success_count']
		status = row['status']
		turn_count = row['turn_count']

		print "processing check %d: calling checks.%s" % (check_id, check_type)
		check_result = checks.run_check(check_type, util.decode(row['data']))

		if not check_result is dict or 'status' not in check_result:
			util.die("bad check handler [%s]: returned non-dict or missing status" % (check_type,))
		elif 'message' not in check_result:
			check_result['message'] = "Check offline: %s" % (check_name,)

		if check_result['status'] == 'fail':
			print "... got failure!"

			if status == 'online':
				if turn_count + 1 >= fail_count:
					# target has failed
					print "... fail_count exceeded, target is offline state now"
					update_result = database.query("UPDATE checks SET status = 'offline', turn_count = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))

					if update_result.affected_rows() == 1:
						# we still had the lock at the point where status was toggled to offline
						# then, send the alert
						alert_result = database.query("SELECT contacts.id, contacts.type, contacts.data FROM contacts, alerts WHERE contacts.id = alerts.contact_id AND alerts.check_id = %s", (check_id,))

						for alert_row in alert_result.fetchall():
							print "... alerting contact %d" % (alert_row['id'],)
							alert_func = getattr(alerts, alert_row['type'], None)

							if not alert_func:
								util.die("Invalid alert handler [%s]!" % (alert_row['type'],))

							# build context
							context = {}
							context['check_id'] = check_id
							context['check_name'] = check_name
							context['fail_count'] = fail_count
							context['success_count'] = success_count
							context['contact_id'] = alert_row['id']
							context['title'] = "Check offline: $check_name"
							context['message'] = check_result['message']

							alert_func(util.decode(alert_row['data']), [str(x) for x in context])
				else:
					# increase turn count
					database.query("UPDATE checks SET turn_count = turn_count + 1, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))
			else:
				database.query("UPDATE checks SET turn_count = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))
		elif check_result['status'] == 'success':
			print "... got success"

			if status == 'offline':
				if turn_count + 1 >= success_count:
					# target has come back online
					print "... success_count exceeded, target is online state now\n"
					database.query("UPDATE checks SET status = 'online', turn_count = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))
				else:
					# increase turn count
					database.query("UPDATE checks SET turn_count = turn_count + 1, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))
			else:
				database.query("UPDATE checks SET turn_count = 0, `lock` = '', last_checked = NOW() WHERE id = %s AND `lock` = %s", (check_id, uid))
		else:
			util.die("Check handler [%s] returned invalid status code [%s]!") % (check_type, check_result['status'])

		database.query("INSERT INTO check_results (check_id, result) VALUES (%s, %s)", (check_id, check_result['status']))
	else:
		print "no checks found, sleeping"
		time.sleep(config['sleep_interval'])
