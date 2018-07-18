import json
import requests
import time
import decimal

from flask import Flask, render_template, request, url_for, jsonify
from pymongo import MongoClient
from flask_cors import CORS, cross_origin
from bson.int64 import Int64
from decimal import Decimal
from bson.decimal128 import Decimal128, create_decimal128_context

import users
import transactions

from users import Users, EngineException
from transactions import Transactions
from externlib import composite_tx_to_json
from externlib import composite_uinfo_to_json

app = Flask(__name__)

@app.route('/register/', methods=['POST'])
@cross_origin( origin = 'localhost' )
def register():
	ret = dict()
	try:
		RequestDict = dict()
		RequestDict['phone'] = request.form['phone']
		RequestDict['phone'] = RequestDict['phone'].split(',')
		RequestDict['mail'] = request.form['mail']
		RequestDict['mail'] = RequestDict['mail'].split(',')
		RequestDict['name'] = request.form['name']
		RequestDict['pass'] = request.form['pass']
		RequestDict['default_currency'] = request.form['default_currency']
		with MongoClient() as ConnResource:
			with Users( ConnResource ) as TempUsrObj:
				ret['data'] = TempUsrObj.user_register( RequestDict )
				ret['status'] = 'OK'
	except EngineException as ex:
		ret['status'] = str(ex)
	except Exception as ex:
		ret['status'] = 'MALFORMED_REQUEST'
	return jsonify( ret )

@app.route('/request/getinfo', methods=['POST'])
@cross_origin( origin = 'localhost' )
def userrequest():
	ret = dict()
	try:
		RequestDict = dict()
		RequestDict['uid'] = Int64( request.form['uid'] )
		RequestDict['key'] = request.form['key']
		with MongoClient() as ConnResource:
			with Users( ConnResource ) as TempUsrObj:
				ret['data'] = TempUsrObj.get_info( RequestDict )
				ret['data'] = composite_uinfo_to_json( ret['data'] )
				ret['status'] = 'OK'
	except EngineException as ex:
		ret['status'] = str(ex)
	except Exception as ex:
		ret['status'] = 'MALFORMED_REQUEST'
	return jsonify( ret )

@app.route('/request/changekeys', methods=['POST'])
@cross_origin( origin = 'localhost' )
def changekeys():
	ret = dict()
	try:
		RequestDict = dict()
		RequestDict['uid'] = Int64( request.form['uid'] )
		RequestDict['oldkey'] = request.form['oldkey']
		with MongoClient() as ConnResource:
			with Users( ConnResource ) as TempUsrObj:
				ret['data'] = TempUsrObj.change_keys(RequestDict['uid'], RequestDict['oldkey'])
				ret['status'] = 'OK'
	except EngineException as ex:
		ret['status'] = str(ex)
	except Exception as ex:
		ret['status'] = 'MALFORMED_REQUEST'
	return jsonify( ret )

@app.route('/request/newtx', methods=['POST'])
@cross_origin( origin = 'localhost' )
def newtransaction():
	ret = dict()
	try:
		RequestDict = dict()
		RequestDict['key'] = request.form['key']
		RequestDict['host'] = Int64( request.form['host'] )
		with MongoClient() as ConnResource:
			with Users( ConnResource ) as TempUsrObj:
				if( TempUsrObj.key_auth(RequestDict['host'], RequestDict['key']) is True ):
					if( Transactions.validate_nature(request.form['nature']) is True ):
						RequestDict['nature'] = request.form['nature']
					if( RequestDict['nature'] == 'payment' ):
						RequestDict['payee'] = request.form['payee']
						if( TempUsrObj.validate( RequestDict['payee'] ) == -1 ):
							raise EngineException( 'PAYEE_NOT_FOUND' )
						else:
							RequestDict['payee'] = TempUsrObj.validate( RequestDict['payee'] )
						RequestDict['payer'] = list()
						TempList1 = list()
						TempList2 = list()
						TempList3 = list()
						TempList1 = request.form['payer-uids'].split(',')
						TempList2 = request.form['payer-shares'].split(',')
						TempList3 = request.form['payer-owes'].split(',')
						if( (len(TempList1) != len(TempList2)) or (len(TempList2) != len(TempList3)) or (len(TempList3) != len(TempList1)) ):
							raise EngineException( 'PAYER_DATA_INVALID' )
						i = 0
						while( i<len(TempList1) ):
							TempDict = dict()
							TempDict['uid'] = TempList1[i]
							TempDict['share'] = TempList2[i]
							if( TempList3[i] != 'f' ):
								TempDict['owes'] = TempList3[i]
							else:
								TempDict['owes'] = False
							RequestDict['payer'].append( TempDict )
							i = i + 1
					elif( RequestDict['nature'] == 'transfer' ):
						RequestDict['xfree'] = request.form['payee']
						if( TempUsrObj.validate( RequestDict['xfree'] ) == -1 ):
							raise EngineException( 'XFREE_NOT_FOUND' )
						else:
							RequestDict['xfree'] = TempUsrObj.validate( RequestDict['xfree'] )
						RequestDict['xfrer'] = request.form['host']
					RequestDict['amount'] = request.form['amount']
					RequestDict['bills'] = request.form['bills'].split(',')
					RequestDict['notes'] = list()
					TempList1 = request.form['note-users'].split(',')
					TempList2 = request.form['note-notes'].split(',')
					if(len(TempList1) != len(TempList2)):
						raise EngineException( 'NOTES_DATA_INVALID' )
					i = 0
					while( i<len(TempList1) ):
						TempDict = dict()
						TempDict['user'] = TempList1[i]
						TempDict['note'] = TempList2[i]
						RequestDict['notes'].append( TempDict )
						i = i + 1
					RequestDict['currency'] = request.form['currency']
					if( len(request.form['assocs']) > 0 ):
						RequestDict['assoc'] = request.form['assocs'].split(',')
					else:
						RequestDict['assoc'] = list()
					RequestDict['datetime'] = int(time.time())
					with Transactions( ConnResource ) as TempTxObj:
						ret['data'] = TempTxObj.new( RequestDict )
						ret['checksum'] = TempTxObj.process( ret['data'] )
						ret['data'] = composite_tx_to_json( ret['data'] )
				#
				ret['status'] = 'OK'
	except EngineException as ex:
		ret['status'] = str(ex)
	except Exception as ex:
		ret['status'] = 'MALFORMED_REQUEST'
	return jsonify( ret )
