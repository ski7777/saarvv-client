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
            'LocValRes': self.compileLocValRes,
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

    def searchList(self, reqs):
        # check data type
        if type(reqs) != list:
            raise TypeError
        # get basic XML
        xml = self.genBaseXML()
        i = 0  # variable for id
        # I think we dont need this ID. I just dont trust the server.
        # Maybe it will mess-up the requests. I dont know
        # iterate over querys
        for query, qtype in reqs:
            # check query string type
            if type(query) != str:
                raise TypeError
            # check request type
            if qtype not in ['ST', 'ADR', 'POI', 'ALLTYPE']:
                raise ValueError
            # generate LocValReq element with ID
            reqxml = etree.SubElement(xml, 'LocValReq', attrib={'id': str(i)})
            # generate ReqLoc element with request query and type
            reqxmlsub = etree.SubElement(reqxml, 'ReqLoc', attrib={
                'match': query, 'type': qtype
            }
            )
            i += 1  # increment id
        # call the server
        data = self.request(xml)
        # check response type
        if data[0] != 'LocValRes':
            raise TypeError
        ressdict = {}
        # iterate over response childs
        for res in data[1]:
            # check type
            if res[0] != 'LocValRes':
                raise TypeError
            resraw = res[1]  # child response data
            resi = resraw[0]  # child response id
            resd = resraw[1]  # child response stops/stations/poi/...
            # save id->data
            ressdict[resi] = resd
        # generate a list with the child responses stations/... sorted by id
        ress = [ressdict[i] for i in sorted(ressdict.keys())]
        # return data
        return(ress)

    def searchOne(self, query, qtype):
        # just search one query and return the first child response
        return(self.searchList([(query, qtype)])[0])

    def searchStations(self, query):
        # seacrch for one station
        return(self.searchOne(query, 'ST'))

    def searchAddresses(self, query):
        # search for one address
        return(self.searchOne(query, 'ADR'))

    def searchPOIs(self, query):
        # search for one POI
        return(self.searchOne(query, 'POI'))

    def searchAll(self, query):
        # search for one of any type
        return(self.searchOne(query, 'ALLTYPE'))

    def compileLocValRes(self, rawdata):
        # list for response items
        data = []
        # get id value
        reqid = rawdata.get('id')
        for c in rawdata.iterchildren():
            # parse it
            o = self.convertBasicLocationStationToFPTF(c)
            # add to list if not empty
            if o != {}:
                data.append(o)
        return(reqid, data)

    def removeURNEXTXML(self, data):
        if '{urn:ExtXml}' not in data:
            return(data)
        data = data.split('{urn:ExtXml}')[1]
        return(data)

