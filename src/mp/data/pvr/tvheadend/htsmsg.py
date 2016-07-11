# -*- coding: utf-8 -*-
##j## BOF

"""
MediaProvider
A device centric multimedia solution
----------------------------------------------------------------------------
(C) direct Netware Group - All rights reserved
https://www.direct-netware.de/redirect?mp;tvheadend

The following license agreement remains valid unless any additions or
changes are being made by direct Netware Group in a written form.

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
----------------------------------------------------------------------------
https://www.direct-netware.de/redirect?licenses;gpl
----------------------------------------------------------------------------
#echo(mpTvheadendVersion)#
#echo(__FILEPATH__)#
"""

from struct import pack, unpack

from dNG.data.binary import Binary
from dNG.data.settings import Settings
from dNG.runtime.io_exception import IOException
from dNG.runtime.socket_reader import SocketReader
from dNG.runtime.type_exception import TypeException
from dNG.runtime.value_exception import ValueException

from .htsbin import Htsbin

class Htsmsg(dict):
#
	"""
Wrapper for a HTSMSG encoded message.

:author:     direct Netware Group et al.
:copyright:  direct Netware Group - All rights reserved
:package:    mp
:subpackage: tvheadend
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
	"""

	BINARY_NULL_BYTE = Binary.bytes("\x00")
	"""
NULL byte encoded
	"""
	FIELD_NAME_LENGTH_SIZE = 1
	"""
Field name size in bytes
	"""
	FIELD_VALUE_LENGTH_SIZE = 4
	"""
Field value size in bytes
	"""
	MESSAGE_LENGTH_SIZE = 4
	"""
Length field size in bytes
	"""
	TYPE_ID_SIZE = 1
	"""
Type ID size in bytes
	"""
	TYPE_MAP = 1
	"""
Map (dict) type
	"""
	TYPE_S64 = 2
	"""
Signed 64bit integer
	"""
	TYPE_STR = 3
	"""
UTF-8 encoded string
	"""
	TYPE_BIN = 4
	"""
Binary string
	"""
	TYPE_LIST = 5
	"""
List type
	"""

	def export(self):
	#
		"""
Exports a HTSMSG encoded message from this dict.

:return: HTSMSG encoded message
:since:  v0.1.00
		"""

		header_size = Htsmsg.TYPE_ID_SIZE + Htsmsg.FIELD_NAME_LENGTH_SIZE + Htsmsg.FIELD_VALUE_LENGTH_SIZE

		data = Htsmsg._encode(self)[header_size:]
		return pack("!I", len(data)) + data
	#

	@staticmethod
	def _decode(data, parent_element):
	#
		"""
Decodes binary HTSMSG field data.

:param data: HTSMSG field data

:return: (mixed) Field content
:since:  v0.1.00
		"""

		_return = parent_element
		parent_element_type = type(parent_element)

		data_position = 0
		data_size = len(data)
		header_size = Htsmsg.TYPE_ID_SIZE + Htsmsg.FIELD_NAME_LENGTH_SIZE + Htsmsg.FIELD_VALUE_LENGTH_SIZE

		if (data_size > 0 and data_size < header_size): raise ValueException("HTSMSG is invalid")

		while ((data_size - data_position) > header_size):
		#
			header_data = unpack("!BBI", data[data_position:data_position + header_size])
			field_size = header_size + header_data[1] + header_data[2]
			if (field_size > data_size): raise IOException("Malformed HTSMSG field")

			field = data[data_position + header_size:data_position + field_size]
			data_position += field_size

			if (header_data[0] == Htsmsg.TYPE_BIN): field_value = Htsbin(field[header_data[1]:])
			elif (header_data[0] == Htsmsg.TYPE_LIST): field_value = Htsmsg._decode(field[header_data[1]:], [ ])
			elif (header_data[0] == Htsmsg.TYPE_S64):
			#
				field_value = unpack("!Q", field[header_data[1]:][::-1].rjust(8, Htsmsg.BINARY_NULL_BYTE))[0]
				if (field_value == 0xffffffffffffffff): field_value = -1
			#
			elif (header_data[0] == Htsmsg.TYPE_STR): field_value = Binary.str(field[header_data[1]:])
			elif (header_data[0] == Htsmsg.TYPE_MAP): field_value = Htsmsg._decode(field[header_data[1]:], { })

			if (parent_element_type is dict):
			#
				if (header_data[1] < 1): raise IOException("Malformed HTSMSG field name")
				field_name = Binary.str(field[:header_data[1]])
				_return[field_name] = field_value
			#
			elif (parent_element_type is list): _return.append(field_value)
			else: _return = field_value
		#

		return _return
	#

	@staticmethod
	def _encode(data, field_name = None):
	#
		"""
Decodes binary HTSMSG field data.

:param data: HTSMSG field data

:return: (mixed) Field content
:since:  v0.1.00
		"""

		if (isinstance(data, dict)):
		#
			field_value = Binary.BYTES_TYPE()

			for data_key in data:
			#
				field_value += Htsmsg._encode(data[data_key], field_name = data_key)
			#

			_return = Htsmsg._encode_field(Htsmsg.TYPE_MAP,
			                               field_name,
			                               field_value
			                              )
		#
		elif (isinstance(data, Htsbin)): _return += Htsmsg._encode_field(Htsmsg.TYPE_BIN, field_name, data)
		elif (isinstance(data, list)):
		#
			field_value = Binary.BYTES_TYPE()
			for entry in data: field_value += Htsmsg._encode(entry)
			_return = Htsmsg._encode_field(Htsmsg.TYPE_LIST, field_name, field_value)
		#
		else:
		#
			if (type(data) in ( int, float )):
			#
				if (data < -1 or data > 0xfffffffffffffffe): raise ValueException("Numeric value is not supported by HTSMSG")
				if (data == -1): data = 0xffffffffffffffff

				if (data == 0): data = "\x00"
				else:
				#
					data = pack("!Q", data)
					data = data.lstrip(Htsmsg.BINARY_NULL_BYTE)[::-1]
				#

				_return = Htsmsg._encode_field(Htsmsg.TYPE_S64, field_name, data)
			#
			elif (isinstance(data, str)): _return = Htsmsg._encode_field(Htsmsg.TYPE_STR, field_name, Binary.bytes(data))
			else: raise TypeException("Object type is not supported for HTSMSG")
		#

		return _return
	#

	@staticmethod
	def _encode_field(_type, field_name, value):
	#
		"""
Encodes the HTSMSG field data given.

:param data: HTSMSG field data

:return: (mixed) Field content
:since:  v0.1.00
		"""

		field_name_size = (0 if (field_name is None) else len(field_name))
		_return = pack("!BBI", _type, field_name_size, len(value))

		if (field_name is not None): _return += Binary.bytes(field_name)
		_return += Binary.bytes(value)

		return _return
	#

	@staticmethod
	def import_message(message):
	#
		"""
Imports a HTSMSG encoded message into this dict.

:param message: HTSMSG encoded message

:return: (object) HTSMSG instance
:since:  v0.1.00
		"""

		message = Binary.bytes(message)
		message_size = len(message)

		if (type(message) is not Binary.BYTES_TYPE): raise TypeException("HTSMSG type given is invalid")
		if (message_size < Htsmsg.MESSAGE_LENGTH_SIZE): raise ValueException("HTSMSG is invalid")

		size = unpack("!I", message[:Htsmsg.MESSAGE_LENGTH_SIZE])[0]

		if ((message_size - Htsmsg.MESSAGE_LENGTH_SIZE) != size): raise IOException("Malformed HTSMSG body")

		return Htsmsg(Htsmsg._decode(message[Htsmsg.MESSAGE_LENGTH_SIZE:], { }))
	#

	@staticmethod
	def import_socket_data(_socket):
	#
		"""
Imports a HTSMSG encoded message into this dict.

:param message: HTSMSG encoded message

:return: (object) HTSMSG instance
:since:  v0.1.00
		"""

		timeout = int(Settings.get("mp_tvheadend_client_socket_data_timeout", 0))
		if (timeout < 1): timeout = int(Settings.get("pas_global_client_socket_data_timeout", 0))

		socket_reader = SocketReader(_socket, timeout)

		message = socket_reader.recv(Htsmsg.MESSAGE_LENGTH_SIZE)
		message_size = len(message)

		if (message_size < Htsmsg.MESSAGE_LENGTH_SIZE): raise ValueException("HTSMSG is invalid")

		message_length = unpack("!I", message)[0]
		message += socket_reader.recv(message_length)

		if (len(message) != Htsmsg.MESSAGE_LENGTH_SIZE + message_length):
		#
			raise IOException("Malformed HTSMSG body")
	#

		return Htsmsg.import_message(message)
	#
#

##j## EOF