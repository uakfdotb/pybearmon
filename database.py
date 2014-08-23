import MySQLdb

class DB:
	conn = None

	def connect(self):
		from config import config
		self.conn = MySQLdb.connect(host=config['db_host'], user=config['db_username'], passwd=config['db_password'], db=config['db_name'])

	def query(self, q, p = []):
		try:
			cursor = self.conn.cursor()
			cursor.execute(q, p)
			return cursor
		except (AttributeError, MySQLdb.OperationalError) as e:
			import time
			print 'database: encountered error: ' + str(e) + "; reconnecting in five seconds..."
			time.sleep(5000)
			print 'database: reconnecting'
			self.connect()
			return self.query(q, p)

db = DB()
db.connect()

def query(q, p = []):
	db.query(q, p)
