#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simgo Task 1.

Usage:
  task1.py -h | --help
  task1.py --version
  task1.py [--piepeline=<STR>]   

Options:
  -h --help            Show this screen.
  --version            Show version.
  --pipeline           Configure the pipeline.
  
Examples:
  ./task1.py --pipeline GTPBTR # configures Byte Generator -> Transport -> PacketPHY -> BytePHY -> Transport -> Byte Printer  
"""

import cmd
import logging
from collections import namedtuple
from time import sleep
import threading
import subprocess
import serial, random, time

import sys, traceback
import os
import re

try:
    from docopt import docopt
except:
    print "docopt is required to run this script"
    print "Command 'apt-get install python-docopt' can help"


NamedListener = namedtuple("NamedListener", ['name', 'callback'])

def buildhexstring(value, width=0, prefix=''):
    valueStr = hex(value)
    valueStr = valueStr.lstrip("0x")
    valueStr = valueStr.rstrip("L")
    valueStr = valueStr.upper();
    if (width > 0):
        valueStr = valueStr.zfill(width)   # add zeros the left

    valueStr = prefix + valueStr

    return valueStr

def bytesToHexString(data):
    '''
    Convert array [0x30, 0x31] to string "30 31"
    '''
    s = ""
    for c in data:
        s = s + "{0}".format(buildhexstring(c, 2)) + " "
    return s



class StatManager:
    '''
    A single place where references to all blocks of debug counters are stored
    '''
    def __init__(self):
        self.groups = {}

    class Block:
        def __init__(self, name):
            '''
            @param name is a name of the block. 
            Useful when there are many instances of the same set of counters. 
            For example "eth0", "eth1"
            '''
            self.name = name
            self.ignoreFields = []
            
            #  All fields added so far are in the ignore list
            for fieldName in self.__dict__:
                self.ignoreFields.append(fieldName)

        
        def addField(self, (name, initialValue)):
            '''
            Add a field with specified name
            @param name is a name of the counter, for example "tx"
            '''
            self.__dict__[name] = initialValue

        def addFields(self, fields):
            '''
            @param fields list of tuples (field name, iniitial value)
            '''
            for f in fields:
                self.addField(f)

        def addFieldsInt(self, fields):
            '''
            @param fields list of field names
            '''
            for f in fields:
                self.addField((f, 0))
            
    def addCounters(self, groupName, block):
        '''
        Add a block of counters to the specified group
        @param groupName is a name of the group, for example "Network traffic"
        @param block is an object of type Block
        '''
        if (not groupName in self.groups):
            self.groups[groupName] = []
        group = self.groups[groupName]
        group.append(block) 

    def __isPrintableField(self, block, fieldName):
        result = fieldName in block.ignoreFields
        return (not result)
        
    def printGroup(self, groupName):
        '''
        Print counters from the specified by name group 
        '''
        counters = self.groups[groupName]
        if (len(counters) <= 0):
            return
        fieldPattern = "{:>14}"
            
        # Print column names
        print fieldPattern.format(groupName),
        o = counters[0]
        for fieldName in o.__dict__:
            if (self.__isPrintableField(o, fieldName)):
                print fieldPattern.format(fieldName),
        print

        separatorLength = 14
        separator = ""
        while (separatorLength > 0):
            separator = separator + "-"
            separatorLength = separatorLength - 1
             
        fields = len(o.__dict__)  + 1 - len(o.ignoreFields)
        while (fields > 0):
            fields = fields - 1
            print separator,
        print
        
        # Print table data
        for counter in counters:
            # Print the name of the counter block
            print fieldPattern.format(counter.name),
            for fieldName in counter.__dict__:
                if (self.__isPrintableField(counter, fieldName)):
                    print fieldPattern.format(counter.__dict__[fieldName]),
            print    
        
    def printAll(self):
        '''
        Print counters from all registered groups
        '''
        for groupName in self.groups:
            self.printGroup(groupName)
            print
            

statManager = StatManager()

class PipelineStage():
    '''
    A stage of the pipeline
    '''
    def __init__(self):
        self.nextStage = None
        self.name = name

    def setNext(self, nextStage):
        '''
        Set sink where to send the randomly generated packets
        @param sink is an object which contains method tx()
        '''    
        self.nextStage = nextStage
        
    def tx(self, packet):
        '''
        Do nothing in the base class
        '''
        logger.error("Method tx() is called for the abstract Sink");
        pass
    
    def getName(self):
        return self.name
        
    def setName(self, name):
        return self.name = name
    
class ByteGenerator(threading.Thread, PipelineStage):
    '''
    Feeds bytes to the First stage of the data pipeline
    Wake up periodically and generate a packet of data
    A packet length and payload are random numbers  
    '''
    def __init__(self, maximumBurstSize=7, period=0.4):
        '''
        @param maximumBurstSize - maximum packet size to generate, the length is random
        @param period - sleep time between the packets  
        '''
        super(ByteGenerator, self).__init__()
        self.maximumBurstSize, self.period = maximumBurstSize, period
        
        self.stat = StatManager.Block("")
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "zeroPackets", "noSink"])
        statManager.addCounters("ByteGenerator", self.stat)
        
    def run(self):
        '''
        Wake, generate a packet, go to sleep
        '''
        while (not self.exitFlag):
            time.sleep(self.period)
            packetSize = randint(0, self.maximumBurstSize)
            packet = os.urandom()
            self.stat.wakeups = self.stat.wakeups + 1
            packetLen = len(packet)
            if (packetLen > 0):
                _sendBytes(packet, packetLen)
            else:
                self.stat.zeroPackets = self.stat.zeroPackets + 1
                
                
    def _sendBytes(self, packet, packetLen):            
        if (self.nextStage != None):
            self.stat.packets = self.stat.packets + 1
            self.stat.bytes = self.stat.bytes + packetLen
            for (b in packet):
                self.nextStage.tx([b])
        else:   
            self.stat.noSink = self.stat.noSink + 1
        
    def cancel(self):
        self.exitFlag = True

class BytePrinter(PipelineStage):
    '''
    Last stage of the data pipeline
    Prints the incoming data
    '''
    def __init__(self):
        self.lock = threading.Lock()
        self.stat = StatManager.Block("")
        self.stat.addFieldsInt(["wakeups", "packets", "bytes"])
        statManager.addCounters("BytePrinter", self.stat)

    def tx(self, packet):
        '''
        A data sink which prints bytes. This method is reentrant
        '''
        s = bytesToHexString(packet)

        self.lock.acquire()
        print s
        self.stat.wakeups = self.stat.wakeups + 1
        self.stat.packets = self.stat.packets + 1
        packetLen = len(self.stat.packets)
        self.stat.bytes = self.stat.bytes + packetLen
        self.lock.release()

class Transport(PipelineStage):
    '''
    Second stage of the pipeline
    '''
    def __init__(self, name):
        self.lock = threading.Lock()
        self.name = name
        self.stat = StatManager.Block(name)
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "noSink"])
        statManager.addCounters("Transport", self.stat)

    def tx(self, data):
        '''
        A data sink which forwards packets to the next stage in the pipeline
        '''
        self.lock.acquire()
        self.stat.wakeups = self.stat.wakeups + 1
        self.stat.packets = self.stat.packets + 1
        packetLen = len(data)
        self.stat.bytes = self.stat.bytes + packetLen
        self.lock.release()
        
        if (self.nextStage != None):
            sink.tx(data)
        else:
            self.stat.noSink = self.stat.noSink + 1

class PacketPHY(PipelineStage):
    '''
    Packet PHY pipeline stage 
    '''
    def __init__(self, name, minimumPacketSize=10):
        self.minimumPacketSize = minimumPacketSize
        self.name = name
        self.lock = threading.Lock()
        self.stat = StatManager.Block(name)
        
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "noSink", "timerStarted", "timerExpired", "timerCanceled"])
        statManager.addCounters("Transport", self.stat)
        
        self.collectedData = []

    def tx(self, data):
        '''
        A data sink which collects bytes and sends packets to the next stage
        '''
        self.lock.acquire()
        
        self.stat.wakeups = self.stat.wakeups + 1
        
        # Start timer on the first arriving byte
        self._startTimer()

        self.collectedData.append(data)
        packetLen = len(self.collectedData)
        if (packetLen > minimumPacketSize):
            self._sendBytes(self.collectedData, packetLen)

        self.lock.release()
        
        
        
    def _startTimer(self):
        '''
        Start timer on the first arriving byte
        Cancel the timer if running
        '''
        if (self.txTimer):
            self.txTimer.cancel()
            self.stat.timerCanceled = self.stat.timerCanceled + 1

        if (len(self.collectedData) == 0): 
            self.txTimer = threading.Timer(1.0, timeoutExpired)
            self.stat.timerStarted = self.stat.timerStarted + 1

            
    def timeoutExpired(self):
        self.lock.acquire()
        
        self.stat.timerExpired = self.stat.timerExpired + 1
        packetLen = len(self.collectedData)
        if (packetLen > 0):
            self._sendBytes(self.collectedData, packetLen)
            
        self.lock.release()
        
        
    def _sendBytes(self, packet, packetLen):
        '''
        Forward bytes to the next stage
        '''            
        if (self.nextStage != None):
            self.stat.packets = self.stat.packets + 1
            self.stat.bytes = self.stat.bytes + packetLen
            self.nextStage.tx(packet)
        else:   
            self.stat.noSink = self.stat.noSink + 1
            
        self._flushData()
            
    def _flushData(self):
        '''
        Drop all collected data, stop timer
        '''
        self.collectedData = []
        if (self.txTimer):
            self.txTimer.cancel()

class BytePHY(Transport):
    '''
    Get bytes, forward the bytes to the next stage
    '''
    def __init__(self, name):
        super(Transport, self).__init__()

 
class cmdGroundLevel(cmd.Cmd):
    '''
    Interactive command line interface 
    '''
    
    def init(self, simgoEngine, cmdLoop):
        '''
        I can not subclass old style class
        '''
        self.simgoEngine, self.cmdLoop = simgoEngine, cmdLoop

    def emptyline(self):
        '''
        If empty line repeat last sent command, unless this is run
        '''
        
        lastcmd = self.lastcmd
        if ((lastcmd == "") or (lastcmd == None)):
            return
        
        words = lastcmd.split()
        if (words[0] in NOT_AUTO_COMMANDS):
            return

        self.onecmd(lastcmd.strip())

              
    def do_none(self, line):
        pass

    def do_sleep(self, line):
        (result, t) = convertToFloat(line)
        if (result):
            time.sleep(t)
        else:
            self.help_sleep()
        
    def help_sleep(self):
        print "Delay execution"
        print "Usage:sleep secs"
        print "Example:sleep 0.1"
        

    def do_statistics(self, line):
        statManager.printAll()

    def help_statistics(self):
        print "Print debug statistics"
      
    def do_status(self, line):
        pass
        
    def help_status(self):
        print "Print systems status, like list of layers"
        print "Usage:status [brief|full]"

    def do_exit(self, line):
        self.closeAll()
        
    def do_quit(self, line):
        self.closeAll()

    def closeAll(self):
        simgo.cancel()
        return exit(0)
    
if __name__ == '__main__':

    arguments = docopt(__doc__, version='simgo task 0.1')

    logging.basicConfig()    
    logger = logging.getLogger('simgo')
    logger.setLevel(logging.INFO)
    
    configurationStr = arguments['--pipeline']
    if (not configurationStr):
        logger.error("Please configure the pipeline, for example, GTPBTR")
        exit(-1)
        

    if (configurationStr == "GTBBTR"):
    elif (configurationStr == "GTPPTR"):
    elif (configurationStr == "GTBPTR"):
    elif (configurationStr == "GTPBTR"):
    else:
        logger.error("Pipeline configuration is not supported {0}".format(configurationStr))
        exit(-1)
        

        
    # Enter main command loop if interactive mode is enabled
    c = cmdGroundLevel()
    while (True):
        try:
            c.cmdloop()
        except KeyboardInterrupt:
            logger.error("Use command 'exit' to exit")
