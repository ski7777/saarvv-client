#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
import requests
from lxml import etree
from . import Debug


class Client:
    baseurl = 'http://saarfahrplan.de/cgi-bin/extxml.exe'
    tz = pytz.timezone('Europe/Berlin')

    def __init__(self, token):
        self.token = token

    def callServer(self, data):
        # send raw data to server and get raw data
        r = requests.post(self.baseurl, data)
        return(r.text)

    def genBaseXML(self):
        # generate basic XML tree
        xml = etree.Element('ReqC', attrib={
            'ver': '1.2',
            'prod': 'ivi',
            'lang': 'DE',
            'accessId': self.token,
        }
        )
        return(xml)

    def request(self, req):
        # convert XML request to string
        reqdata = etree.tostring(req, encoding='iso8859-1')
        # call the server
        rawres = self.callServer(reqdata).encode('iso8859-1')
        # convert raw response to XML
        resxml = etree.fromstring(rawres)
        # compile response
        res = self.compileResponse(resxml)
        # return FPTF data
        return(res)

    def compileResponse(self, rawdata):
        # validate as response
        if self.removeURNEXTXML(rawdata.tag) != 'ResC':
            raise ValueError
        # prepare list for child responses
        reslist = []
        # iterate over responses
        for c in rawdata.iterchildren():
            # compile response
            # append to list
            reslist.append(self.compileResponseElement(c))
        # get type of responses
        # it semms like it is impossible to have a response with different types
        # so we just grep the first one
        if len(reslist) == 0:
            # if there are no responses: None
            t = None
        else:
            # grep type of first response
            t = reslist[0][0]
        return(t, reslist)

    def compileResponseElement(self, rawdata):
        # define child response type -> compiler function
        ResponseProcessors = {
        }
        # get tag of child response
        tag = self.removeURNEXTXML(rawdata.tag)
        # check type is valid
        if tag not in ResponseProcessors:
            if Debug.printUnknowResponse:
                Debug.printXML(rawdata)
            raise ValueError
        # get child response compiler and call it
        data = ResponseProcessors[tag](rawdata)
        return(tag, data)

