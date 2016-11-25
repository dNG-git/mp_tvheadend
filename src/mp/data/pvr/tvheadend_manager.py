# -*- coding: utf-8 -*-

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
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
----------------------------------------------------------------------------
https://www.direct-netware.de/redirect?licenses;gpl
----------------------------------------------------------------------------
#echo(mpTvheadendVersion)#
#echo(__FILEPATH__)#
"""

from weakref import ref

from dNG.data.tasks.memory import Memory as MemoryTasks
from dNG.data.upnp.resources.mp_entry_pvr_recording import MpEntryPvrRecording
from dNG.database.connection import Connection
from dNG.plugins.hook import Hook
from dNG.runtime.thread_lock import ThreadLock

from mp.net.tvheadend.client import Client
from mp.tasks.resource_deleter import ResourceDeleter
from mp.tasks.resource_pvr_recording_tvheadend_refresh import ResourcePvrRecordingTvheadendRefresh

from .abstract_manager import AbstractManager

class TvheadendManager(AbstractManager):
    """
Tvheadend PVR manager.

:author:     direct Netware Group et al.
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
        """
Called for "mp.pvr.tvheadend.Client.onEvent"

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
        """

        if ("message" in params and "method" in params['message']):
            message = params['message']
            method = message['method']

            if (method in ( "dvrEntryAdd", "dvrEntryUpdate" )):
                _id = message['id']

                MemoryTasks.get_instance().add("mp.tasks.ResourcePvrRecordingTvheadendRefresh.{0}".format(_id),
                                               ResourcePvrRecordingTvheadendRefresh(self.get_container(), message, self.get_name()),
                                               0
                                              )

                if (self.recordings_cache is not None):
                    with self._lock:
                        # Thread safety
                        if (self.recordings_cache is not None): self.recordings_cache.append("{0}:///{1}".format(self.get_vfs_scheme(), _id))
                    #
                #
            elif (method == "dvrEntryDelete"):
                _id = message['id']
                resource = "{0}:///{1}".format(self.get_vfs_scheme(), _id)

                MemoryTasks.get_instance().add("mp.tasks.ResourceDeleter.{0}".format(_id),
                                               ResourceDeleter(resource),
                                               0
                                              )

                if (self.recordings_cache is not None):
                    with self._lock:
                        # Thread safety
                        if (self.recordings_cache is not None
                            and _id in self.recordings_cache
                           ): self.recordings_cache.remove(resource)
                    #
                #
            elif (method == "initialSyncCompleted"):
                with Connection.get_instance():
                    container = self.get_container()
                    children = container.get_content_list_of_type(MpEntryPvrRecording.TYPE_CDS_ITEM)

                    with self._lock:
                        for entry in children:
                            if (isinstance(entry, MpEntryPvrRecording)):
                                entry_data = entry.get_data_attributes("id", "vfs_url")

                                if (entry_data['vfs_url'] not in self.recordings_cache):
                                    MemoryTasks.get_instance().add("mp.tasks.ResourceDeleter.{0}".format(entry_data['id']),
                                                                   ResourceDeleter(entry_data['vfs_url']),
                                                                   0
                                                                  )
                                #
                            #
                        #
                    #
                #

                with self._lock: self.recordings_cache = None
            #
        #
    #

    def get_vfs_scheme(self):
        """
Returns the PVR manager VFS scheme.

:return: (str) PVR manager VFS scheme
:since:  v0.1.00
        """

        return "x-tvheadend"
    #

    def start(self, params = None, last_return = None):
        """
Starts the activity of this manager.

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
        """

        Hook.register("mp.pvr.tvheadend.Client.onEvent", self._handle_event)

        self.client = Client.get_instance()
        self.client.start()
        self.client.enableAsyncMetadata()

        self.name = self.client.get_server_name()

        AbstractManager.start(self, params, last_return)

        return last_return
    #

    def stop(self, params = None, last_return = None):
        """
Stops the activity of this manager.

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
        """

        if (self.client is not None):
            self.client.stop()
            self.client = None

            Hook.unregister("mp.pvr.tvheadend.Client.onEvent", self._handle_event)
        #

        return last_return
    #

    @staticmethod
    def get_instance():
        """
Get the TvheadendManager singleton.

:return: (TvheadendManager) Object on success
:since:  v0.1.00
        """

        _return = None

        with TvheadendManager._instance_lock:
            if (TvheadendManager._weakref_instance is not None): _return = TvheadendManager._weakref_instance()

            if (_return is None):
                _return = TvheadendManager()
                TvheadendManager._weakref_instance = ref(_return)
            #
        #

        return _return
    #
#
