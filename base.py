import decimal

from pymongo import MongoClient
from bson.decimal128 import Decimal128, create_decimal128_context
from decimal import Decimal
from Crypto.PublicKey import RSA
from bson.int64 import Int64

class Base(object):
	con = {}
	req = {}
	def __init__(self):
		self.con = MongoClient()
		self.req = self.con['kikki']
	def rebuild_base(self):
		self.req.drop_collection('users')
		self.req.create_collection('users')
		self.req.drop_collection('transactions')
		self.req.create_collection('transactions')
	def rebuild_tx(self):
		self.req.drop_collection('transactions')
		self.req.create_collection('transactions')
	def dump(self):
		print("-Base dump-")
		print("-Users dump-")
		for x in self.req['users'].find({}, {'_id':False}):
			print(x)
			print("\n")
		print("-Transactions dump-")
		for x in self.req['transactions'].find({}, {'_id':False}):
			print("\n")
			print(x)
#