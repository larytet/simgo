#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simgo Task 1.

Usage:
  task1.py -h | --help
  task1.py --version
  task1.py pipeline --stages=<STR>   

Options:
  -h --help            Show this screen.
  --version            Show version.
  --stages=<STR>     Configure the pipeline.
  
Examples:
   # Configure Byte Generator -> Transport -> PacketPHY -> BytePHY -> Transport -> Byte Printer
  ./task1.py pipeline --stages GTPBTR
  
   # Configure Byte Generator -> Transport -> BytePHY -> BytePHY -> Transport -> Byte Printer
  ./task1.py pipeline --stages GTBBTR
  
  Also:
  ./task1.py pipeline --stages GTPPTR
  ./task1.py pipeline --stages GTBPTR
"""

import cmd
import logging
from time import sleep
import threading
import random, time

import os

try:
    from docopt import docopt
except:
    print "docopt is required to run this script"
    print "On Ubuntu try 'apt-get install python-docopt'"


def buildhexstring(value, width=0, prefix=''):
    '''
    Get an integer, return a formatted string 
    For example if value is 0x1E55, widht=8 will retun "00001E55"  
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
        s = s + "{0}".format(buildhexstring(c, 2)) + " "
    return s

def convertToFloat(s):
    '''
    Convert string to float, handle exception
    Return True if conversion is Ok
    '''
    value = None;
    try:
        value = float(s)
        result = True;
    except:
        logger.error("Bad formed number '{0}'".format(s));
        result = False;
    return (result, value);


class StatManager:
    '''
    A single place where references to all blocks of debug counters are stored
    Counters divided in groups, for example a group of ETH counters
    Every group can contain zero or more blocks (eth0, eth1, ...)
    Every block contains zero or more debug counters
    A debug counter is usually an integer or any printable object  
    '''
    def __init__(self):
        self.groups = {}

    class Block:
        '''
        Useful when there are many instances of the same set of counters. 
        For example counter for "eth0", "eth1"
        '''
        def __init__(self, name):
            '''
            @param name is a name of the block. 
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
        '''
        I print only counters in the block object, ignore Python internal fields
        '''
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
    A pipeline stage has a name, reference to the next stage
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
        self.maximumBurstSize, self.period = maximumBurstSize, period
        
        self.stat = StatManager.Block("")
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "zeroPackets", "noSink"])
        statManager.addCounters("ByteGenerator", self.stat)
        self.exitFlag = False
        
    def run(self):
        '''
        Wake, generate a packet, go to sleep
        '''
        while (not self.exitFlag):
            time.sleep(self.period)
            packetSize = random.randint(0, self.maximumBurstSize)
            packet = os.urandom(packetSize)
            self.stat.wakeups = self.stat.wakeups + 1
            packetLen = len(packet)
            if (packetLen > 0):
                self._sendBytes(packet, packetLen)
            else:
                self.stat.zeroPackets = self.stat.zeroPackets + 1
                
                
    def _sendBytes(self, packet, packetLen):
        '''
        Send the generated bytes to the next stage if any
        '''            
        if (self.nextStage != None):
            self.stat.packets = self.stat.packets + 1
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
        self.lock = threading.Lock()
        self.stat = StatManager.Block("")
        self.stat.addFieldsInt(["wakeups", "packets", "bytes"])
        statManager.addCounters("BytePrinter", self.stat)
        self.printEnabled = True

    def tx(self, packet):
        '''
        A data sink which prints bytes. This method is reentrant
        '''
        dataStr = bytesToHexString(packet)

        self.lock.acquire()
        if (self.printEnabled):
            print dataStr   
        self.stat.wakeups = self.stat.wakeups + 1
        self.stat.packets = self.stat.packets + 1
        packetLen = len(packet)
        self.stat.bytes = self.stat.bytes + packetLen
        self.lock.release()
        
    def enable(self, flag):
        self.printEnabled = flag

    def isEnabled(self):
        return self.printEnabled
        
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
            self.nextStage.tx(data)
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
        self.txTimer = None
        
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "noSink", "timerStarted", "timerExpired", "timerCanceled"])
        statManager.addCounters("PacketPHY", self.stat)
        
        self.collectedData = []

    def tx(self, data):
        '''
        A data sink which collects bytes and sends packets to the next stage
        '''
        self.lock.acquire()
        
        self.stat.wakeups = self.stat.wakeups + 1
        
        # Start timer on the first arriving byte
        self._startTimer()

        for b in data:
            self.collectedData.append(b)
        packetLen = len(self.collectedData)
        if (packetLen > self.minimumPacketSize):
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
            self.txTimer = threading.Timer(1.0, self.timeoutExpired)
            self.txTimer.start()
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
        self.lock = threading.Lock()
        self.name = name
        self.stat = StatManager.Block(name)
        self.stat.addFieldsInt(["wakeups", "packets", "bytes", "noSink"])
        statManager.addCounters("BytePHY", self.stat)

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
            self.nextStage.tx(data)
        else:
            self.stat.noSink = self.stat.noSink + 1

 
class cmdGroundLevel(cmd.Cmd):
    '''
    Interactive command line interface 
    '''
    
    def init(self, byteGenerator, bytePrinter):
        '''
        I can not subclass old style class
        '''
        self.byteGenerator = byteGenerator
        self.bytePrinter = bytePrinter

    def emptyline(self):
        '''
        If empty line repeat last sent command, unless this is run
        '''
        
        lastcmd = self.lastcmd
        if ((lastcmd == "") or (lastcmd == None)):
            return
        
        words = lastcmd.split()
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
    
if __name__ == '__main__':

    arguments = docopt(__doc__, version='simgo task 0.1')

    logging.basicConfig()    
    logger = logging.getLogger('simgo')
    logger.setLevel(logging.INFO)

    if (not ('--stages' in arguments)):     
        logger.error("Please configure the pipeline, for example, pipeline --stages GTPBTR")
        exit(-1)
        
    configurationStr = arguments['--stages']
        
    bytePrinter = BytePrinter()
    byteGenerator = ByteGenerator()
    transport0 = Transport("transport0")
    transport1 = Transport("transport1")
    byteGenerator.setNext(transport0)
    transport1.setNext(bytePrinter)

    if (configurationStr == "GTBBTR"):
        bytePhy0 = BytePHY("bytePhy0")
        bytePhy1 = BytePHY("bytePhy1")
        transport0.setNext(bytePhy0)
        bytePhy0.setNext(bytePhy1)
        bytePhy1.setNext(transport1)
        
    elif (configurationStr == "GTPPTR"):
        packetPhy0 = PacketPHY("packetPhy0")
        packetPhy1 = PacketPHY("packetPhy1")
        transport0.setNext(packetPhy0)
        packetPhy0.setNext(packetPhy1)
        packetPhy1.setNext(transport1)

    elif (configurationStr == "GTBPTR"):
        bytePhy0 = BytePHY("bytePhy0")
        packetPhy0 = PacketPHY("packetPhy0")
        transport0.setNext(bytePhy0)
        bytePhy0.setNext(packetPhy0)
        packetPhy0.setNext(transport1)
        
    elif (configurationStr == "GTPBTR"):
        bytePhy0 = BytePHY("bytePhy0")
        packetPhy0 = PacketPHY("packetPhy0")
        transport0.setNext(packetPhy0)
        packetPhy0.setNext(bytePhy0)
        bytePhy0.setNext(transport1)
        
    else:
        logger.error("Pipeline configuration is not supported {0}".format(configurationStr))
        exit(-1)
        

    byteGenerator.start()
        
    # Enter main command loop if interactive mode is enabled
    c = cmdGroundLevel()
    c.init(byteGenerator, bytePrinter)
    while (True):
        try:
            c.cmdloop()
        except KeyboardInterrupt:
            logger.error("Use command 'exit' to exit")
