#  CMPT 474 Spring 2014, Assignment 5 boilerplate

# Imports from standard library
import os
import sys
import time
import json
import StringIO

# Imports from installed libraries
import redis
import mimeparse
from bottle import route, run, request, response, abort

# Imports from boilerplate
from vectorclock import VectorClock

config = { 'servers': [{ 'host': 'localhost', 'port': 6379 }] }

if (len(sys.argv) > 1):
	config = json.loads(sys.argv[1])

# Connect to a single Redis instance
client = redis.StrictRedis(host=config['servers'][0]['host'], port=config['servers'][0]['port'], db=0)

# A user updating their rating of something which can be accessed as:
# curl -XPUT -H'Content-type: application/json' -d'{ "rating": 5, "clock": { "c1" : 5, "c2" : 3 } }' http://localhost:2500/rating/bob
# Response is a JSON object specifying the new rating for the entity:
# { rating: 5 }
@route('/rating/<entity>', method='PUT')
def put_rating(entity):

	# Check to make sure JSON is ok
	type = mimeparse.best_match(['application/json'], request.headers.get('Accept'))
	if not type: return abort(406)

	# Check to make sure the data we're getting is JSON
	if request.headers.get('Content-Type') != 'application/json': return abort(415)

	response.headers.append('Content-Type', type)
	
	# Read the data sent from the client
	data = json.load(request.body)
	setrating = data.get('rating')
	setclock = VectorClock.fromDict(data.get('clocks'))

	# Basic sanity checks on the rating
	if isinstance(setrating, int): setrating = float(setrating)
	if not isinstance(setrating, float): return abort(400)

	# Weave the new rating into the current rating list
	key = '/rating/'+entity

	# YOUR CODE GOES HERE
	# REPLACE THE FOLLOWING LINE
	finalrating = setrating
	# SET THE RATING, CHOICES, AND CLOCKS IN THE DATABASE FOR THIS KEY
	# COMPUTE THE MEAN, finalrating

	# HINT: CONSIDER USING THE HASH DATA TYPE IN REDIS (HGET/HSET/...)

	# Return the new rating for the entity
	return {
		"rating": finalrating
	}


# Add a route for getting the aggregate rating of something which can be accesed as:
# curl -XGET http://localhost:2500/rating/bob
# Response is a JSON object specifying the rating list and time list for the entity:
# { rating: 5, choices: [5], clocks: [{c1: 3, c4: 10}] }
@route('/rating/<entity>', method='GET')
def get_rating(entity):
	# YOUR CODE GOES HERE
	# REPLACE THE FOLLOWING LINES
	return {
		"rating":  '5.0',
        "choices": '[5.0]',
		"clocks":  '[{"c1":0}]'
	}

# Add a route for deleting all the rating information which can be accessed as:
# curl -XDELETE http://localhost:2500/rating/bob
# Response is a JSON object showing the new rating for the entity (always null)
# { rating: null }
@route('/rating/<entity>', method='DELETE')
def delete_rating(entity):
	count = client.delete('/rating/'+entity)
	if count == 0: return abort(404)
	return { "rating": None }

# Fire the engines
if __name__ == '__main__':
	run(host='0.0.0.0', port=os.getenv('PORT', 2500), quiet=True)
