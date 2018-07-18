import binascii
import decimal
import re

from pymongo import MongoClient
from bson.decimal128 import Decimal128, create_decimal128_context
from decimal import Decimal
from bson.int64 import Int64
from base64 import b64decode
from os import urandom
from email.utils import parseaddr

import secrets

class EngineException(Exception):
	pass

class Users:
	conn = None
	handle = None
	data = None
	extended = False
	base = None
	def seqnext(self):
		ret = None
		try:
			ret = self.handle.find_one_and_update( filter = { '_id': 'userseq' }, update = { '$inc': {'seq': Int64(1)}}, projection = {'_id': False} ).get('seq')
		except Exception as ex:
			self.handle.insert({'_id': "userseq", 'seq': Int64(1) })
			ret = self.handle.find_one_and_update( filter = { '_id': 'userseq' }, update = { '$inc': {'seq': Int64(1)}}, projection = {'_id': False} ).get('seq')
		return Int64(ret)
	def base_seqnext(self):
		ret = None
		if( self.data['id'] is not None ):
			try:
				ret = self.handle.find_one_and_update( filter = { 'id': self.data['id'] }, update = { '$inc': {'base': Int64(1)}}, projection = {'_id': False} ).get('base')
			except Exception as ex:
				self.handle.update( filter = {'id': self.data['id']}, update = {'$set': {'base': Int64(1) }}, upsert = True )
				ret = self.handle.find_one_and_update( filter = { 'id': self.data['id'] }, update = { '$inc': {'base': Int64(1)}}, projection = {'_id': False} ).get('base')
			return Int64(ret)
		else:
			return None
	def __init__(self, rawhead = None):
		#
		# Default Constructor
		# Creating collections and sequences
		# Attaching database handler to self
		#
		if( rawhead is not None ):
			self.extended = True
			self.conn = rawhead
		else:
			self.extended = False
			self.conn = MongoClient()
		handle = self.conn['kikki']
		if('devices' not in handle.collection_names()):
			handle.create_collection('devices')
		if('users' not in handle.collection_names()):
			handle.create_collection('users')
			handle['users'].insert({'_id': "userseq", 'seq': Int64(1) })
		self.handle = handle['users']
	def validate(self, UIDObj):
		qry = dict()
		data = None
		try:
			TempList = list()
			TempList.append(str(UIDObj))
			if(re.search(r'^[1-9][0-9]*$', str(UIDObj)) is not None):
				qry['id'] = Int64( UIDObj )
				data = self.handle.find_one( filter = qry, projection = {'_id' : False} )
			elif(re.search(r'^\+[0-9\-\.\(\)]*$', str(UIDObj)) is not None):
				data = self.handle.find_one( filter = {'phone':{'$in': TempList }}, projection = {'_id' : False} )
			elif(len(parseaddr(str(UIDObj))[1]) != 0):
				data = self.handle.find_one( filter = {'mail':{'$in': TempList }}, projection = {'_id' : False} )
			if(data is None):
				return -1
			else:
				return data['id']
		except Exception as ex:
			raise EngineException( 'USER_INVALID' )
	def load(self, UIDObj):
		#
		# User Instance Loader
		# Building user object from any ID
		#
		qry = dict()
		try:
			TempList = list()
			TempList.append(str(UIDObj))
			if(re.search(r'^[1-9][0-9]*$', str(UIDObj)) is not None):
				qry['id'] = Int64( UIDObj )
				self.data = self.handle.find_one( filter = qry, projection = {'_id' : False} )
			elif(re.search(r'^\+[0-9\-\.\(\)]*$', str(UIDObj)) is not None):
				self.data = self.handle.find_one( filter = {'phone':{'$in': TempList }}, projection = {'_id' : False} )
			elif(len(parseaddr(str(UIDObj))[1]) != 0):
				self.data = self.handle.find_one( filter = {'mail':{'$in': TempList }}, projection = {'_id' : False} )
			if(self.data is None):
				raise EngineException( 'USER_NOT_FOUND' )
		except EngineException as ex:
			raise EngineException( ex )
	def resolve(self):
		return self.data['id']
	def update_balance(self):
		BalanceDict = dict()
		LentDict = dict()
		BorrowedDict = dict()
		count = 0
		BalanceDict = self.data['balance']['total']
		LentDict = self.data['balance']['lent']
		BorrowedDict = self.data['balance']['borrowed']
		for x in self.data['wallet']:
			D128_CTX = create_decimal128_context()
			with decimal.localcontext(D128_CTX):
				if( x['type'] == 'lent' ):
					if( x['currency'] in list(LentDict.keys()) ):
						LentDict[ x['currency'] ] = Decimal128( LentDict[ x['currency'] ].to_decimal() + x['amount'].to_decimal() )
						BalanceDict[ x['currency'] ] = Decimal128( BalanceDict[ x['currency'] ].to_decimal() + x['amount'].to_decimal() )
					else:
						LentDict[ x['currency'] ] = x['amount']
						BalanceDict[ x['currency'] ] = x['amount']
					count = count + 1
				elif( x['type'] == 'borrowed' ):
					if( x['currency'] in list(BorrowedDict.keys()) ):
						BorrowedDict[ x['currency'] ] = Decimal128( BorrowedDict[ x['currency'] ].to_decimal() + x['amount'].to_decimal() )
						BalanceDict[ x['currency'] ] = Decimal128( BalanceDict[ x['currency'] ].to_decimal() - x['amount'].to_decimal() )
					else:
						BorrowedDict[ x['currency'] ] = x['amount']
						BalanceDict[ x['currency'] ] = Decimal128('0.0')
						BalanceDict[ x['currency'] ] = Decimal128( BalanceDict[ x['currency'] ].to_decimal() - x['amount'].to_decimal() )
					count = count + 1
		if( count > 0 ):
			self.data['balance'] = dict()
			self.data['balance']['total'] = BalanceDict
			self.data['balance']['borrowed'] = BorrowedDict
			self.data['balance']['lent'] = LentDict
			qry = dict()
			qry['id'] = self.data['id']
			ret = self.handle.update_one( filter = qry, update = {'$set': {'balance':{'total': BalanceDict, 'borrowed': BorrowedDict, 'lent': LentDict} }})
			return ret.modified_count
		else:
			return 1
	def init_balance(self, default_currency, UIDObj = None):
		BalanceDict = dict()
		LentDict = dict()
		BorrowedDict = dict()
		if( UIDObj is None ):
			self.load( self.data['id'] )
		else:
			self.load( UIDObj )
		if((['total', 'borrowed', 'lent'] != self.data['balance'].keys()) or ( len(self.data['balance']['total']) == 0 ) and ( len(self.data['balance']['borrowed']) == 0 ) and ( len(self.data['balance']['lent']) == 0 )):
			D128_CTX = create_decimal128_context()
			with decimal.localcontext(D128_CTX):
				LentDict[ default_currency ] = Decimal128( '0.0' )
				BorrowedDict[ default_currency ] = Decimal128( '0.0' )
				BalanceDict[ default_currency ] = Decimal128( '0.0' )
				self.data['balance'] = dict()
				self.data['balance']['total'] = BalanceDict
				self.data['balance']['borrowed'] = BorrowedDict
				self.data['balance']['lent'] = LentDict
				qry = dict()
				qry['id'] = self.data['id']
				ret = self.handle.update_one( filter = qry, update = {'$set': {'balance':{'total': BalanceDict, 'borrowed': BorrowedDict, 'lent': LentDict} }})
			return ret.modified_count
		else:
			return 0
	def update_wallet(self, WalletDict, BaseID):
		qry = dict()
		qry['id'] = self.data['id']
		TempDict = WalletDict
		TempDict['baseid'] = BaseID
		ret = self.handle.update_one( filter = qry, update = {'$addToSet': {'wallet': TempDict}} )
		return ret.modified_count
	def pay(self, TxDict):
		WalletDict = dict()
		WalletDict['id'] = TxDict['id']
		WalletDict['settled'] = True
		WalletDict['type'] = 'paid'
		WalletDict['target'] = TxDict['payee']
		D128_CTX = create_decimal128_context()
		with decimal.localcontext(D128_CTX):
			WalletDict['amount'] = Decimal128( '0.0' )
			for x in TxDict['payer']:
				if( x['uid'] == self.data['id'] ):
					WalletDict['amount'] = Decimal128( WalletDict['amount'].to_decimal() + x['share'].to_decimal() )
				elif(( x['owes'] != False ) and ( x['owes'] == self.data['id'] ) ):
					WalletDict['amount'] = Decimal128( WalletDict['amount'].to_decimal() + x['share'].to_decimal() )
		WalletDict['currency'] = TxDict['currency']
		for x in self.data['wallet']:
			if( x['id'] == TxDict['id'] ):
				raise EngineException( 'TRANSACTION_ALREADY_LOGGED' )
		self.base = self.base_seqnext()
		ret = 0
		ret = ret + self.update_wallet( WalletDict, self.base )
		self.load( self.data['id'] )
		ret = ret + self.update_balance()
		with Users( self.conn ) as TempUsrObj:
			TempUsrObj.load( TxDict['payee'] )
			WalletDict['type'] = 'received'
			WalletDict['target'] = self.data['id']
			WalletDict['amount'] = WalletDict['amount']
			TempUsrObj.base = TempUsrObj.base_seqnext()
			ret = ret + TempUsrObj.update_wallet( WalletDict, TempUsrObj.base )
			TempUsrObj.load( TxDict['payee'] )
			ret = ret + TempUsrObj.update_balance()
		return ret
	def xfer(self, TxDict):
		WalletDict = dict()
		WalletDict['id'] = TxDict['id']
		WalletDict['settled'] = True
		WalletDict['type'] = 'xfer'
		WalletDict['target'] = TxDict['xfree']
		WalletDict['amount'] = TxDict['amount']
		WalletDict['currency'] = TxDict['currency']
		for x in self.data['wallet']:
			if( x['id'] == TxDict['id'] ):
				raise EngineException( 'TRANSACTION_ALREADY_LOGGED' )
		self.base = self.base_seqnext()
		ret = 0
		ret = ret + self.update_wallet( WalletDict, self.base )
		self.load( self.data['id'] )
		ret = ret + self.update_balance()
		with Users( self.conn ) as TempUsrObj:
			TempUsrObj.load( TxDict['xfree'] )
			WalletDict['type'] = 'xferred'
			WalletDict['target'] = self.data['id']
			WalletDict['amount'] = TxDict['amount']
			TempUsrObj.base = TempUsrObj.base_seqnext()
			ret = ret + TempUsrObj.update_wallet( WalletDict, TempUsrObj.base )
			TempUsrObj.load( TxDict['xfree'] )
			ret = ret + TempUsrObj.update_balance()
		return ret
	def lend_to(self, TxDict, BrwID):
		WalletDict = dict()
		WalletDict['id'] = TxDict['id']
		WalletDict['settled'] = False
		WalletDict['type'] = 'lent'
		WalletDict['target'] = BrwID
		for x in TxDict['payer']:
			if( x['uid'] == BrwID ):
				WalletDict['amount'] = x['share']
		WalletDict['currency'] = TxDict['currency']
		for x in self.data['wallet']:
			if( ( x['id'] == TxDict['id'] ) and ( x['type'] != 'paid' ) and ( x['type'] != 'received' ) ):
				raise EngineException( 'TRANSACTION_ALREADY_LOGGED' )
		self.base = self.base_seqnext()
		ret = 0
		ret = ret + self.update_wallet( WalletDict, self.base )
		self.load( self.data['id'] )
		ret = ret + self.update_balance()
		return ret
	def borrow_from(self, TxDict, LndID):
		WalletDict = dict()
		WalletDict['id'] = TxDict['id']
		WalletDict['settled'] = False
		WalletDict['type'] = 'borrowed'
		WalletDict['target'] = LndID
		for x in TxDict['payer']:
			if( x['uid'] == self.data['id'] ):
				WalletDict['amount'] = x['share']
		WalletDict['currency'] = TxDict['currency']
		for x in self.data['wallet']:
			if( ( x['id'] == TxDict['id'] ) and ( x['type'] != 'paid' ) and ( x['type'] != 'received' ) ):
				raise EngineException( 'TRANSACTION_ALREADY_LOGGED' )
		self.base = self.base_seqnext()
		ret = 0
		ret = ret + self.update_wallet( WalletDict, self.base )
		self.load( self.data['id'] )
		ret = ret + self.update_balance()
		return ret
	def gen_key(self):
		key = dict()
		key['key'] = secrets.token_hex( 28 )[:56]
		key['iv'] = binascii.hexlify( urandom(4) ).decode()
		return key
	def user_register(self, UsrObj):
		TempKey = self.gen_key()
		UserDict = dict()
		for x in UsrObj['phone']:
			if( self.handle.find_one( filter = {'phone':{'$in':UsrObj['phone']}}, projection = {'_id' : False} ) is not None ):
				raise EngineException( 'USER_ALREADY_REGISTERED' )
		UserDict['phone'] = UsrObj['phone']
		for x in UsrObj['mail']:
			if( ( len(x) > 0) and (self.handle.find_one( filter = {'mail':{'$in':UsrObj['mail']}}, projection = {'_id' : False} ) is not None ) ):
				raise EngineException( 'USER_ALREADY_REGISTERED' )
		UserDict['mail'] = UsrObj['mail']
		UserDict['pass'] = UsrObj['pass']
		UserDict['name'] = UsrObj['name']
		UserDict['key'] = TempKey
		UserDict['default_currency'] = UsrObj['default_currency']
		UserDict['balance'] = dict()
		UserDict['wallet'] = list()
		UserDict['base'] = Int64(0)
		UserDict['id'] = self.seqnext()
		self.handle.insert_one( UserDict )
		qry = dict()
		qry['id'] = UserDict['id']
		self.init_balance( UsrObj['default_currency'], qry['id'] )
		qry['public_key'] = TempKey
		return qry
	def get_info(self, ReqObj):
		self.load(ReqObj['uid'])
		ret = self.data
		ret.pop('pass', None)
		ret.pop('base', None)
		TempKey = ret.pop('key', None)
		if( TempKey['key'] == ReqObj['key'] ):
			return ret
		else:
			raise EngineException( 'AUTH_FAILED' )
	def key_auth(self, UIDObj, UKey):
		self.load(UIDObj)
		ret = self.data
		ret = ret.pop('key', None)
		if( ret['key'] == UKey ):
			return True
		else:
			raise EngineException( 'AUTH_FAILED' )
	def change_keys(self, UId, OldKey):
		self.load(UId)
		ret = self.data
		ret = ret.pop('key', None)
		if( ret['key'] == OldKey ):
			try:
				qry = dict()
				qry['id'] = self.data['id']
				NewKey = self.gen_key()
				ret = self.handle.update_one( filter = qry, update = {'$set': {'key': NewKey}})
				return NewKey
			except Exception as ex:
				raise EngineException( 'KEY_CHANGE_FAILED' )
		else:
			raise EngineException( 'AUTH_FAILED' )
	def __enter__(self):
		#
		# Context manager entry
		#
		return self
	def __exit__(self, type, value, traceback):
		#
		# Context manager exit
		# Closing connection resource if not extended
		#
		if( self.extended == False):
			self.conn.close()
