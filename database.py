import MySQLdb
import threading

class DB:
	conn = None
	db_lock = threading.RLock()

	def connect(self, reconnect = False):
		from config import config
		try:
			self.conn = MySQLdb.connect(host=config['db_host'], user=config['db_username'], passwd=config['db_password'], db=config['db_name'])
			self.conn.autocommit(True)
		except (AttributeError, MySQLdb.OperationalError) as e:
			if not reconnect:
				raise
			# else ignore and return

	def query(self, q, p = []):
		with self.db_lock:
			try:
				cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
				cursor.execute(q, p)
				self.conn.commit()
				return cursor
			except (AttributeError, MySQLdb.OperationalError) as e:
				import time
				print 'database: encountered error: ' + str(e) + "; reconnecting in five seconds..."
				time.sleep(5)
				print 'database: reconnecting'
				self.connect()
				return self.query(q, p)

db = DB()
db.connect()

def query(q, p = []):
	return db.query(q, p)
