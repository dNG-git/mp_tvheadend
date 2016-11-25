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

# pylint: disable=import-error,no-name-in-module

from dNG.data.binary import Binary
from dNG.data.settings import Settings
from dNG.data.upnp.resources.mp_entry_pvr_recording import MpEntryPvrRecording
from dNG.database.connection import Connection
from dNG.plugins.hook import Hook
from dNG.runtime.io_exception import IOException
from dNG.runtime.thread_lock import ThreadLock
from dNG.vfs.abstract import Abstract

from mp.net.tvheadend.client import Client
from dNG.database.nothing_matched_exception import NothingMatchedException

class Object(Abstract):
    """
Provides the VFS implementation for 'x-tvheadend' objects.

:author:     direct Netware Group et al.
:copyright:  direct Netware Group - All rights reserved
:package:    mp
:subpackage: tvheadend
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
    """

    def __init__(self):
        """
Constructor __init__(TvheadendFile)

:since: v0.1.00
        """

        Abstract.__init__(self)

        self.dvr_id = None
        """
Tvheadend DVR entry ID
        """
        self.handle_id = None
        """
File ID of the opened Tvheadend file
        """
        self.handle_position = 0
        """
File handle position calculated
        """
        self._lock = ThreadLock()
        """
Thread safety lock
        """
        self.vfs_type = None
        """
VFS type
        """

        self.supported_features['seek'] = self._supports_handle
        self.supported_features['time_updated'] = self._supports_handle
    #

    def close(self):
        """
python.org: Flush and close this stream.

:since: v0.1.00
        """

        client = Client.get_instance()

        try:
            if (self.handle_id is not None
                and client.is_active()
               ): client.fileClose(id = self.handle_id)
        finally:
            self.dvr_id = None
            self.handle_id = None
            self.vfs_type = None
        #
    #

    def _ensure_handle_opened(self):
        """
Checks the Tvheadend recording status and an opened file handle. This method
only requests one if the recording status indicates that it is available.

:return: (str) Implementing scheme name
:since:  v0.1.00
        """

        if (self.vfs_type is None): raise IOException("VFS object not opened")

        if (self.handle_id is None and self._supports_handle()):
            client = Client.get_instance()
            if (not client.is_active()): raise IOException("Tvheadend client is not listening")

            with self._lock:
                # Thread safety
                if (self.handle_id is None):
                    self.handle_id = client.fileOpen(file = "/dvrfile/{0}".format(self.dvr_id))['id']
                #
            #
        #
    #

    def get_implementing_scheme(self):
        """
Returns the implementing scheme name.

:return: (str) Implementing scheme name
:since:  v0.1.00
        """

        return "x-tvheadend"
    #

    def get_name(self):
        """
Returns the name of this VFS object.

:return: (str) VFS object name
:since:  v0.1.00
        """

        _return = None

        client = Client.get_instance()
        if (not client.is_active()): raise IOException("Tvheadend client is not listening")

        if (self.vfs_type == Object.TYPE_DIRECTORY): _return = client.get_server_name()
        elif (self.vfs_type == Object.TYPE_FILE): _return = "/dvrfile/{0}".format(self.dvr_id)
        else: raise IOException("VFS object not opened")

        return _return
    #

    def get_size(self):
        """
Returns the size in bytes.

:return: (int) Size in bytes
:since:  v0.1.00
        """

        _return = None

        client = Client.get_instance()
        if (not client.is_active()): raise IOException("Tvheadend client is not listening")

        if (self.vfs_type == Object.TYPE_DIRECTORY): _return = 0
        elif (self.vfs_type == Object.TYPE_FILE):
            self._ensure_handle_opened()
            _return = (0 if (self.handle_id is None) else client.fileStat(id = self.handle_id)['size'])
        else: raise IOException("VFS object not opened")

        return _return
    #

    def get_time_created(self):
        """
Returns the UNIX timestamp this object was created.

:return: (int) UNIX timestamp this object was created
:since:  v0.1.00
        """

        return self.get_time_updated()
    #

    def get_time_updated(self):
        """
Returns the UNIX timestamp this object was updated.

:return: (int) UNIX timestamp this object was updated
:since:  v0.1.00
        """

        _return = None

        client = Client.get_instance()
        if (not client.is_active()): raise IOException("Tvheadend client is not listening")

        if (self.vfs_type == Object.TYPE_DIRECTORY): _return = Hook.call("dNG.pas.Status.getTimeStarted")
        elif (self.vfs_type == Object.TYPE_FILE):
            self._ensure_handle_opened()

            _return = (Hook.call("dNG.pas.Status.getTimeStarted")
                       if (self.handle_id is None) else
                       client.fileStat(id = self.handle_id)['mtime']
                      )
        else: raise IOException("VFS object not opened")

        return _return
    #

    def get_type(self):
        """
Returns the type of this object.

:return: (int) Object type
:since:  v0.1.00
        """

        if (self.vfs_type is None): raise IOException("VFS object not opened")
        return self.vfs_type
    #

    def get_url(self):
        """
Returns the URL of this VFS object.

:return: (str) VFS URL
:since:  v0.1.00
        """

        _return = None

        if (self.vfs_type == Object.TYPE_DIRECTORY): _return = "x-tvheadend:///"
        elif (self.vfs_type == Object.TYPE_FILE): _return = "x-tvheadend:///{0}".format(self.dvr_id)
        else: raise IOException("VFS object not opened")

        return _return
    #

    def is_eof(self):
        """
Checks if the pointer is at EOF.

:return: (bool) True on success
:since:  v0.1.00
        """

        self._ensure_handle_opened()
        return (self.handle_id is None or self.handle_position >= self.get_size())
    #

    def is_valid(self):
        """
Returns true if the object is available.

:return: (bool) True on success
:since:  v0.1.00
        """

        _return = (self.vfs_type is not None and Client.get_instance().is_active())

        if (self.vfs_type == Object.TYPE_FILE):
            self._ensure_handle_opened()
            _return = (self.handle_id is not None)
        #

        return _return
    #

    def open(self, vfs_url, readonly = False):
        """
Opens a VFS object. The handle is set at the beginning of the object.

:param vfs_url: VFS URL
:param readonly: Open object in readonly mode

:since: v0.1.00
        """

        client = Client.get_instance()
        if (not client.is_active()): raise IOException("Tvheadend client is not listening")

        vfs_url = Binary.str(vfs_url)
        dvr_id = Object._get_id_from_vfs_url(vfs_url)

        if (dvr_id == ""): self.vfs_type = Object.TYPE_DIRECTORY
        else:
            self.dvr_id = dvr_id
            self.handle_position = 0
            self.vfs_type = Object.TYPE_FILE
        #
    #

    def read(self, n = 0, timeout = -1):
        """
python.org: Read up to n bytes from the object and return them.

:param n: How many bytes to read from the current position (0 means until
          EOF)
:param timeout: Timeout to use (if supported by implementation)

:return: (bytes) Data; None if EOF
:since:  v0.1.00
        """

        _return = None
        if (self.vfs_type != Object.TYPE_FILE): raise IOException("VFS object not opened")

        self._ensure_handle_opened()

        if (self.handle_id is not None):
            if (n is None or n < 1): n = int(Settings.get("pas_global_io_chunk_size_local_network", 1048576))

            client = Client.get_instance()

            _return = (client.fileRead(id = self.handle_id, size = n)['data']
                       if (client.is_active()) else
                       None
                      )

            if (_return is not None): self.handle_position += len(_return)
        #

        return _return
    #

    def seek(self, offset):
        """
python.org: Change the stream position to the given byte offset.

:param offset: Seek to the given offset

:return: (int) Return the new absolute position.
:since:  v0.1.00
        """

        if (self.vfs_type != Object.TYPE_FILE): raise IOException("VFS object not opened")

        self._ensure_handle_opened()

        if (self.handle_id is not None):
            client = Client.get_instance()

            self.handle_position = client.fileSeek(id = self.handle_id,
                                                   offset = offset,
                                                   whence = "SEEK_SET"
                                                  )['offset']
        #

        return self.handle_position
    #

    def _supports_handle(self):
        """
Returns false if an handle for the VFS object can not be obtained.

:return: (bool) True if an handle for the VFS object can be obtained
:since:  v0.2.00
        """

        _return = (self.handle_id is not None)

        if ((not _return) and self.vfs_type == Object.TYPE_FILE):
            with Connection.get_instance():
                try:
                    resource = MpEntryPvrRecording.load_resource(self.get_url())
                    resource_recording_status = resource.get_data_attributes("recording_status")['recording_status']
                except NothingMatchedException: resource_recording_status = None
            #

            _return = (resource_recording_status in ( MpEntryPvrRecording.RECORDING_STATUS_FINISHED,
                                                      MpEntryPvrRecording.RECORDING_STATUS_RECORDING
                                                    )
                      )
        #

        return _return
    #

    def tell(self):
        """
python.org: Return the current stream position as an opaque number.

:return: (int) Stream position
:since:  v0.1.00
        """

        if (self.vfs_type != Object.TYPE_FILE): raise IOException("VFS object not opened")
        return self.handle_position
    #
#
