#database information
"""
This file may contain cleartext passwords. It is strongly encouraged to ensure the account used is locked down
  to the principle of least privilege, and if able to, not use cleartext authentication to connect to your DB.
"""
import mysql.connector

class mysqlConn:

  def connect(self):
    config = {
      'user': '<db-user>',
      'password': '<db-password>',
      'host': '<db-ip/hostname>',
      'database': 'traderbot',
      'raise_on_warnings': True
    }
    return mysql.connector.connect(**config)
