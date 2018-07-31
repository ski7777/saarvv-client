#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#


class Debug():
    printUnknowResponse = True

    def printXML(sekf, data):
        print(etree.tostring(data, encoding='iso8859-1', pretty_print=True).decode('iso8859-1'))


from .client import Client
