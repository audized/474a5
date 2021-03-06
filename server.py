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
	# HINT: CONSIDER USING THE HASH DATA TYPE IN REDIS (HGET/HSET/...)
	old_rating = client.hget(key, 'rating')

	# if rating does not exist, add it. Otherwise..
	# SET THE RATING, CHOICES, AND CLOCKS IN THE DATABASE FOR THIS KEY
	# COMPUTE THE MEAN, finalrating
	if not old_rating:
		client.hset(key, 'rating', setrating)
		client.hset(key, 'choices', [setrating])
		client.hset(key, 'clocks', jsonify_vcl([setclock]))
		finalrating = setrating
	else:
		finalrating = old_rating
		choices = eval(client.hget(key, 'choices'))
		vcl = eval(client.hget(key, 'clocks'))
		new_vcl = []
		new_choices = []
		greaterThanAlreadyFound = False
		needToUpdateDB = True
		for i in range(0, len(vcl)):
			old_clock = VectorClock.fromDict(vcl[i])
			# if the received clock is older, nothing needs updating
			if setclock <= old_clock:
				needToUpdateDB = False
				break
			else:
				# if the received clock is newer, make changes accordingly
				if setclock > old_clock:
					# If we have not found an older clock and replaced it with the 
					# new one previously, put this new clock in. Otherwise, ignore.
					if not greaterThanAlreadyFound:
						greaterThanAlreadyFound = True
						new_vcl.append(setclock)
						new_choices.append(setrating)
				# incomparable
				else:
					new_vcl.append(old_clock)
					new_choices.append(choices[i])

		# Update DB only if the received clock is not older than or the same as any of the
		# existing clocks
		if needToUpdateDB:
			# if the received clock is not newer than any of the existing clocks, it's
			# incomparable
			if not greaterThanAlreadyFound:
				new_vcl.append(setclock)
				new_choices.append(setrating)

			# calculate the new rating
			ratingSum = 0.0
			for choice in new_choices:
				ratingSum+=choice
			finalrating = ratingSum/len(new_choices)

			# update DB
			client.hset(key, 'rating', finalrating)
			client.hset(key, 'choices', new_choices)
			client.hset(key, 'clocks', jsonify_vcl(new_vcl))
				

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
	key = '/rating/'+entity
	return {
		"rating": client.hget(key, 'rating'),
        	"choices": client.hget(key, 'choices'),
		"clocks": client.hget(key, 'clocks')
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

# Turn a list of vector clocks into a JSON formatted string to be stored in redis
def jsonify_vcl(vcl):
	i = 0
	json_str = '['
	#json_str = ''
	for vc in vcl:
		json_str = json_str+'{'
		i += 1
		j = 0
		for key in vc.clock.keys():
			json_str = json_str+'"'+key+'"'+': '+str(vc.clock[key])
			j+=1
			if j < len(vc.clock.keys()):
				json_str = json_str+', '
		json_str = json_str+'}'
		if i < len(vcl):
			json_str = json_str + ', '
	json_str = json_str+']'
	return json_str

# Fire the engines
if __name__ == '__main__':
	run(host='0.0.0.0', port=os.getenv('PORT', 2500), quiet=True)
