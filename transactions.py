import decimal

from pymongo import MongoClient
from bson.decimal128 import Decimal128, create_decimal128_context
from decimal import Decimal
from bson.int64 import Int64

import users

from users import EngineException
from users import Users

class Transactions:
	conn = None
	handle = None
	extended = False
	def seqnext(self):
		ret = None
		try:
			ret = self.handle.find_one_and_update( filter = { '_id': 'transactionseq' }, update = { '$inc': {'seq': Int64(1)}}, projection = {'_id': False} ).get('seq')
		except Exception as ex:
			self.handle.insert({'_id': "transactionseq", 'seq': Int64(1) })
			ret = self.handle.find_one_and_update( filter = { '_id': 'transactionseq' }, update = { '$inc': {'seq': Int64(1)}}, projection = {'_id': False} ).get('seq')
		return Int64(ret)
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
		if('transactions' not in handle.collection_names()):
			handle.create_collection('transactions')
			handle['transactions'].insert({'_id': "transactionseq", 'seq': Int64(1) })
		self.handle = handle['transactions']
	def validate(self, TxId, TxIsAssoc = False):
		qry = dict()
		try:
			qry['id'] = TxId
			data = self.handle.find_one( filter = qry, projection = {'_id' : False} )
			if(data is None):
				if( TxIsAssoc is True ):
					raise EngineException( 'ASSOC_TRANSACTION_NOT_FOUND' )
				else:
					raise EngineException( 'TRANSACTION_NOT_FOUND' )
			else:
				return TxId
		except Exception as ex:
			raise EngineException( 'TRANSACTION_NOT_FOUND' )
	@staticmethod
	def validate_nature(TxType):
		if(TxType in ['payment', 'transfer', 'settlement', 'refund']):
			return True
		else:
			raise EngineException( 'INVALID_NATURE' )
	def new(self, TxObj):
		TxDict = dict()
		try:
			TempUsrObj = Users( self.conn )
			TempUsrObj.load( TxObj['host'] )
			TxDict['host'] = TempUsrObj.resolve()
			TempUsrObj.load( TxObj['payee'] )
			TxDict['payee'] = TempUsrObj.resolve()
			TxDict['amount'] = Decimal128( TxObj['amount'] )
			TxDict['payer'] = list()
			ResolvedUIDList = list()
			AddedShareAmount = Decimal128( '0' )
			for x in TxObj['payer']:
				TempUsrObj.load( x['uid'] )
				ResolvedUIDList.append( TempUsrObj.resolve() )
			for x in TxObj['payer']:
				TempDict = dict()
				TempUsrObj.load( x['uid'] )
				TempDict['uid'] = TempUsrObj.resolve()
				TempDict['share'] = Decimal128( x['share'] )
				if( x['owes'] is not False):
					if( TempUsrObj.validate( x['owes'] ) not in ResolvedUIDList):
						raise EngineException( 'LENDER_NOT_PRESENT' )
					else:
						TempDict['owes'] = TempUsrObj.validate( x['owes'] )
				else:
					TempDict['owes'] = False
				TxDict['payer'].append( TempDict )
				D128_CTX = create_decimal128_context()
				with decimal.localcontext(D128_CTX):
					AddedShareAmount = Decimal128( AddedShareAmount.to_decimal() + TempDict['share'].to_decimal() )
			if( AddedShareAmount != TxDict['amount'] ):
				raise EngineException( 'SUM_NOT_EQUAL' )
			TxDict['bills'] = list()
			for x in TxObj['bills']:
				TxDict['bills'].append( x )
			TxDict['notes'] = list()
			for x in TxObj['notes']:
				TempDict = dict()
				TempUsrObj.load( x['user'] )
				TempDict['user'] = TempUsrObj.resolve()
				TempDict['note'] = x['note']
				TxDict['notes'].append( TempDict )
			TxDict['nature'] = TxObj['nature']
			TxDict['currency'] = TxObj['currency']
			TxDict['assoc'] = list()
			for x in TxObj['assoc']:
				TxDict['assoc'].append( self.validate(x, True) )
			TxDict['datetime'] = TxObj['datetime']
			return TxDict
		except EngineException as ex:
			raise ex
		except Exception as ex:
			raise EngineException( 'UNKNOWN_ERROR' )
	def process(self, TxDict):
		TempUsrObj = Users( self.conn )
		ret = None
		if( TxDict['nature'] == 'payment' ):
			TxDict['id'] = self.seqnext()
			ret = self.handle.insert_one( TxDict )
			for x in TxDict['payer']:
				if( x['owes'] == False ):
					TempUsrObj.load( x['uid'] )
					ret = TempUsrObj.pay( TxDict )
				else:
					TempUsrObj.load( x['uid'] )
					TempLenderUsrObj = Users( self.conn )
					TempLenderUsrObj.load( x['owes'] )
					ret = TempLenderUsrObj.lend_to( TxDict, x['uid'] )
					ret = ret + TempUsrObj.borrow_from( TxDict, x['owes'] )
		elif( TxDict['nature'] == 'transfer' ):
			TxDict['id'] = self.seqnext()
			ret = self.handle.insert_one( TxDict )
			TempUsrObj.load( TxDict['xfrer'] )
			ret = TempUsrObj.xfer( TxDict )
		elif( TxDict['nature'] == 'settlement' ):
			TxDict['id'] = self.seqnext()
			ret = self.handle.insert_one( TxDict )
			TempUsrObj.load( TxDict['xfrer'] )
			ret = TempUsrObj.xfer( TxDict )
		return ret
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
