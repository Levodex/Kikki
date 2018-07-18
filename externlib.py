import binascii
import blowfish
import hmac
import decimal

from json import JSONEncoder
from decimal import Decimal
from bson.decimal128 import Decimal128, create_decimal128_context

#
#	External Library
#

#
#	CryptoWrapper - Wrapper for OFB BlowFish with IV
#
class CryptoWrapper(object):
	cipher = ""
	vector = ""
	def __init__(self, hash, vector):
		self.cipher = blowfish.Cipher(bytes(hash, "utf8"))
		self.vector = vector
	def getcode(self):
		return self.vector
	def setcode(self, data):
		self.vector = data
	def __enter__(self):
		return self
	def __exit__(self, type, value, traceback):
		pass
	def encrypt(self, data):
		return binascii.hexlify(b"".join(self.cipher.encrypt_ofb(bytes(data, "utf8"), self.vector)))
	def decrypt(self, data):
		return (b"".join(self.cipher.decrypt_ofb(binascii.unhexlify(data), self.vector))).decode("utf8")
#

#
# Code to JSON Serialize Decimal128 in transactions
#
import simplejson as json
def composite_tx_to_json( composite ):
	ret = None
	D128_CTX = create_decimal128_context()
	with decimal.localcontext(D128_CTX):
		ret = composite
		ret.pop('_id', None)
		ret['amount'] = ret['amount'].to_decimal()
		length = len( ret['payer'] )
		i = 0
		while( i < length ):
			ret['payer'][i]['share'] = ret['payer'][i]['share'].to_decimal()
			i = i + 1
	return ret

#
# Code to JSON Serialize Decimal128 in User Objects
#
import simplejson as json
def composite_uinfo_to_json( composite ):
	ret = None
	D128_CTX = create_decimal128_context()
	with decimal.localcontext(D128_CTX):
		ret = composite
		ret.pop('_id', None)
		length = len( ret['wallet'] )
		i = 0
		while( i < length ):
			ret['wallet'][i]['amount'] = ret['wallet'][i]['amount'].to_decimal()
			i = i + 1
		for x in ret['balance']['total']:
			ret['balance']['total'][x] = ret['balance']['total'][x].to_decimal()
		for x in ret['balance']['borrowed']:
			ret['balance']['borrowed'][x] = ret['balance']['borrowed'][x].to_decimal()
		for x in ret['balance']['lent']:
			ret['balance']['lent'][x] = ret['balance']['lent'][x].to_decimal()
	return ret