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

from dNG.pas.data.settings import Settings
from dNG.pas.data.pvr.tvheadend_manager import TvheadendManager
from dNG.pas.plugins.hook import Hook

def get_singletons(params, last_return = None):
#
	"""
Called for "dNG.mp.pvr.Manager.getSingletons"

:param params: Parameter specified
:param last_return: The return value from the last hook called.

:return: (mixed) Return value
:since:  v0.1.00
	"""

	if (type(last_return) is list): _return = last_return
	else: _return = [ ]

	_return.append(TvheadendManager.get_instance())

	return _return
#

def register_plugin():
#
	"""
Register plugin hooks.

:since: v0.1.00
	"""

	Settings.read_file("{0}/settings/mp/tvheadend.json".format(Settings.get("path_data")))

	if (Settings.get("mp_tvheadend_enabled", False)):
	#
		Hook.register("dNG.mp.pvr.Manager.getSingletons", get_singletons)
	#
#

def unregister_plugin():
#
	"""
Unregister plugin hooks.

:since: v0.1.00
	"""

	Hook.unregister("dNG.mp.pvr.Manager.getSingletons", get_singletons)
#

##j## EOF