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

from threading import local
from weakref import ref, WeakValueDictionary
import asyncore
import hashlib
import re
import socket

from dNG.data.binary import Binary
from dNG.data.settings import Settings
from dNG.data.traced_exception import TracedException
from dNG.module.named_loader import NamedLoader
from dNG.plugins.hook import Hook
from dNG.runtime.instance_lock import InstanceLock
from dNG.runtime.io_exception import IOException
from dNG.runtime.result_event import ResultEvent
from dNG.runtime.thread import Thread
from dNG.runtime.thread_lock import ThreadLock
from dNG.runtime.value_exception import ValueException

from mp.data.pvr.tvheadend.htsbin import Htsbin
from mp.data.pvr.tvheadend.htsmsg import Htsmsg

class Client(asyncore.dispatcher):
    """
Client for Tvheadend.

:author:     direct Netware Group et al.
:copyright:  (C) direct Netware Group - All rights reserved
:package:    mp
:subpackage: tvheadend
:since:      v0.1.00
:license:    https://www.direct-netware.de/redirect?licenses;gpl
             GNU General Public License 2
    """

    HTSP_VERSION = 25
    """
HTS protocol version
    """

    _instance_lock = InstanceLock()
    """
Thread safety lock
    """
    _response_waiting_events = WeakValueDictionary()
    """
Threads waiting for the "seq" used as the key
    """
    _weakref_instance = None
    """
Client weakref instance
    """

    def __init__(self):
        """
Constructor __init__(Client)

:since: v0.1.00
        """

        self.active = False
        """
Listener state
        """
        self.authenticated = False
        """
True if authenticated
        """
        self.auth_username = None
        """
Authentication username
        """
        self.auth_digest = None
        """
Authentication digest
        """
        self._auth_lock = ThreadLock()
        """
Thread safety lock for authorization
        """
        self.channel_server_method_supported = False
        """
Tvheadend HTSP getChannel requires version 14 or newer
        """
        self.channels_cache = { }
        """
Tvheadend channels cache
        """
        self.listener_data = None
        """
Listener connection data
        """
        self.listener_mode = None
        """
Listener socket mode
        """
        self.local = local()
        """
Local data handle
        """
        self.lost_connection = False
        """
True after "handle_close()" has been called
        """
        self._lock = ThreadLock()
        """
Thread safety lock
        """
        self.log_handler = NamedLoader.get_singleton("dNG.data.logging.LogHandler", False)
        """
The LogHandler is called whenever debug messages should be logged or errors
happened.
        """
        self.seq = 0
        """
Sequence counter
        """
        self.server_name = None
        """
Server name
        """
        self.server_version = None
        """
Server version
        """
        self.socket = None
        """
Connection socket
        """
        self.server_transcoding_supported = False
        """
Tvheadend HTSP transcoding requires version 11 or newer
        """
        self.timeout = 0
        """
Socket timeout value
        """

        self.timeout = int(Settings.get("mp_tvheadend_client_socket_data_timeout", 0))

        if (self.timeout < 1): self.timeout = int(Settings.get("pas_global_client_socket_data_timeout", 0))
        if (self.timeout < 1): self.timeout = int(Settings.get("pas_global_socket_data_timeout", 30))

        listener_address = Settings.get("mp_tvheadend_listener_address", "localhost:9982")
        listener_mode = Settings.get("mp_tvheadend_listener_mode")

        self.listener_mode = (socket.AF_INET6 if (listener_mode == "ipv6") else socket.AF_INET)

        re_result = re.search("^(.+):(\\d+)$", listener_address)
        if (re_result is None): raise ValueException("Invalid configuration for Tvheadend client")

        self.listener_data = ( Binary.str(re_result.group(1)), int(re_result.group(2)) )

        listener_socket = socket.socket(self.listener_mode, socket.SOCK_STREAM)
        listener_socket.settimeout(self.timeout)
        listener_socket.connect(self.listener_data)

        asyncore.dispatcher.__init__(self, sock = listener_socket)
    #

    def __getattr__(self, api_method):
        """
python.org: Called when an attribute lookup has not found the attribute in
the usual places (i.e. it is not an instance attribute nor is it found in the
class tree for self).

:param api_method: API method

:return: (proxymethod) API callable
:since:  v0.1.00
        """

        self._ensure_session_established()

        def proxymethod(**kwargs): return self._call(api_method, kwargs)

        return proxymethod
    #

    def _call(self, api_method, params = None):
        """
Sends a API method call to the Tvheadend server.

:param api_method: API method
:param params: Dict with request parameters

:return: (dict) Parsed HTSMSG response
:since:  v0.1.00
        """

        if (self.log_handler is not None): self.log_handler.debug("#echo(__FILEPATH__)# -{0!r}._call({1})- (#echo(__LINE__)#)", self, api_method, context = "mp_tvheadend")

        if (params is None): params = { }
        if (self.auth_username is not None): params['username'] = self.auth_username
        if (self.auth_digest is not None): params['digest'] = self.auth_digest

        with self._lock:
            seq = self.seq

            self.seq += 1
            if (self.seq > 32768): self.seq = 0
        #

        params['method'] = api_method
        params['seq'] = seq
        message = Htsmsg(params).export()

        response_waiting_event = ResultEvent()
        with Client._instance_lock: Client._response_waiting_events[seq] = response_waiting_event

        Client.send(self, message)
        return self._wait_for_and_get_response_seq(response_waiting_event)
    #

    def _ensure_session_established(self):
        """
Checks the session and authenticates this client at the Tvheadend server.

:since: v0.1.00
        """

        if (not self.authenticated):
            if (not self.active): self.start()

            with self._auth_lock:
                # Thread safety
                if (not self.authenticated):
                    response = self._call("hello",
                                          { "htspversion": Client.HTSP_VERSION,
                                            "clientname": "mp.tvheadend",
                                            "clientversion": "#echo(mpTvheadendVersion)#"
                                          }
                                         )

                    if (response['htspversion'] < 8): raise IOException("Tvheadend indicated HTSP version is too old")

                    self.channel_server_method_supported = (response['htspversion'] >= 14)
                    self.server_transcoding_supported = (response['htspversion'] >= 11)

                    self.server_name = response['servername']
                    self.server_version = response['serverversion']

                    self.auth_username = Settings.get("mp_tvheadend_user")
                    password = Binary.bytes(Settings.get("mp_tvheadend_password"))

                    if (self.auth_username is not None and password is not None):
                        self.auth_digest = Htsbin(hashlib.new("sha1", password + response['challenge']).digest())

                        response = self._call("authenticate")
                        if ("noaccess" in response): raise IOException("Tvheadend denied access")
                    #

                    self.authenticated = True
                    if (not self.channel_server_method_supported): Hook.register("mp.pvr.tvheadend.Client.onEvent", self._handle_event)
                #
            #
        #
    #

    def get_channel_name(self, _id):
        """
Returns the channel name for the channel with the given ID.

:param _id: Channel ID

:return: (str) Channel name or call sign
:since:  v0.1.00
        """

        if (self.channel_server_method_supported): return self.getChannel(channelId = _id)['channelName']
        else:
            with self._lock:
                if (_id not in self.channels_cache): raise ValueException("Channel ID given is invalid")
                return self.channels_cache[_id]
            #
        #
    #

    def get_epg_details(self, channel, start_timestamp, end_timestamp = None, title = None):
        """
Returns the EPG details matching the recording defined by the channel ID,
its start and end time.

:return: (dict) Event data
:since:  v0.1.00
        """

        _return = None

        self.epg_time_threshold = 5 * 60

        event_id = None
        start_timestamp_min = start_timestamp - self.epg_time_threshold
        end_timestamp_max = (None if (end_timestamp is None) else end_timestamp + self.epg_time_threshold)

        while (_return is None):
            params = { "channelId": channel,
                       "numFollowing": 10
                     }

            if (event_id is not None): params['eventId'] = event_id
            if (end_timestamp_max is not None): params['maxTime'] = end_timestamp_max

            events = self.getEvents(**params)['events']

            if (len(events) > 0 and events[0]['stop'] <= start_timestamp_min):
                event = events[-1]

                if (event['start'] < start_timestamp_min
                    and "nextEventId" in event
                   ): event_id = event['nextEventId']
                else:
                    _return = Client._get_matching_event(events, start_timestamp_min, end_timestamp_max, title)
                    break
                #
            else: break
        #

        if (_return is None): raise ValueException("No EPG event matches the given criteria")
        return _return
    #

    def get_epg_event_details(self, event_id):
        """
Returns the EPG details matching the recording defined by the channel ID,
its start and end time.

:return: (dict) Event data
:since:  v0.1.00
        """

        try: return self.getEvent(eventId = event_id)
        except IOException as handled_exception: raise ValueException("No EPG event matched the given ID", _exception = handled_exception)
    #

    def get_server_name(self):
        """
Returns the Tvheadend server name.

:return: (str) Server name
:since:  v0.1.00
        """

        self._ensure_session_established()
        return self.server_name
    #

    def get_server_version(self):
        """
Returns the Tvheadend server version.

:return: (str) Server version
:since:  v0.1.00
        """

        self._ensure_session_established()
        return self.server_version
    #

    def handle_close(self):
        """
python.org: Called when the socket is closed.

:since: v0.1.00
        """

        if (self.active):
            if (self.log_handler is not None): self.log_handler.warning("mp.tvheadend.Client reporting: Socket closed - marked for reconnect", context = "mp_tvheadend")

            self.stop()
            self.lost_connection = True
        #
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

            if (not self.channel_server_method_supported):
                if (method in ( "channelAdd", "channelUpdate" )):
                    if ("channelName" in message): self.channels_cache[message['channelId']] = message['channelName']
                elif (method == "channelDelete"):
                    with self._lock:
                        if (message['channelId'] in self.channels_cache): del(self.channels_cache[message['channelId']])
                    #
                #
            #
        #
    #

    def handle_read(self):
        """
python.org: Called when the asynchronous loop detects that a "read()" call
on the channel's socket will succeed.

:since: v0.1.00
        """

        try:
            message = Htsmsg.import_socket_data(self.socket)

            if (message is None):
                if (self.log_handler is not None): self.log_handler.warning("mp.tvheadend.Client reporting: Socket lost - marked for reconnect", context = "mp_tvheadend")

                self.stop()
                self.lost_connection = True
            elif ("seq" in message):
                with Client._instance_lock:
                    seq = message['seq']

                    if (seq not in Client._response_waiting_events): raise IOException("HTSMSG seq is invalid")

                    response_waiting_event = Client._response_waiting_events[seq]
                    del(Client._response_waiting_events[seq])
                #

                response_waiting_event.set_result(message)
            elif ("method" in message):
                Thread(target = Hook.call,
                       args = ( "mp.pvr.tvheadend.Client.onEvent", ),
                       kwargs = { "message": message }
                      ).start()
            elif (self.log_handler is not None): self.log_handler.error("mp.tvheadend.Client received async message without method", context = "mp_tvheadend")
        except Exception as handled_exception:
            if (self.log_handler is not None): self.log_handler.error(handled_exception, context = "mp_tvheadend")
        #
    #

    def is_active(self):
        """
Returns the PVR manager status.

:return: (bool) True if active
:since:  v0.1.00
        """

        if (self.lost_connection):
            with self._lock:
                # Thread safety
                if (self.lost_connection): self.start()
            #
        #

        return self.active
    #

    def start(self):
        """
Starts the prepared dispatcher in a new thread.

:since: v0.1.00
        """

        if (not self.active):
            is_already_active = False

            with self._lock:
                # Thread safety
                is_already_active = self.active

                if (not is_already_active):
                    self.active = True
                    self.lost_connection = False
                #
            #

            if (not is_already_active):
                Hook.register("dNG.pas.Status.onShutdown", self.thread_stop)

                self.channels_cache = { }

                if (self.seq > 0):
                    listener_socket = socket.socket(self.listener_mode, socket.SOCK_STREAM)
                    listener_socket.settimeout(self.timeout)
                    listener_socket.connect(self.listener_data)

                    self.seq = 0
                    self.set_socket(listener_socket)
                #

                Thread(target = self.run).start()
            #
        #
    #

    def run(self):
        """
Run the main loop for this dispatcher instance.

:since: v0.1.00
        """

        # pylint: disable=broad-except

        if (self.log_handler is not None): self.log_handler.debug("#echo(__FILEPATH__)# -{0!r}.run()- (#echo(__LINE__)#)", self, context = "mp_tvheadend")

        if (not hasattr(self.local, "sockets")): self.local.sockets = { }

        try:
            self.add_channel(self.local.sockets)
            asyncore.loop(5, map = self.local.sockets)

            for _socket in self.local.sockets:
                try: self.local.sockets[_socket].close()
                except socket.error: pass
            #

            self.local.sockets = { }
        except Exception as handled_exception:
            if (self.active):
                if (self.log_handler is None): TracedException.print_current_stack_trace()
                else: self.log_handler.error(handled_exception, context = "mp_tvheadend")
            #
        finally: self.stop()
    #

    def stop(self):
        """
Stops the listener and unqueues all running sockets.

:since: v0.1.00
        """

        # pylint: disable=broad-except

        with self._lock:
            if (self.active):
                if (self.log_handler is not None): self.log_handler.debug("#echo(__FILEPATH__)# -{0!r}.stop()- (#echo(__LINE__)#)", self, context = "mp_tvheadend")

                self.active = False
                self.authenticated = False

                Hook.unregister("dNG.pas.Status.onShutdown", self.thread_stop)
                if (not self.channel_server_method_supported): Hook.unregister("mp.pvr.tvheadend.Client.onEvent", self._handle_event)

                try: self.close()
                except Exception: pass
            #
        #
    #

    def thread_stop(self, params = None, last_return = None):
        """
Stops the running dispatcher instance by hook call.

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
        """

        self.stop()
        return last_return
    #

    def _wait_for_and_get_response_seq(self, response_waiting_event):
        """
Waits for and returns the response.

:return: (dict) Parsed HTSMSG response
:since:  v0.1.00
        """

        if (self.log_handler is not None): self.log_handler.debug("#echo(__FILEPATH__)# -{0!r}._receive_response()- (#echo(__LINE__)#)", self, context = "mp_tvheadend")

        if (not response_waiting_event.wait(self.timeout)): raise IOException("Tvheadend client timed out")
        if (not self.active): raise IOException("Tvheadend client has stopped listening")

        _return = response_waiting_event.get_result()
        if ("error" in _return): raise IOException("mp.tvheadend.Client received error: {0}".format(_return['error']))

        return _return
    #

    def writable(self):
        """
python.org: Called each time around the asynchronous loop to determine
whether a channel's socket should be added to the list on which write events
can occur.

:return: (bool) Always False
:since:  v0.1.00
        """

        return False
    #

    @staticmethod
    def get_instance():
        """
Get the Client singleton.

:return: (Client) Object on success
:since:  v0.1.00
        """

        _return = None

        with Client._instance_lock:
            if (Client._weakref_instance is not None): _return = Client._weakref_instance()

            if (_return is None):
                _return = Client()
                Client._weakref_instance = ref(_return)
            #
        #

        return _return
    #

    @staticmethod
    def _get_matching_event(events, start_timestamp_min, end_timestamp_max, title):
        """
Searches through the list of events given to find the match based on
the given criteria.

:return: (dict) Event data if found; None if not matched
:since:  v0.1.00
        """

        _return = None

        for event in events:
            if (title is None or event['title'] == title):
                if (event['start'] > start_timestamp_min and event['stop'] < end_timestamp_max):
                    _return = event
                    break
                #
            #
        #

        return _return
    #
#
