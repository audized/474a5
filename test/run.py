#!/usr/bin/env python
# coding=utf8

# CMPT 474, Spring 2014, Assignment 5 run file

# Core libraries
import math
import random
import string
import StringIO
import itertools
import functools

# Standard libraries for interacting with OS
import os
import time
import json
import shutil
import argparse
import urlparse
import subprocess

# Extend path to our containing directory, so we can import vectorclock
import sys
sys.path.append(sys.path[0]+'/..')

# Libraries that have to have been installed by pip
import redis
import requests
from termcolor import colored

# File distributed with assignment boilerplate
from vectorclock import VectorClock


class HTTPOutput():
	def __init__(self, url):
		self.url = url
	def write(self, data):
		requests.post(self.url, data=data, headers={ 'Content-type': 'application/json' })
	def flush(self):
		pass

parser = argparse.ArgumentParser(description='Process.')

parser.add_argument('--key',
                    dest='key',
                    action='store',
                    nargs='?',
                    default=''.join(random.sample((string.ascii_uppercase + 
                                                   string.digits)*10, 10)),
                    help='random nonce')

parser.add_argument('--results',
                    dest='output',
                    action='store',
                    nargs='?',
                    default=None,
                    help='where to send results (default stdout); can be url or file')

parser.add_argument('--leavedb',
                    action='store_true',
                    help='leave the database after termination')

parser.add_argument('--test',
                    dest='test',
                    action='store',
                    nargs='?',
                    default=None,
                    help='name of single test to run')

args = parser.parse_args()
if args.output:
	url = urlparse.urlparse(args.output)
	if not url.scheme:
		output = file(url.path, 'w')
	else:
		output = HTTPOutput(urlparse.urlunparse(url))
else:
	output = sys.stdout

# Seed the random number generator with a known value
random.seed(args.key)

n = 1  # Only a single server in this assignment
port = 5555

base = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
log = os.path.join(base, 'var', 'log')
db = os.path.join(base, 'var', 'db')

if os.path.exists(log): shutil.rmtree(log)
if os.path.exists(db): shutil.rmtree(db)

os.makedirs(log)
os.makedirs(db)

configs = [ { 'id': str(i), 'host': 'localhost', 'port': port+i } for i in range(n) ]
processes =	[ subprocess.Popen(['redis-server',
                                '--port', str(config['port']),
                                '--bind', '127.0.0.1',
                                '--logfile', os.path.join(log, 'server'+config['id']+'.log'),
                                '--dbfilename', 'server'+config['id']+'.rdb',
                                '--databases', '1',
                                '--dir', db ])
                                for config in configs ]
clients = [ redis.StrictRedis(host=config['host'], port=config['port'], db=0) for config in configs ]

server = subprocess.Popen(['python', os.path.join(base, 'server.py'), json.dumps({ 'servers': configs })])
ITEM = 'bob'
endpoint = 'http://localhost:2500'

def get(id):
	headers = { 'Accept': 'application/json' }
	url = endpoint+'/rating/'+id
	try:
		request = requests.get(url, headers=headers)
		data = request.json()
	except:
		raise Exception('Invalid request: %s HTTP %d  %s' % (url, request.status_code, request.text))

	try:
		rating = float(data['rating'])
	except:
		rating = data['rating']

	choices = json.loads(data['choices'])
	#TODO: Handle return of malformed vector clock
	clocks = json.load(StringIO.StringIO(data['clocks']))
	return rating, choices, [VectorClock.fromDict(vcstr) for vcstr in clocks]

def put(id, rating, clock):
	headers = { 'Accept': 'application/json', 'Content-type': 'application/json' }
	data = json.dumps({ 'rating': rating, 'clocks': clock.clock })
	requests.put(endpoint+'/rating/'+id, headers=headers, data=data)

def result(r):
	output.write(json.dumps(r)+'\n')
	output.flush()

def testResult(rgot, rexp, choicesgot, choicesexp, clocksgot, clocksexp):
    result({ 'type': 'EXPECT_RATING', 'got': rgot, 'expected': rexp})
    result({ 'type': 'EXPECT_CHOICES', 'got': choicesgot, 'expected': choicesexp })
    result({ 'type': 'EXPECT_CLOCKS', 'got': [c.asDict() for c in clocksgot], 'expected' : [c.asDict() for c in clocksexp] })

def getAndTest(item, rexp, choicesexp, clocksexp):
    r, ch, cl = get(item)
    testResult(r, rexp, ch, choicesexp, cl, clocksexp)

def makeVC(cl, count):
    return VectorClock().update(cl, count)

def info(msg):
	sys.stdout.write(colored('ℹ', 'green')+' '+msg+'\n')
	sys.stdout.flush()

def flush():
	for client in clients:
		client.flushall()

def count():
	return sum(map(lambda c:c.info()['total_commands_processed'],clients))

def sum(l):
	return reduce(lambda s,a: s+a, l, float(0))

def mean(l):
	return sum(l)/len(l)

def variance(l):
	m = mean(l)
	return map(lambda x: (x - m)**2, l)

def stddev(l):
	return math.sqrt(mean(variance(l)))

def usage():
	def u(i):
		return i['db0']['keys'] if 'db0' in i else 0
	return [ u(c.info()) for c in clients ]


print("Running test #"+args.key)

# Some general information
result({ 'name': 'info', 'type': 'KEY', 'value': args.key })
result({ 'name': 'info', 'type': 'SHARD_COUNT', 'value': n })

# Give the server some time to start up
time.sleep(1)

tests = [ ]
def test():
	def wrapper(f):
		def rx(obj):
			x = obj.copy()
			obj['name'] = f.__name__
			result(obj)
		@functools.wraps(f)
		def wrapped(*a):
			info("Running test %s" % (f.__name__))
			# Clean the database before subsequent tests
			flush()
			# Reset the RNG to a known value
			random.seed(args.key+'/'+f.__name__)
			f(rx, *a)
		tests.append(wrapped)
		return wrapped
	return wrapper

@test()
def simple(result):
	# Simple write to empty item should be unique
    rating  = 5
    time = 1
    cv = VectorClock().update('c0', time)
    put(ITEM, rating, cv)
    r, choices, clocks = get(ITEM)
    testResult(r, rating, choices, [rating], clocks, [cv])

@test()
def moreRecentData(result):
    # Overwrite with more recent data
    put(ITEM, 5, VectorClock().update('c0', 1))
    finalr = 1
    finalvc =  VectorClock().update('c0', 3)
    put(ITEM, finalr, finalvc)
    r, choices, clocks = get(ITEM)
    testResult(r, finalr, choices, [finalr], clocks, [finalvc])

@test()
def staleData(result):
    # Ignore stale data
    finalr = 5
    finalvc = VectorClock().update('c0', 5)
    put(ITEM, finalr, finalvc)
    put(ITEM, 1, VectorClock().update('c0', 1))
    r, choices, clocks = get(ITEM)
    testResult(r, finalr, choices, [finalr], clocks, [finalvc])

@test()
def inComparableData(result):
    # Two incompatible writes
    r1 = 5
    vc1 = VectorClock().update('c0', 5)
    r2 = 2
    vc2 = VectorClock().update('c1', 3)
    put(ITEM, r1, vc1)
    put(ITEM, r2, vc2)
    r, choices, clocks = get(ITEM)
    testResult(r, (r1+r2)/2.0, choices, [r1, r2], clocks, [vc1, vc2])

@test()
def coalescableData(result):
    # More recent value overrides two earlier values
    r1 = 5
    vc1 = VectorClock().update('c0',5)
    r2 = 2
    vc2 = VectorClock().update('c1',3)
    put(ITEM, r1, vc1)
    put(ITEM, r2, vc2)
    r3 = 3
    vc3 = VectorClock().update('c0',7).update('c1',10)
    put(ITEM, r3, vc3)
    r, choices, clocks = get(ITEM)
    testResult(r, r3, choices, [r3], clocks, [vc3])

@test()
def longerSequence(result):
    # Long sequence of updates
    vc4 = makeVC('c4',100)
    put(ITEM, 10, vc4)
    getAndTest(ITEM, 10, [10], [vc4])

    vc5 = makeVC('c5',6)
    put(ITEM, 2, vc5)
    getAndTest(ITEM, 6, [10, 2], [vc4, vc5])

    vc23 = makeVC('c23',12)
    put(ITEM, 3, vc23)
    getAndTest(ITEM, 5, [10, 2, 3], [vc4, vc5, vc23])

    vc5_23 = makeVC('c5', 21).update('c23', 13)
    put(ITEM, 8, vc5_23)
    getAndTest(ITEM, 9, [10, 8], [vc4, vc5_23])

    vc4_5 = makeVC('c4', 101).update('c5', 6)
    put(ITEM, 6, vc4_5)
    getAndTest(ITEM, 7, [6, 8], [vc4_5, vc5_23])

    vc5_23_bis = makeVC('c5', 21).update('c23', 21)
    put(ITEM, 2, vc5_23_bis)
    getAndTest(ITEM, 4, [6, 2], [vc4_5, vc5_23_bis])

    vc4_5_23 = makeVC('c4',102).update('c5',21).update('c23',12)
    put(ITEM, 20, vc4_5_23)
    getAndTest(ITEM, 11, [20,2], [vc4_5_23, vc5_23_bis])

    vc4_23 = makeVC('c4',99).update('c23',12)
    put(ITEM, 30, vc4_23) # No effect---outdated clock
    getAndTest(ITEM, 11, [20,2], [vc4_5_23, vc5_23_bis])

    vc4_5_23_bis = makeVC('c4',102).update('c5',21).update('c23',40)
    put(ITEM, 18, vc4_5_23_bis)
    getAndTest(ITEM, 18, [18], [vc4_5_23_bis])

# Go through all the tests and run them
try:
    for test in tests:
        if args.test == None or args.test == test.__name__:
            test()
finally:
    # Shut. down. everything.
    server.terminate()
    if not args.leavedb:
        for p in processes: p.terminate()

# Fin.
