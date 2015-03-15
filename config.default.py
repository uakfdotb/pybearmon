config = {}

# database settings (MySQL)
config['db_name'] = 'monitor'
config['db_host'] = 'localhost'
config['db_username'] = 'monitor'
config['db_password'] = ''

# SMTP settings
config['mail_from'] = 'noreply@example.com'
config['mail_ssl'] = True
config['mail_host'] = 'example.com'
config['mail_port'] = '465'
config['mail_username'] = 'monitor'
config['mail_password'] = 'password'

# daemon settings
config['sleep_interval'] = 5 # seconds to sleep when idle
config['confirmations'] = 3 # confirmations needed before swapping state
config['num_threads'] = 2 # number of threads to spawn for monitoring
config['user_agent'] = 'pybearmon'
