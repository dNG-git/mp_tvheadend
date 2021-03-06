# -*- coding: utf-8 -*-

"""
MediaProvider
A device centric multimedia solution
----------------------------------------------------------------------------
(C) direct Netware Group - All rights reserved
https://www.direct-netware.de/redirect?mp;core

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
#echo(mpCoreVersion)#
#echo(__FILEPATH__)#
"""

from time import time

from dNG.data.settings import Settings
from dNG.data.tasks.memory import Memory as MemoryTasks
from dNG.data.upnp.resources.mp_entry_pvr_recording import MpEntryPvrRecording
from dNG.database.connection import Connection
from dNG.database.nothing_matched_exception import NothingMatchedException
from dNG.database.transaction_context import TransactionContext
from dNG.plugins.hook import Hook
from dNG.runtime.value_exception import ValueException
from dNG.tasks.abstract_lrt_hook import AbstractLrtHook

from mp.net.tvheadend.client import Client

from .resource_metadata_refresh import ResourceMetadataRefresh

class ResourcePvrRecordingTvheadendRefresh(AbstractLrtHook):
    """
"ResourcePvrRecordingTvheadendRefresh" is responsible of refreshing the
resource's metadata based on the TvHeadend message.

:author:     direct Netware Group et al.
:copyright:  direct Netware Group - All rights reserved
:package:    mp
:subpackage: core
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
    """

    def __init__(self, upnp_container, message, recorder_name):
        """
Constructor __init__(ResourcePvrRecordingTvheadendRefresh)

:since: v0.1.00
        """

        AbstractLrtHook.__init__(self)

        self.message = message
        """
TvHeadend message
        """
        self.recorder_name = recorder_name
        """
TvHeadend recorder name
        """
        self.upnp_container = upnp_container
        """
UPnP container resource
        """

        self.context_id = "mp.tasks.ResourcePvrRecordingTvheadendRefresh"
    #

    def _get_recording_details(self):
        """
Returns EPG details for the recording identified by the given HTSP message.

:return: (dict) EPG data on match; None otherwise
:since:  v0.1.00
        """

        _return = None

        client = None

        if (("stop" not in self.message or self.message['stop'] >= time())
            and "eventId" in self.message
           ):
            client = Client.get_instance()

            try: _return = client.get_epg_event_details(self.message['eventId'])
            except ValueException: pass
        #

        if (_return is None and "channel" in self.message and "start" in self.message and "stop" in self.message):
            if (client is None): client = Client.get_instance()

            try:
                _return = client.get_epg_details(self.message['channel'],
                                                 self.message['start'],
                                                 self.message['stop'],
                                                 self.message.get("title")
                                                )
            except ValueException: pass
        #

        return _return
    #

    def _process_recording_details(self, recording_details):
        """
Processes recording details and builds the internal title used for sorting.

:param recording_details: EPG data or HTSP message

:return: (dict) Processed recording details
:since:  v0.1.00
        """

        _return = None

        if (Settings.get("mp_tvheadend_recording_details_custom_processing", False)):
            _return = Hook.call("mp.pvr.tvheadend.MpPvrRecording.processRecordingDetails", details = recording_details)
        #

        if (_return is None and "title" in recording_details):
            _return = recording_details

            if ("subtitle" in recording_details):
                _return['title'] = "{0} - {1}".format(recording_details['title'],
                                                      recording_details['subtitle']
                                                     )

                _return['resource_title'] = recording_details['title']
            elif ("resource_title" not in _return): _return['resource_title'] = recording_details['title']
        #

        return _return
    #

    @Connection.wrap_callable
    def _run_hook(self):
        """
Hook execution

:since: v0.1.00
        """

        _id = self.message['id']
        entry_id = None
        is_refreshable = False
        recording_details = None
        recording_status = ResourcePvrRecordingTvheadendRefresh._get_recording_status(self.message)
        vfs_url = "x-tvheadend:///{0}".format(_id)

        try:
            recording_details = (self.message
                                 if ("description" in self.message
                                     or "subtitle" in self.message
                                     or "summary" in self.message
                                    ) else
                                 self._get_recording_details()
                                )

            entry = MpEntryPvrRecording.load_resource(vfs_url)
            entry_id = entry.get_resource_id()

            entry_data = entry.get_data_attributes("refreshable", "recording_status")
            is_refreshable = (recording_status == MpEntryPvrRecording.RECORDING_STATUS_FINISHED)

            if (recording_status != entry_data['recording_status']): entry.set_recording_status(recording_status)
            elif (not entry_data['refreshable']): is_refreshable = False

            entry_data = { }

            is_start_defined = ("start" in self.message)

            if (is_start_defined):
                entry_data['time_started'] = self.message['start']
                entry_data['time_sortable'] = self.message['start']
            #

            if ("stop" in self.message):
                if (is_start_defined): entry_data['duration'] = (self.message['stop'] - self.message['start'])
                entry_data['time_finished'] = self.message['stop']
            #

            if (recording_details is not None):
                recording_details = self._process_recording_details(recording_details)

                if ("title" in recording_details): entry_data['title'] = recording_details['title']
                if ("resource_title" in recording_details): entry_data['resource_title'] = recording_details['resource_title']
                if ("series" in recording_details): entry_data['series'] = recording_details['series']
                if ("episodeNumber" in recording_details): entry_data['episode'] = recording_details['episodeNumber']
                if ("description" in recording_details): entry_data['description'] = recording_details['description']

                if ("summary" in recording_details): entry_data['summary'] = recording_details['summary']
                elif ("subtitle" in recording_details): entry_data['summary'] = recording_details['subtitle']
            #

            if (len(entry_data) > 0):
                entry.set_data_attributes(**entry_data)
                entry.save()
            #
        except NothingMatchedException:
            is_refreshable = (recording_status == MpEntryPvrRecording.RECORDING_STATUS_FINISHED)

            if (recording_details is None): recording_details = self.message
            recording_details = self._process_recording_details(recording_details)

            entry = MpEntryPvrRecording()

            entry_data = { "title": recording_details['title'],
                           "vfs_url": vfs_url,
                           "resource_title": recording_details['resource_title'],
                           "refreshable": is_refreshable,
                           "duration": (self.message['stop'] - self.message['start']),
                           "series": recording_details.get("series"),
                           "summary": recording_details.get("summary"),
                           "description": recording_details.get("description"),
                           "time_started": self.message['start'],
                           "time_finished": self.message['stop'],
                           "recorder": self.recorder_name
                         }

            if ("channel" in self.message):
                client = Client.get_instance()
                entry_data['channel'] = client.get_channel_name(self.message['channel'])
            #

            with TransactionContext():
                entry.set_data_attributes(**entry_data)
                entry.set_recording_status(recording_status)

                self.upnp_container.add_entry(entry)

                entry.save()
            #

            entry_id = entry.get_resource_id()
        #

        entry.close()

        if (is_refreshable):
            MemoryTasks.get_instance().add("mp.tasks.ResourceMetadataRefresh.{0}".format(entry_id),
                                           ResourceMetadataRefresh(entry_id),
                                           1
                                          )
        #
    #

    @staticmethod
    def _get_recording_status(message):
        """
Returns the recording status identified by the given HTSP message.

:return: (int) Recording status
:since:  v0.1.00
        """

        _return = MpEntryPvrRecording.RECORDING_STATUS_UNKNOWN

        status = message.get("state")

        if (status == "completed"): _return = MpEntryPvrRecording.RECORDING_STATUS_FINISHED
        elif (status == "missed"): _return = MpEntryPvrRecording.RECORDING_STATUS_FAILED
        elif (status == "recording"): _return = MpEntryPvrRecording.RECORDING_STATUS_RECORDING
        elif (status == "scheduled"): _return = MpEntryPvrRecording.RECORDING_STATUS_PLANNED

        return _return
    #
#
