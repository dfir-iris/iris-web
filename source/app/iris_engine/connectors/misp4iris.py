#!/usr/bin/env python3
#
#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# IMPORTS ------------------------------------------------
import json

# VARS ---------------------------------------------------

# CONTENT ------------------------------------------------
from pymisp import PyMISP, ExpandedPyMISP
from app.configuration import misp_url, misp_key, misp_verifycert, misp_http_proxy, misp_https_proxy
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Misp4Iris(object):
    """
    Handles the link with misp (not community) and provide a layer for Iris
    """
    def __init__(self):
        proxies = {
            "http": misp_http_proxy,
            "https": misp_https_proxy
        }
        self._misp = ExpandedPyMISP(url=misp_url,
                                    key=misp_key,
                                    ssl=misp_verifycert,
                                    proxies=proxies
                                    )

    def search_ip(self, search_term):
        """
        Execute a search in MISP matching provided IP
        :param search_term: IP to look for
        :return: JSON result
        """
        # Do the search against IP attributes
        result = self._misp.search(controller="attributes",
                                   metadata=False,
                                   type_attribute=["ip-src", "ip-dest"],
                                   value=search_term)

        res = {}
        for e in result['Attribute']:
            res.update({
                e.get("value"): json.dumps({
                    "misp_desc": "{} - {}".format(e.get('category'), e.get('Event').get('info')),
                    "misp_id": e.get('event_id')
                })
            })

        return res if len(res) > 0 else None

    def search_domain(self, search_term):
        """
        Execute a search in MISP matching provided domain
        :param search_term: IP to look for
        :return: JSON result
        """
        # Do the search against IP attributes
        result = self._misp.search(controller="attributes",
                                   metadata=False,
                                   type_attribute=["domain"],
                                   value=search_term)

        res = {}
        for e in result['Attribute']:
            res.update({
                e.get("value"): json.dumps({
                    "misp_desc": "{} - {}".format(e.get('category'), e.get('Event').get('info')),
                    "misp_id": e.get('event_id')
                })
            })

        return res if len(res) > 0 else None

    def search_filename(self, search_term):
        """
        Execute a search in MISP matching provided filename
        :param search_term: IP to look for
        :return: JSON result
        """
        # Do the search against IP attributes
        result = self._misp.search(controller="attributes",
                                   metadata=False,
                                   type_attribute=["filename"],
                                   value=search_term)

        res = {}
        for e in result['Attribute']:
            res.update({
                e.get("value"): json.dumps({
                    "misp_desc": "{} - {}".format(e.get('category'), e.get('Event').get('info')),
                    "misp_id": e.get('event_id')
                })
            })

        return res if len(res) > 0 else None


    def search_md5(self, search_term):
        """
        Execute a search in MISP matching provided MD5
        :param search_term: FileContentHash objects
        :return: JSON result
        """
        to_search = []
        # Build the search list. search_item is a list of object pulled from DB
        # so we need to read hash field and remove the dashes before injecting into
        # build list
        for element in search_term:
            to_search.append(element.content_hash.replace('-', ''))

        # Do the search against MD5 attributes only
        result = self._misp.search(controller='attributes',
                                   metadata=False,
                                   type_attribute="md5",
                                   value= to_search
                                   )

        res = {}
        for e in result['Attribute']:
            # For every match, update the cache list of Iris. It will be injected into DB
            res.update({
                e.get("value"): json.dumps({
                    "misp_desc": "{} - {}".format(e.get('category'), e.get('Event').get('info')),
                    "misp_id": e.get('event_id')
                })
            })

        return res if len(res) > 0 else None

    def search_fn(self, search_term):
        """
        Execute a seach in MSIP matching file_name
        :param search_term: Term to look for
        :return: JSON result
        """
        controller = 'attributes'
        to_search = []
        for element in search_term:
            to_search.append(element.filename)

        kwargs = {"values": to_search}
        result = self._misp.search(controller=controller,
                                   type_attribute="filename",
                                   value=to_search
                                   )

        res = {}
        for e in result['response']['Attribute']:
            res.update({
                e.get("value"): {
                    "misp_desc": "{} - {}".format(e.get('category'), e.get('Event').get('info')),
                    "misp_id": e.get('event_id')
                }
            })

        return res if len(res) > 0 else None