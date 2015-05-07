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

# pylint: disable=import-error,no-name-in-module

try: from urllib.parse import urlsplit
except ImportError: from urlparse import urlsplit

from dNG.pas.data.settings import Settings
from dNG.pas.net.tvheadend.client import Client
from dNG.pas.runtime.io_exception import IOException
from .abstract import Abstract

class TvheadendFile(Abstract):
#
	"""
"TvheadendFile" represents an Tvheadend recorded file.

:author:     direct Netware Group
:copyright:  direct Netware Group - All rights reserved
:package:    mp
:subpackage: tvheadend
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
	"""

	def __init__(self):
	#
		"""
Constructor __init__(TvheadendFile)

:since: v0.1.00
		"""

		Abstract.__init__(self)

		self.file_id = None
		"""
File ID of the opened Tvheadend file
		"""
		self.file_position = 0
		"""
File handle position calculated
		"""

		self.io_chunk_size = int(Settings.get("pas_global_io_chunk_size_remote", 1048576))

		self.supported_features['seeking'] = True
	#

	def close(self):
	#
		"""
Closes all related resource pointers for the active streamer session.

:return: (bool) True on success
:since: v0.1.00
		"""

		with self._lock:
		#
			client = Client.get_instance()

			if (client.is_active() and self.file_id is not None):
			#
				try: client.fileClose(id = self.file_id)
				except IOException: pass

				self.file_id = None
			#
		#

		return True
	#

	def get_size(self):
	#
		"""
Returns the size in bytes.

:return: (int) Size in bytes
:since:  v0.1.00
		"""

		client = Client.get_instance()

		with self._lock:
		#
			if (self.file_id is None): raise IOException("Streamer resource is invalid")
			return client.fileStat(id = self.file_id)['size']
		#
	#

	def is_eof(self):
	#
		"""
Checks if the resource has reached EOF.

:return: (bool) True if EOF
:since:  v0.1.00
		"""

		with self._lock:
		#
			return (self.file_id is None or self.file_position >= self.get_size())
		#
	#

	def is_resource_valid(self):
	#
		"""
Returns true if the streamer resource is available.

:return: (bool) True on success
:since:  v0.1.00
		"""

		return (self.file_id is not None)
	#

	def is_url_supported(self, url):
	#
		"""
Returns true if the streamer is able to return data for the given URL.

:param url: URL to be streamed

:return: (bool) True if supported
:since:  v0.1.00
		"""

		_return = True

		client = Client.get_instance()
		url_elements = urlsplit(url)

		try:
		#
			response = client.fileOpen(file = "/dvrfile/{0}".format(url_elements.path[1:]))
			client.fileClose(id = response['id'])
		#
		except IOException: _return = False

		return _return
	#

	def open_url(self, url):
	#
		"""
Opens a streamer session for the given URL.

:param url: URL to be streamed

:return: (bool) True on success
:since:  v0.1.00
		"""

		_return = False

		url_elements = urlsplit(url)

		if (url_elements.scheme == "tvheadend-file"):
		#
			client = Client.get_instance()

			with self._lock:
			#
				response = client.fileOpen(file = "/dvrfile/{0}".format(url_elements.path[1:]))
				self.file_id = response['id']
				self.file_position = 0
			#

			_return = True
		#

		return _return
	#

	def read(self, _bytes = None):
	#
		"""
Reads from the current streamer session.

:param _bytes: How many bytes to read from the current position (0 means
               until EOF)

:return: (bytes) Data; None if EOF
:since:  v0.1.00
		"""

		_return = None

		if (_bytes is None): _bytes = self.io_chunk_size
		client = Client.get_instance()

		with self._lock:
		#
			if (self.file_id is None): raise IOException("Streamer resource is invalid")

			_return = (client.fileRead(id = self.file_id, size = _bytes)['data']
			           if (client.is_active()) else
			           None
			          )

			if (_return is not None): self.file_position += len(_return)
		#

		return _return
	#

	def seek(self, offset):
	#
		"""
Seek to a given offset.

:param offset: Seek to the given offset

:return: (bool) True on success
:since:  v0.1.00
		"""

		_return = False

		client = Client.get_instance()
		if (not client.is_active()): raise IOException("Tvheadend client is not listening")

		with self._lock:
		#
			if (self.file_id is None): raise IOException("Streamer resource is invalid")

			self.file_position = client.fileSeek(id = self.file_id,
			                                     offset = offset, whence = "SEEK_SET"
			                                    )['offset']

			_return = True
		#

		return _return
	#

	def tell(self):
	#
		"""
Returns the current offset.

:return: (int) Offset
:since:  v0.1.00
		"""

		with self._lock:
		#
			if (self.file_id is None): raise IOException("Streamer resource is invalid")
			return self.file_position
		#
	#
#

##j## EOF