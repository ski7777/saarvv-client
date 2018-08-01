#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
import requests
from lxml import etree
import pytz
from datetime import datetime, timedelta
import dateutil.parser
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
    def getFromDictFallback(self, rawdata, key, fallback):
        # try to find key in dict
        if key in rawdata:
            # found -> return it
            return(rawdata[key])
        else:
            # not found -> return fallback
            return(fallback)

    def convertBasicLocationStationToFPTF(self, rawdata):
        # get tag
        tag = self.removeURNEXTXML(rawdata.tag)
        if tag == 'Station':
            # covert station to FPTF
            return(self.convertStationToFPTF(rawdata))
        elif tag in ['Address', 'Poi', 'ReqLoc']:
            try:
                # covert location to FPTF
                return(self.convertBasicLocationToFPTF(rawdata))
            except ValueError:
                return({})
        else:
            # type unknown -> error
            raise ValueError

    def getJourneyAttributes(self, rawdata):
        data = []
        # iter over attributes
        for a in rawdata.iter('{urn:ExtXml}JourneyAttribute'):
            # prepare dict and basic information
            attr = {
                'from': int(a.get('from')),
                'to': int(a.get('to')),
                'variants': {}
            }
            # iter over attribute variants and texts
            for aa in a.iter('{urn:ExtXml}Attribute'):
                for v in aa.iter('{urn:ExtXml}AttributeVariant'):
                    for t in v.iter('{urn:ExtXml}Text'):
                        # add variant->text
                        attr['variants'][v.get('type')] = t.text
            # add attribute
            data.append(attr)
        return(data)

    def getOperator(self, attr):
        # one attribute type can occur multiple times
        # every attrubute has a to and a from value
        # so we can calculate which attribute is active for the longest time
        rawoperator = {}
        maxlength = 0
        # iterate over attributes
        for o in attr:
            # check whether attribute is operator
            if o['name'] == 'OPERATOR':
                # calc length
                length = o['to'] - o['from']
                # save this att if its length is longer than the last one
                if length > maxlength:
                    rawoperator = o
        # no operator found -> {}
        if rawoperator == {}:
            return({})
        operator = {'type': 'operator'}
        # iterate over attribute variant types
        # we try to get the shortest one available
        for t in ['SHORT', 'NORMAL', 'LONG']:
            if t in rawoperator['variants']:
                # save this one as id
                operator['id'] = rawoperator['variants'][t]
                break
        # raise error if not found
        if 'id' not in operator:
            raise ValueError
        # iterate over attribute variant types
        # we try to get the longest one available
        for t in ['LONG', 'NORMAL', 'SHORT']:
            if t in rawoperator['variants']:
                # save this one as name
                operator['name'] = rawoperator['variants'][t]
                break
        return(operator)

    def getDepartureTime(self, rawdata):
        try:
            # get raw time
            dep = rawdata.find('{urn:ExtXml}Dep')
            t = dep.find('{urn:ExtXml}Time').text
        except:
            raise ValueError
        # convert it
        return(self.convertDateTimeToISO8601(t))

    def getDepartureDelay(self, rawxml, deptime):
        try:
            # get raw time
            sp = rawxml.find('{urn:ExtXml}StopPrognosis')
            delt = dateutil.parser.parse(self.getDepartureTime(sp))
        except:
            # no delay data available -> return None
            return(None)
        # load planned time
        dept = dateutil.parser.parse(deptime)
        # return timedelta in seconds
        return(int((delt - dept).total_seconds()))

    def getArrivalTime(self, rawdata):
        try:
            # get raw time
            arr = rawdata.find('{urn:ExtXml}Arr')
            t = arr.find('{urn:ExtXml}Time').text
        except:
            raise ValueError
        # convert it
        return(self.convertDateTimeToISO8601(t))

    def getArrivalDelay(self, rawxml, arrtime):
        try:
            # get raw time
            sp = rawxml.find('{urn:ExtXml}StopPrognosis')
            delt = dateutil.parser.parse(self.getArrivalTime(sp))
        except:
            # no delay data available -> return None
            return(None)
        # load planned time
        arrt = dateutil.parser.parse(arrtime)
        # return timedelta in seconds
        return(int((delt - arrt).total_seconds()))

    def convertDateTimeToISO8601(self, rawtime):
        # converts a hafas Time Element to a good time format
        now = datetime.now(self.tz)
        timelist = []
        # I´m not sure whether the day element is always present
        # So I just asume it is optional
        # parse day element
        if 'd' in rawtime:
            timelist.append(int(rawtime.split('d')[0]))
        # parse the rest
        timelist += [int(e) for e in rawtime[-8:].split(':')]
        # validate it
        if len(timelist) < 3 or len(timelist) > 4:
            raise ValueError
        if len(timelist) == 3:
            timelist = [0] + timelist
        # add day offset
        now = now + timedelta(days=timelist[0])
        # convert everything to a string
        year = str(now.year)
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        hour = str(timelist[1]).zfill(2)
        minutes = str(timelist[2]).zfill(2)
        seconds = str(timelist[3]).zfill(2)
        # calc timezone offset
        # @Hacon: Please add it to your time format. It´s so important...
        dst = self.getIsDST()
        if dst:
            zone = '+02:00'
        else:
            zone = '+01:00'
        # generate the whole string
        return('-'.join([year, month, day]) +
               'T' +
               ':'.join([hour, minutes, seconds]) +
               zone
               )

    def convertStationToFPTF(self, xmldata):
        data = {'type': 'station'}
        # add all attributes
        data['id'] = xmldata.get('externalStationNr')
        data['name'] = xmldata.get('name')
        data['location'] = {'type': 'location'}
        data['location']['name'] = data['name']
        data['location'].update(self.calcCoordinate(xmldata))
        return(data)

    def convertBasicLocationToFPTF(self, xmldata):
        data = {'type': 'location'}
        # get name
        data['name'] = xmldata.get('name')
        if data['name'] is None:
            # not found -> try alternative methode
            data['name'] = xmldata.get('output')
        if data['name'] is None:
            # still not found -> error
            raise ValueError
        # add coordinate
        data.update(self.calcCoordinate(xmldata))
        return(data)

    def removeURNEXTXML(self, data):
        # delete the strange '{urn:ExtXml}' from a string
        if '{urn:ExtXml}' not in data:
            return(data)
        data = data.split('{urn:ExtXml}')[1]
        return(data)

    def calcCoordinate(self, rawdata):
        # get values
        x = rawdata.get('x')
        y = rawdata.get('y')
        if x is None or y is None:
            return({})
        data = {}
        # some calculations
        # @hacon: What about using floats...
        data['latitude'] = int(y) / 100
        data['longitude'] = int(x) / 10
        return(data)

    def generateProductFilter(self, prod, parent):
        # this is a dummy fucntion
        # TODO: ask ZPS for the file 'zugart'
        etree.SubElement(parent, 'Prod', attrib={'prod': '11111111111'})

    def generateRFlags(self, data, parent):
        if not ('nbefore' in data and 'nafter' in data):
            raise ValueError
        if data['nbefore'] > 1 or data['nafter'] > 5:
            raise ValueError
        # add b and f
        attr = {'b': str(data['nbefore']), 'f': str(data['nafter'])}
        if 'changes' in data:
            if changes > 6:
                raise ValueError
            # add nrChanges
            attr['nrChanges'] = data['changes']
        # add getPrice
        attr['getPrice'] = '0'
        if 'price' in data:
            if data['price']:
                # set getPrice to 1 if needed
                attr['getPrice'] = '1'
        # add XML element
        etree.SubElement(parent, 'RFlags', attrib=attr)

    def generateTime(self, data, parent):
        # generate a Hafas ReqT
        if not ('date' in data and 'time' in data):
            raise ValueError
        attr = {'time': data['time'], 'date': data['date']}
        # add 'a' tag. a=0-> time is departure time, a=1-> arrival time
        if 'type' not in data:
            attr['a'] = "0"
        elif data['type'] not in ['departure', 'arrival']:
            raise ValueError
        elif data['type'] == 'departure':
            attr['a'] = "0"
        else:
            attr['a'] = "1"
        etree.SubElement(parent, 'ReqT', attrib=attr)

    def getIsDST(self):
        # check whether we are in DST
        # hafas just uses the local time. It does not care about timezones and dst
        # thus we have to calc everything on our own...
        now = pytz.utc.localize(datetime.utcnow())
        return(now.astimezone(self.tz).dst() != timedelta(0))

