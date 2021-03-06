#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simgo Task 1.

Usage:
  task1.py -h | --help
  task1.py --version
  task1.py pipeline --stages=<CONF>   

Options:
  -h --help            Show this screen.
  --version            Show version.
  --stages <CONF>      Configuration of the pipeline (GTPBTR|GTBBTR|GTPPTR|GTBPTR)
  
Examples:
   # Configure Byte Generator -> Transport -> PacketPHY -> BytePHY -> Transport -> Byte Printer
  ./task1.py pipeline --stages GTPBTR
"""

import cmd
import logging
from time import sleep
import threading, collections
import random, time

import os

try:
    from docopt import docopt
except:
    print "docopt is required to run this script"
    print "On Ubuntu try 'apt-get install python-docopt' or 'pip install docopt'"
    exit(-1)


def buildHexString(value, width=0, prefix=''):
    '''
    Get an integer, return a formatted string 
    For example if value is 0x1E55, width=8 this function will retun "00001E55"
    @param value: an integer to convert
    @param width: min length of the resulting string, padded by zeros
    @param prefix: for example '0x'
    @return: a hexadecimal string representation of the value     
    '''
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
    Convert an array of bytes to string 
    For example will convert [0x30, 0x31] to string "30 31"
    '''
    s = ""
    for c in data:
        s = s + "{0}".format(buildHexString(c, 2)) + " "
    return s

def convertToFloat(s):
    '''
    Convert string to float, handle exception
    Return non-None if conversion is Ok
    '''
    value = None;
    try:
        value = float(s)
    except:
        logger.error("Bad formed number '{0}'".format(s));
    return value;


class StatManager:
    '''
    A single place where references to all blocks of debug counters are stored
    All system statistics is divided by groups, for example a group of ETH counters
    Every group contains zero or more blocks (eth0, eth1, ...)
    Every block contains zero or more debug counters
    A debug counter is usually an integer or any printable object  
    '''
    def __init__(self):
        self.groups = {}
        # I use fieldLength when formating the print of the counters tables
        self.fieldLength = 1

    class Block:
        '''
        Useful when there are many instances of the same set of counters. 
        For example counter for "eth0", "eth1"
        '''
        def __init__(self, name=""):
            '''
            @param name is a name of the block. 
            '''
            self.name = name
            self.fieldsToPrint = []
            
            # Fields in the Block object are ordered as inserted 
            self.__dict__ = collections.OrderedDict(sorted(self.__dict__.items()))
            
            # I use fieldLength when formating the print of the counters tables
            self.fieldLength = 1

        
        def addField(self, (name, initialValue)):
            '''
            Add a field with specified name
            @param name is a name of the counter, for example "tx"
            '''
            self.__dict__[name] = initialValue
            self.fieldsToPrint.append(name)
            self.fieldLength = max(self.fieldLength, len(name))


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
        self.fieldLength = max(self.fieldLength, block.fieldLength)

    def printGroup(self, groupName):
        '''
        Print counters from the specified by name group 
        '''
        counters = self.groups[groupName]
        if (len(counters) <= 0):
            return
        
        fieldLength = self.fieldLength
        fieldPattern = '{:>'+str(fieldLength)+'}'
            
        # Print column names
        print fieldPattern.format(groupName),
        o = counters[0]
        for fieldName in o.fieldsToPrint:
            print fieldPattern.format(fieldName),
        print

        # Print a line of dashes
        separator = "-" * fieldLength;
        separator = (separator + " ") * (len(o.fieldsToPrint) + 1)  
        print separator
             
        # Print table data
        for counter in counters:
            # Print the name of the counter block
            print fieldPattern.format(counter.name),
            # Print the fields in the insertion order
            for fieldName in counter.fieldsToPrint:
                print fieldPattern.format(counter.__dict__[fieldName]),
            # New line after every block
            print
        
    def printAll(self):
        '''
        Print counters from all registered groups
        '''
        for groupName in self.groups:
            self.printGroup(groupName)
            print
            
'''
All debug statisitcs is collected here 
'''
statManager = StatManager()

class PipelineStage():
    '''
    A stage of the pipeline
    A pipeline stage has a name, reference to the next stage
    '''
    def __init__(self, name):
        self.nextStage = None
        self.name = name
        # all stages need a lock
        self.lock = threading.Lock()

    def setNext(self, nextStage):
        '''
        Set next stage of the pipeline - a "sink" where to send the packets
        @param nextStage is an object which contains method tx()
        '''    
        self.nextStage = nextStage

         
    def tx(self, packet):
        '''
        Do nothing in the base class
        '''
        logger.error("Method tx() is called for the abstract pipeline stage");
        pass
        
    def getName(self):
        return self.name
        
    def setName(self, name):
        self.name = name
    
class ByteGenerator(threading.Thread, PipelineStage):
    '''
    Feeds bytes to the first stage of the data pipeline
    Wake up periodically and generate a burst of data
    The burst size and burst data are random   
    '''
    def __init__(self, maximumBurstSize=7, period=0.4):
        '''
        @param maximumBurstSize - maximum burst size to generate, the length is random
        @param period - sleep time between the burst  
        '''
        super(ByteGenerator, self).__init__()
        PipelineStage.__init__(self, "ByteGenerator")
        self.maximumBurstSize, self.period = maximumBurstSize, period
        
        self.stat = StatManager.Block()
        self.stat.addFieldsInt(["wakeups", "bursts", "bytes", "zeroPackets", "noSink", "lastBurstSize"])
        statManager.addCounters(self.name, self.stat)
        self.exitFlag = False
        
    def run(self):
        '''
        Wake up, generate a packet, go to sleep
        '''
        while (not self.exitFlag):
            time.sleep(self.period)
            packetSize = random.randint(0, self.maximumBurstSize)
            packet = os.urandom(packetSize)
            self.stat.wakeups = self.stat.wakeups + 1
            packetLen = len(packet)
            self.stat.lastBurstSize = packetLen; 
            if (packetLen > 0):
                self._sendBytes(packet, packetLen)
            else:
                self.stat.zeroPackets = self.stat.zeroPackets + 1
                
                
    def _sendBytes(self, packet, packetLen):
        '''
        Send the generated bytes to the next stage if any
        '''            
        if (self.nextStage != None):
            self.stat.bursts = self.stat.bursts + 1
            self.stat.bytes = self.stat.bytes + packetLen
            for b in packet:
                dataByte = ord(b)
                self.nextStage.tx([dataByte])
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
        PipelineStage.__init__(self, "BytePrinter")
        self.stat = StatManager.Block()
        self.stat.addFieldsInt(["wakeups", "packets", "bytes"])
        statManager.addCounters(self.name, self.stat)
        self.printEnabled = True

    def tx(self, packet):
        '''
        A data sink which prints bytes. This method is reentrant
        '''
        dataStr = bytesToHexString(packet)
        packetLen = len(packet)

        self.lock.acquire()
        if (self.printEnabled):
            print dataStr   
        self.stat.wakeups = self.stat.wakeups + 1
        self.stat.packets = self.stat.packets + 1
        self.stat.bytes = self.stat.bytes + packetLen
        self.lock.release()
        
    def enable(self, flag):
        '''
        Toggle printing On/Off
        '''
        self.printEnabled = flag

    def isEnabled(self):
        '''
        Get currect state of the printEnabled flag
        '''
        return self.printEnabled
        
class Transport(PipelineStage):
    '''
    Second stage of the pipeline
    '''
    def __init__(self, name):
        PipelineStage.__init__(self, name)
        self.stat = StatManager.Block(name)
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "bytes", "noSink"])
        statManager.addCounters("Transport", self.stat)

    def tx(self, data):
        '''
        A data sink which forwards packets to the next stage in the pipeline
        '''
        packetLen = len(data)
        
        self.lock.acquire()
        self.stat.wakeups = self.stat.wakeups + 1
        self.lock.release()
        
        if (self.nextStage != None):
            self.stat.packets = self.stat.packets + 1
            self.stat.bytes = self.stat.bytes + packetLen
            self.nextStage.tx(data)
        else:
            self.stat.noSink = self.stat.noSink + 1

class PacketPHY(PipelineStage):
    '''
    Packet PHY pipeline stage 
    Collect incoming bytes, send a single packet when 10 bytes or more collected 
    or timeout expires 
    '''
    def __init__(self, name, minimumPacketSize=10, timeout=1.0):
        PipelineStage.__init__(self, name)
        self.minimumPacketSize = minimumPacketSize
        self.timeout = timeout
        self.stat = StatManager.Block(name)
        self.txTimer = None
        
        self.stat.addFieldsInt(["wakeups", "packetsIn", "packetsOut", "bytesIn", "bytesOut", "noSink", "timerStarted", "timerExpired", "timerCanceled"])
        statManager.addCounters("PacketPHY", self.stat)
        
        self.collectedData = []

    def tx(self, data):
        '''
        A data sink which collects bytes and sends packets to the next stage
        '''
        self.lock.acquire()
        
        self.stat.wakeups = self.stat.wakeups + 1
        self.stat.bytesIn = self.stat.bytesIn + len(data)
        self.stat.packetsIn = self.stat.packetsIn + 1
        
        # Start timer on the first arriving byte
        if (len(self.collectedData) == 0): 
            self._startTimer()

        self.collectedData = self.collectedData + data
        packetLen = len(self.collectedData)
        if (packetLen > self.minimumPacketSize):
            self._sendBytes(self.collectedData)

        self.lock.release()
        
    def _sendBytes(self, packet):
        '''
        Forward bytes to the next stage
        '''            
        if (self.nextStage != None):
            self.stat.packetsOut = self.stat.packetsOut + 1
            self.stat.bytesOut = self.stat.bytesOut + len(packet)
            self.nextStage.tx(packet)
            self._flushData()
        else:   
            self.stat.noSink = self.stat.noSink + 1
        
    def _startTimer(self):
        '''
        Cancel the timer if running
        Start timer on the first arriving byte
        '''
        if (self.txTimer):
            self.txTimer.cancel()
            self.stat.timerCanceled = self.stat.timerCanceled + 1
        self.txTimer = threading.Timer(self.timeout, self.timeoutExpired)
        self.txTimer.start()
        self.stat.timerStarted = self.stat.timerStarted + 1

            
    def timeoutExpired(self):
        '''
        If timer expired send all collected data to the next stage
        of the pipeline
        '''
        
        self.lock.acquire()
        
        self.stat.timerExpired = self.stat.timerExpired + 1
        packetLen = len(self.collectedData)
        if (packetLen > 0):
            self._sendBytes(self.collectedData)
            
        self.lock.release()
            
    def _flushData(self):
        '''
        Drop all collected data, stop timer
        '''
        del self.collectedData[:]
        if (self.txTimer):
            self.txTimer.cancel()

class BytePHY(PipelineStage):
    '''
    Get bytes, forward the bytes to the next stage
    '''
    def __init__(self, name):
        PipelineStage.__init__(self, name)
        self.stat = StatManager.Block(name)
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "noSink"])
        statManager.addCounters("BytePHY", self.stat)

    def tx(self, data):
        '''
        A data sink which forwards packets to the next stage in the pipeline
        '''
        packetLen = len(data)

        self.lock.acquire()
        self.stat.wakeups = self.stat.wakeups + 1
        self.lock.release()
        
        if (self.nextStage != None):
            self.stat.bytes = self.stat.bytes + packetLen
            self.stat.packets = self.stat.packets + 1
            self.nextStage.tx(data)
        else:
            self.stat.noSink = self.stat.noSink + 1

 
class cmdGroundLevel(cmd.Cmd):
    '''
    Interactive command line interface 
    '''
    
    def init(self, byteGenerator, bytePrinter):
        '''
        I can not subclass old style class. This is a limitation of
        the cmd package
        '''
        self.byteGenerator = byteGenerator
        self.bytePrinter = bytePrinter
        self.doNotRepeat = ["enable"]

    def emptyline(self):
        '''
        If empty line repeat last sent command
        '''
        
        lastcmd = self.lastcmd
        if ((lastcmd == "") or (lastcmd == None)):
            return
        if (lastcmd in self.doNotRepeat):
            return
        
        words = lastcmd.split()
        self.onecmd(lastcmd.strip())

              
    def do_none(self, line):
        pass

    def do_sleep(self, line):
        t = convertToFloat(line)
        if (t):
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
      
    def do_enable(self, line):
        self.bytePrinter.enable(not self.bytePrinter.isEnabled())
        
    def help_enable(self):
        print "Toggle printing"

    def do_exit(self, line):
        self.closeAll()
        
    def do_quit(self, line):
        self.closeAll()

    def closeAll(self):
        byteGenerator.cancel()
        return exit(0)

def initPipeline(configurationStr):
    '''
    Create and link stages of the pipeline
    '''
    if (configurationStr == "GTBBTR") : (stage1, stage2) = (BytePHY("bytePhy0"), BytePHY("bytePhy1")); 
    elif (configurationStr == "GTPPTR") : (stage1, stage2) = (PacketPHY("packetPhy0"), PacketPHY("packetPhy1")); 
    elif (configurationStr == "GTBPTR") : (stage1, stage2) = (BytePHY("bytePhy0"), PacketPHY("packetPhy0"));
    elif (configurationStr == "GTPBTR") : (stage1, stage2) = (PacketPHY("packetPhy0"), BytePHY("bytePhy0"));
    else:
        logger.error("Pipeline configuration '{0}' is not supported".format(configurationStr))
        return (False, None, None)

    bytePrinter = BytePrinter()
    byteGenerator = ByteGenerator()
    transport0 = Transport("transport0")
    transport1 = Transport("transport1")
    byteGenerator.setNext(transport0)
    transport1.setNext(bytePrinter)

    transport0.setNext(stage1)
    stage1.setNext(stage2)
    stage2.setNext(transport1)
        
    return (True, byteGenerator, bytePrinter)


def startPipeline():
    '''
    Start random data generator
    '''
    byteGenerator.start()
        
if __name__ == '__main__':

    arguments = docopt(__doc__, version='simgo task 0.1')

    logging.basicConfig()    
    logger = logging.getLogger('simgo')
    logger.setLevel(logging.INFO)

    configurationStr = arguments['--stages']
    (res, byteGenerator, bytePrinter) = initPipeline(configurationStr)
    if (not res):
        exit(-1)

    startPipeline()        
        
    # Enter main command loop 
    c = cmdGroundLevel()
    c.init(byteGenerator, bytePrinter)
    # Print CLI help
    c.do_help(None)
    while (True):
        try:
            c.cmdloop()
        except KeyboardInterrupt:
            logger.error("Use command 'exit' to exit")
