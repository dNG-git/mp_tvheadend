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

from weakref import ref

from dNG.pas.data.tasks.memory import Memory as MemoryTasks
from dNG.pas.data.upnp.resources.mp_entry_pvr_recording import MpEntryPvrRecording
from dNG.pas.net.tvheadend.client import Client
from dNG.pas.plugins.hook import Hook
from dNG.pas.runtime.thread_lock import ThreadLock
from dNG.pas.tasks.mp.resource_deleter import ResourceDeleter
from dNG.pas.tasks.mp.resource_pvr_recording_tvheadend_refresh import ResourcePvrRecordingTvheadendRefresh
from .abstract_manager import AbstractManager

class TvheadendManager(AbstractManager):
#
	"""
Tvheadend PVR manager.

:author:     direct Netware Group
:copyright:  direct Netware Group - All rights reserved
:package:    mp
:subpackage: tvheadend
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
	"""

	id = "tvheadend"
	"""
PVR manager identifier
	"""

	def __init__(self):
	#
		"""
Constructor __init__(TvheadendManager)

:since: v0.1.00
		"""

		AbstractManager.__init__(self)

		self.client = None
		"""
Tvheadend client instance
		"""
		self._lock = ThreadLock()
		"""
Thread safety lock
		"""
		self.recordings_cache = [ ]
		"""
Cached list of synchronized recordings
		"""
	#

	def _handle_event(self, params, last_return = None):
	#
		"""
Called for "dNG.mp.tvheadend.Client.onEvent"

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
		"""

		if ("message" in params and "method" in params['message']):
		#
			message = params['message']
			method = message['method']

			if (method in ( "dvrEntryAdd", "dvrEntryUpdate" )):
			#
				_id = message['id']

				MemoryTasks.get_instance().add("dNG.pas.tasks.mp.ResourcePvrRecordingTvheadendRefresh.{0}".format(_id),
				                               ResourcePvrRecordingTvheadendRefresh(self.get_container(), message, self.get_name()),
				                               0
				                              )

				if (self.recordings_cache is not None):
				# Thread safety
					with self._lock:
					#
						if (self.recordings_cache is not None): self.recordings_cache.append("tvheadend-file:///{0}".format(_id))
					#
				#
			#
			elif (method == "dvrEntryDelete"):
			#
				_id = message['id']
				resource = "tvheadend-file:///{0}".format(_id)

				MemoryTasks.get_instance().add("dNG.pas.tasks.mp.ResourceDeleter.{0}".format(_id),
				                               ResourceDeleter(resource),
				                               0
				                              )

				if (self.recordings_cache is not None):
				# Thread safety
					with self._lock:
					#
						if (self.recordings_cache is not None
						    and _id in self.recordings_cache
						   ): self.recordings_cache.remove(resource)
					#
				#
			#
			elif (method == "initialSyncCompleted"):
			#
				container = self.get_container()
				children = container.get_content_list_of_type(MpEntryPvrRecording.TYPE_CDS_ITEM)

				for entry in children:
				#
					if (isinstance(entry, MpEntryPvrRecording)):
					#
						entry_data = entry.get_data_attributes("id", "resource")

						if (entry_data['resource'] not in self.recordings_cache):
						#
							MemoryTasks.get_instance().add("dNG.pas.tasks.mp.ResourceDeleter.{0}".format(entry_data['id']),
							                               ResourceDeleter(entry_data['resource']),
							                               0
							                              )
						#
					#
				#

				with self._lock: self.recordings_cache = None
			#
		#
	#

	def start(self, params = None, last_return = None):
	#
		"""
Starts the activity of this manager.

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
		"""

		Hook.register("dNG.mp.tvheadend.Client.onEvent", self._handle_event)

		self.client = Client.get_instance()
		self.client.start()
		self.client.enableAsyncMetadata()

		self.name = self.client.get_server_name()

		AbstractManager.start(self, params, last_return)

		return last_return
	#

	def stop(self, params = None, last_return = None):
	#
		"""
Stops the activity of this manager.

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
		"""

		if (self.client is not None):
		#
			self.client.stop()
			self.client = None

			Hook.unregister("dNG.mp.tvheadend.Client.onEvent", self._handle_event)
		#

		return last_return
	#

	@staticmethod
	def get_instance():
	#
		"""
Get the TvheadendManager singleton.

:return: (TvheadendManager) Object on success
:since:  v0.1.00
		"""

		_return = None

		with TvheadendManager._instance_lock:
		#
			if (TvheadendManager._weakref_instance is not None): _return = TvheadendManager._weakref_instance()

			if (_return is None):
			#
				_return = TvheadendManager()
				TvheadendManager._weakref_instance = ref(_return)
			#
		#

		return _return
	#
#

##j## EOF