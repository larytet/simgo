#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Simgo Task 1.

Usage:
  task1.py -h | --help
  task1.py --version
  task1.py [--device=<STR>] -i | --interactive  
  task1.py run [--device=<STR>] [--filename=<STR>] [--address=<HEX>] [--interactive]  

Options:
  -h --help            Show this screen.
  --version            Show version.
  
"""

import cmd
from docopt import docopt
import logging
from collections import namedtuple
from time import sleep
import threading
import subprocess
import serial, random, time

import sys, traceback
import os
import re



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

class Sound:
    def __init__(self):
        self.lock = threading.Lock()
        self.__canceled = False
        self.__disabled = False
        self.__running = False
        
    def cancel(self):
        self.__canceled = True

    def disable(self):
        self.__disabled = True

    def playSoundThread(self, args):
        '''
        Sometime ALSA returns error 
        /usr/bin/play WARN alsa: under-run
        '''
        
        if (self.__canceled or self.__disabled or self.__running):
            return
        
        self.lock.acquire()
        
        self.__running = True
        
        for _ in range(10):
            if (self.__canceled or self.__disabled):
                break
            os.system("/usr/bin/play --no-show-progress --null --channels 1 synth 0.05 sine 400")
            
        self.__running = False
        
        self.lock.release()

    def playSound(self):
        '''
        Execute system 'beep' in the backgorund
        '''
        self.__canceled = False
        threading.Thread(target=self.playSoundThread, args=([None])).start()    

beepSound = Sound()

class ByteGenerator(threading.Thread):
    '''
    Wake up periodically and generate a packet of data 
    '''
    def __init__(self, maximumPacketSize=7, period=0.4):
        '''
        Byte generator generates packets between 0 and maximumPacketSize bytes
        The generator wakes up every "period" seconds
        @param maximumPacketSize - maximum packet size to generate
        @param period - sleep time between the packets  
        '''
        self.maximumPacketSize = maximumPacketSize
'''
List of commands which will not be repeated when entering an empty line
'''
NOT_AUTO_COMMANDS = []

def nonautomatic(decorator):
    '''
    Decorator - if used add the command to the global list NOT_AUTO_COMMANDS
    Code below is executed before the decorated function is executed
    '''
    
    def new_decorator(*arg):
        '''
        This function will replace the decorated function
        Arbitrary list of arguments - usualy 'self' and 'line', but I do not care
        '''
        decorator(*arg)

    # get the funciton name and drop leading do_
    pattern = "do_(.+)"
    m = re.match(pattern, decorator.__name__)
    command = m.group(1)
    
    # add the function name to the black list
    NOT_AUTO_COMMANDS.append(command)

    return new_decorator
 
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

    def precmd(self, line):
        '''
        Handle simple scripts - single line which contains commands separated by ';'
        '''
        if (";" in line):
            commands = line.split(";")
            for command in commands:
                if (command != ""):
                    self.onecmd(command)
            return "none"
        else:
            return line
              
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
        
      
    def do_status(self, line):
        pass
        
            
        
    def help_status(self):
        print "Print systems status, like last commands, last used address, connection state"
        print "Usage:status [brief|full]"
    

    def do_exit(self, line):
        self.closeAll()
        
    def do_quit(self, line):
        self.closeAll()
    BEEP_COMMANDS_TEST = ['test', 'start']
        
    BEEP_COMMANDS_CANCEL = ['cancel', 'exit', 'stop']
    BEEP_COMMANDS_COMPLETION = ['cancel', 'test']
    def do_beep(self, command):
        '''
        beep [cancel|test]
        '''        
        if ((command in self.BEEP_COMMANDS_TEST) or (not command)):
            beepSound.playSound()
        elif (command in self.BEEP_COMMANDS_CANCEL):
            beepSound.cancel()
        
    def complete_beep(self, text, line, begidx, endidx):
        if (not text):
            completions = self.BEEP_COMMANDS_COMPLETION[:]
        else:
            completions = []
            for f in self.BEEP_COMMANDS_COMPLETION:
                if (f.startswith(text)):
                    completions.append(f)

        return completions

    def help_beep(self):
        print "Test system beep"
        print "Usage: beep [test|start|cancel|exit|stop]"

    def closeAll(self):
        beepSound.disable()
        simgo.cancel()
        return exit(0)
    
if __name__ == '__main__':

    arguments = docopt(__doc__, version='simgo task 0.1')

    logging.basicConfig()    
    logger = logging.getLogger('simgo')
    logger.setLevel(logging.INFO)    

        
    # Enter main command loop if interactive mode is enabled
    c = cmdGroundLevel()
    while (True):
        try:
            c.cmdloop()
        except KeyboardInterrupt:
            logger.error("Use command 'exit' to exit")
